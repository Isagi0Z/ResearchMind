"""Command-line interface for ResearchMind Module 1.

Provides commands for ingesting PDFs, listing processed papers, inspecting
SROs, validating schemas, and checking service health.

Usage::

    researchmind ingest paper.pdf
    researchmind ingest-batch ./papers/
    researchmind list --sort-by confidence
    researchmind inspect <sro_id>
    researchmind validate output/sro.json
    researchmind health
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from researchmind.models.intermediates import PipelineConfig, PipelineError
from researchmind.models.sro import StructuredResearchObject
from researchmind.pipeline import IngestionPipeline
from researchmind.storage.registry import PaperRegistry

logger = logging.getLogger(__name__)
console = Console()

# Default paths (relative to CWD)
_DEFAULT_CONFIG = "config/default.yaml"
_DEFAULT_OUTPUT = "output"


def _setup_logging(verbose: bool = False) -> None:
    """Configure logging for CLI usage."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    # Suppress noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _load_config(config_path: str | None) -> PipelineConfig:
    """Load pipeline configuration from a YAML file."""
    path = config_path or _DEFAULT_CONFIG
    config = PipelineConfig.load(path)
    logger.debug("Loaded config from %s", path)
    return config


def _save_sro(sro: StructuredResearchObject, output_dir: str) -> str:
    """Serialise an SRO to a JSON file and return the file path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    filename = f"{sro.meta.sro_id}.json"
    filepath = out / filename

    json_str = sro.model_dump_json(indent=2)
    filepath.write_text(json_str, encoding="utf-8")
    logger.info("SRO saved to %s", filepath)
    return str(filepath)


def _load_sro_from_json(json_path: str) -> StructuredResearchObject:
    """Load an SRO from a JSON file."""
    path = Path(json_path)
    if not path.exists():
        console.print(f"[red]File not found: {json_path}[/red]")
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    return StructuredResearchObject(**data)


# ======================================================================
# CLI group
# ======================================================================


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
def cli(verbose: bool) -> None:
    """ResearchMind — Scientific paper ingestion pipeline."""
    _setup_logging(verbose)


# ======================================================================
# ingest
# ======================================================================


@cli.command()
@click.argument("pdf_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--output-dir", "-o",
    default=None,
    help=f"Directory to write SRO JSON files.  [default: config or '{_DEFAULT_OUTPUT}']",
)
@click.option(
    "--config-path", "-c",
    default=None,
    help=f"Path to pipeline config YAML.  [default: '{_DEFAULT_CONFIG}']",
)
def ingest(pdf_path: str, output_dir: str | None, config_path: str | None) -> None:
    """Ingest a single PDF and produce a Structured Research Object."""
    config = _load_config(config_path)
    out_dir = output_dir or config.storage.output_dir or _DEFAULT_OUTPUT

    pipeline = IngestionPipeline(config)
    registry = PaperRegistry(config.storage.db_path)

    pdf = Path(pdf_path)
    console.print(f"\n[bold blue]Processing:[/bold blue] {pdf.name}")

    try:
        # Check for duplicates
        from researchmind.intake.fingerprint import fingerprint as _fp
        intake = _fp(pdf)
        dup_id = registry.find_duplicate(intake.sha256)
        if dup_id:
            console.print(
                f"[yellow]Duplicate detected — already processed as {dup_id}[/yellow]"
            )
            console.print("Use --force or process a different file.")
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Ingesting...", total=5)
            sro = pipeline.process(pdf)
            progress.update(task, completed=5)

        json_path = _save_sro(sro, out_dir)
        registry.register(sro, json_path)

        # Print summary
        _print_ingest_summary(sro, json_path)

    except PipelineError as exc:
        console.print(f"\n[red bold]Pipeline error[/red bold] ({exc.stage}): {exc.message}")
        sys.exit(1)
    except Exception as exc:
        console.print(f"\n[red bold]Unexpected error:[/red bold] {exc}")
        logger.exception("Unhandled error during ingestion")
        sys.exit(1)
    finally:
        registry.close()


def _print_ingest_summary(sro: StructuredResearchObject, json_path: str) -> None:
    """Print a formatted summary after successful ingestion."""
    console.print("\n[bold green]✓ Ingestion complete[/bold green]\n")

    table = Table(title="SRO Summary", show_header=False, border_style="dim")
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("SRO ID", sro.meta.sro_id)
    table.add_row("Title", sro.header.title[:100])
    table.add_row("Authors", str(len(sro.header.authors)))
    table.add_row("Pages", str(sro.meta.source_file.page_count))
    table.add_row("Route", sro.meta.extraction_route.value)
    table.add_row("Sections", str(len(sro.body.sections)))
    table.add_row("Chunks", str(len(sro.body.chunks)))
    table.add_row("References", str(len(sro.references)))
    table.add_row("Citations", str(len(sro.citations)))
    table.add_row("Entities", str(len(sro.entities)))
    table.add_row("Claims", str(len(sro.candidate_claims)))
    table.add_row("Confidence", f"{sro.quality.overall_confidence:.2%}")
    table.add_row("Review needed", "Yes" if sro.quality.requires_manual_review else "No")
    table.add_row("Output", json_path)

    if sro.quality.validation_errors:
        table.add_row(
            "Errors",
            f"[red]{len(sro.quality.validation_errors)}[/red]",
        )

    console.print(table)


# ======================================================================
# ingest-batch
# ======================================================================


@cli.command("ingest-batch")
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--skip-duplicates / --no-skip-duplicates",
    default=True,
    help="Skip PDFs whose SHA-256 is already in the registry.  [default: skip]",
)
@click.option("--output-dir", "-o", default=None, help="Directory for SRO JSON files.")
@click.option("--config-path", "-c", default=None, help="Path to pipeline config YAML.")
def ingest_batch(
    directory: str,
    skip_duplicates: bool,
    output_dir: str | None,
    config_path: str | None,
) -> None:
    """Ingest all PDF files in a directory."""
    config = _load_config(config_path)
    out_dir = output_dir or config.storage.output_dir or _DEFAULT_OUTPUT

    pdf_files = sorted(Path(directory).glob("*.pdf"))
    if not pdf_files:
        console.print(f"[yellow]No PDF files found in {directory}[/yellow]")
        return

    console.print(f"\n[bold blue]Found {len(pdf_files)} PDF(s) in {directory}[/bold blue]\n")

    pipeline = IngestionPipeline(config)
    registry = PaperRegistry(config.storage.db_path)

    successes = 0
    skipped = 0
    failures = 0

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Processing PDFs…", total=len(pdf_files))

            for pdf in pdf_files:
                progress.update(task, description=f"[cyan]{pdf.name}[/cyan]")

                try:
                    # Duplicate check
                    if skip_duplicates:
                        from researchmind.intake.fingerprint import fingerprint as _fp
                        intake = _fp(pdf)
                        dup_id = registry.find_duplicate(intake.sha256)
                        if dup_id:
                            logger.info("Skipping duplicate: %s (sro_id=%s)", pdf.name, dup_id)
                            skipped += 1
                            progress.advance(task)
                            continue

                    sro = pipeline.process(pdf)
                    json_path = _save_sro(sro, out_dir)
                    registry.register(sro, json_path)
                    successes += 1
                    logger.info("✓ %s → %s (confidence=%.2f)", pdf.name, sro.meta.sro_id, sro.quality.overall_confidence)

                except PipelineError as exc:
                    logger.error("✗ %s — pipeline error (%s): %s", pdf.name, exc.stage, exc.message)
                    failures += 1
                except Exception as exc:
                    logger.error("✗ %s — unexpected error: %s", pdf.name, exc, exc_info=True)
                    failures += 1

                progress.advance(task)

    finally:
        registry.close()

    # Summary
    console.print(f"\n[bold]Batch complete:[/bold]  "
                  f"[green]{successes} succeeded[/green]  "
                  f"[yellow]{skipped} skipped[/yellow]  "
                  f"[red]{failures} failed[/red]")


# ======================================================================
# list
# ======================================================================


@cli.command("list")
@click.option(
    "--sort-by", "-s",
    type=click.Choice(["confidence", "date", "title"], case_sensitive=False),
    default="date",
    help="Sort order.  [default: date]",
)
@click.option(
    "--min-confidence",
    type=float,
    default=0.0,
    help="Only show papers with confidence ≥ this value.",
)
@click.option("--config-path", "-c", default=None, help="Path to pipeline config YAML.")
def list_papers(sort_by: str, min_confidence: float, config_path: str | None) -> None:
    """List all processed papers from the registry."""
    config = _load_config(config_path)
    registry = PaperRegistry(config.storage.db_path)

    try:
        papers = registry.list_papers(min_confidence=min_confidence)

        if not papers:
            console.print("[yellow]No papers found in registry.[/yellow]")
            return

        # Sort
        sort_key_map: dict[str, str] = {
            "confidence": "overall_confidence",
            "date": "created_at",
            "title": "title",
        }
        key = sort_key_map.get(sort_by, "created_at")
        reverse = sort_by == "confidence"  # high confidence first
        papers.sort(key=lambda p: p.get(key, ""), reverse=reverse)

        # Build table
        table = Table(title=f"Processed Papers ({len(papers)})", border_style="dim")
        table.add_column("#", style="dim", width=4)
        table.add_column("SRO ID", style="cyan", max_width=36)
        table.add_column("Title", max_width=50)
        table.add_column("Confidence", justify="right", width=12)
        table.add_column("Route", width=20)
        table.add_column("Review", width=8)
        table.add_column("Date", width=20)

        for i, p in enumerate(papers, 1):
            conf = p.get("overall_confidence", 0.0)
            conf_style = "green" if conf >= 0.7 else ("yellow" if conf >= 0.5 else "red")
            review = "⚠ Yes" if p.get("requires_review") else "No"
            review_style = "yellow" if p.get("requires_review") else "green"

            table.add_row(
                str(i),
                p.get("sro_id", "?")[:36],
                (p.get("title", "?") or "?")[:50],
                f"[{conf_style}]{conf:.2%}[/{conf_style}]",
                p.get("extraction_route", "?"),
                f"[{review_style}]{review}[/{review_style}]",
                (p.get("created_at", "?") or "?")[:19],
            )

        console.print(table)
    finally:
        registry.close()


# ======================================================================
# inspect
# ======================================================================


@cli.command()
@click.argument("target")
@click.option("--config-path", "-c", default=None, help="Path to pipeline config YAML.")
def inspect(target: str, config_path: str | None) -> None:
    """Inspect a processed paper by SRO ID or JSON file path.

    TARGET can be an SRO ID (UUID) or a path to an SRO JSON file.
    """
    config = _load_config(config_path)

    # Determine if target is a file path or an SRO ID
    target_path = Path(target)
    if target_path.exists() and target_path.suffix == ".json":
        sro = _load_sro_from_json(str(target_path))
    else:
        # Try to find it in the registry
        registry = PaperRegistry(config.storage.db_path)
        try:
            paper = registry.get_paper(target)
            if paper is None:
                console.print(f"[red]Paper not found: {target}[/red]")
                console.print("Provide a valid SRO ID or path to an SRO JSON file.")
                sys.exit(1)
            json_path = paper["json_path"]
            if not Path(json_path).exists():
                console.print(f"[red]JSON file missing: {json_path}[/red]")
                sys.exit(1)
            sro = _load_sro_from_json(json_path)
        finally:
            registry.close()

    _print_sro_detail(sro)


def _print_sro_detail(sro: StructuredResearchObject) -> None:
    """Pretty-print a detailed SRO summary using Rich."""
    console.print(f"\n[bold cyan]═══ SRO Inspection ═══[/bold cyan]\n")

    # --- Meta ---
    meta_table = Table(title="Meta", show_header=False, border_style="dim")
    meta_table.add_column("Field", style="bold", width=22)
    meta_table.add_column("Value")
    meta_table.add_row("SRO ID", sro.meta.sro_id)
    meta_table.add_row("Schema version", sro.meta.schema_version)
    meta_table.add_row("Pipeline version", sro.meta.pipeline_version)
    meta_table.add_row("Created at", sro.meta.created_at.isoformat())
    meta_table.add_row("Extraction route", sro.meta.extraction_route.value)
    meta_table.add_row("Source file", sro.meta.source_file.filename)
    meta_table.add_row("SHA-256", sro.meta.source_file.sha256[:16] + "…")
    meta_table.add_row("Page count", str(sro.meta.source_file.page_count))
    meta_table.add_row("Processing time", f"{sro.meta.processing_time_ms or 0}ms")
    console.print(meta_table)

    # --- Header ---
    console.print(f"\n[bold]Title:[/bold]  {sro.header.title}")
    if sro.header.authors:
        author_str = ", ".join(a.full_name for a in sro.header.authors[:5])
        if len(sro.header.authors) > 5:
            author_str += f" … (+{len(sro.header.authors) - 5} more)"
        console.print(f"[bold]Authors:[/bold]  {author_str}")
    if sro.header.doi:
        console.print(f"[bold]DOI:[/bold]  {sro.header.doi}")

    # --- Abstract ---
    abstract_preview = sro.abstract.raw_text[:300]
    if len(sro.abstract.raw_text) > 300:
        abstract_preview += "…"
    console.print(f"\n[bold]Abstract[/bold] (structured={sro.abstract.is_structured}, "
                  f"confidence={sro.abstract.confidence:.2f}):")
    console.print(f"  {abstract_preview}")

    # --- Body stats ---
    stats_table = Table(title="\nBody & Annotations", border_style="dim")
    stats_table.add_column("Component", style="bold")
    stats_table.add_column("Count", justify="right")
    stats_table.add_row("Sections", str(len(sro.body.sections)))
    stats_table.add_row("Chunks", str(len(sro.body.chunks)))
    stats_table.add_row("Tables", str(len(sro.body.tables)))
    stats_table.add_row("Figures", str(len(sro.body.figures)))
    stats_table.add_row("References", str(len(sro.references)))
    stats_table.add_row("Citations", str(len(sro.citations)))
    stats_table.add_row("Entities", str(len(sro.entities)))
    stats_table.add_row("Candidate claims", str(len(sro.candidate_claims)))
    console.print(stats_table)

    # --- Quality ---
    q = sro.quality
    qual_table = Table(title="\nQuality", show_header=False, border_style="dim")
    qual_table.add_column("Field", style="bold", width=22)
    qual_table.add_column("Value")

    conf_style = "green" if q.overall_confidence >= 0.7 else ("yellow" if q.overall_confidence >= 0.5 else "red")
    qual_table.add_row("Overall confidence", f"[{conf_style}]{q.overall_confidence:.2%}[/{conf_style}]")
    qual_table.add_row("Requires review", "[yellow]Yes[/yellow]" if q.requires_manual_review else "[green]No[/green]")

    fs = q.field_scores
    qual_table.add_row("  Title score", f"{fs.title:.2f}")
    qual_table.add_row("  Authors score", f"{fs.authors:.2f}")
    qual_table.add_row("  Abstract score", f"{fs.abstract:.2f}")
    qual_table.add_row("  Sections score", f"{fs.sections:.2f}")
    qual_table.add_row("  References score", f"{fs.references:.2f}")
    qual_table.add_row("  Entities score", f"{fs.entities:.2f}")
    console.print(qual_table)

    if q.validation_errors:
        console.print(f"\n[red bold]Validation Errors ({len(q.validation_errors)}):[/red bold]")
        for err in q.validation_errors[:10]:
            console.print(f"  [red]• {err}[/red]")

    if q.validation_warnings:
        console.print(f"\n[yellow]Validation Warnings ({len(q.validation_warnings)}):[/yellow]")
        for w in q.validation_warnings[:10]:
            console.print(f"  [yellow]• {w}[/yellow]")

    # --- Pipeline log ---
    if q.pipeline_log:
        log_table = Table(title="\nPipeline Log", border_style="dim")
        log_table.add_column("Stage")
        log_table.add_column("Status")
        log_table.add_column("Duration", justify="right")
        log_table.add_column("Warnings", justify="right")
        log_table.add_column("Errors", justify="right")

        for entry in q.pipeline_log:
            status_style = {
                "success": "green",
                "partial": "yellow",
                "failed": "red",
                "skipped": "dim",
            }.get(entry.status.value, "white")

            log_table.add_row(
                entry.stage,
                f"[{status_style}]{entry.status.value}[/{status_style}]",
                f"{entry.duration_ms or 0}ms",
                str(len(entry.warnings)),
                str(len(entry.errors)),
            )
        console.print(log_table)

    console.print()


# ======================================================================
# validate
# ======================================================================


@cli.command()
@click.argument("json_path", type=click.Path(exists=True, dir_okay=False))
def validate(json_path: str) -> None:
    """Validate an SRO JSON file against the schema."""
    console.print(f"\n[bold blue]Validating:[/bold blue] {json_path}")

    try:
        sro = _load_sro_from_json(json_path)
    except Exception as exc:
        console.print(f"\n[red bold]Schema validation FAILED[/red bold]")
        console.print(f"  Error: {exc}")
        sys.exit(1)

    # Run additional semantic validation
    from researchmind.quality.validator import validate_sro as _validate
    errors, warnings = _validate(sro)

    if errors:
        console.print(f"\n[red bold]Validation FAILED — {len(errors)} error(s)[/red bold]")
        for err in errors:
            console.print(f"  [red]✗ {err}[/red]")
    else:
        console.print(f"\n[green bold]✓ Validation PASSED[/green bold]")

    if warnings:
        console.print(f"\n[yellow]{len(warnings)} warning(s):[/yellow]")
        for w in warnings:
            console.print(f"  [yellow]⚠ {w}[/yellow]")

    console.print(f"\n  SRO ID:      {sro.meta.sro_id}")
    console.print(f"  Title:       {sro.header.title[:80]}")
    console.print(f"  Confidence:  {sro.quality.overall_confidence:.2%}")
    console.print()

    if errors:
        sys.exit(1)


# ======================================================================
# health
# ======================================================================


@cli.command()
@click.option("--config-path", "-c", default=None, help="Path to pipeline config YAML.")
def health(config_path: str | None) -> None:
    """Check service health — GROBID, NLP models, disk space."""
    config = _load_config(config_path)

    console.print("\n[bold cyan]═══ Health Check ═══[/bold cyan]\n")

    checks: list[tuple[str, bool, str]] = []

    # 1. GROBID service
    grobid_ok, grobid_msg = _check_grobid(config.grobid.url)
    checks.append(("GROBID service", grobid_ok, grobid_msg))

    # 2. spaCy model
    spacy_ok, spacy_msg = _check_spacy_model(config.ner.general_model)
    checks.append((f"spaCy model ({config.ner.general_model})", spacy_ok, spacy_msg))

    # 3. Biomedical model (if enabled)
    if config.ner.enable_biomedical:
        bio_ok, bio_msg = _check_spacy_model(config.ner.biomedical_model)
        checks.append((f"Biomedical model ({config.ner.biomedical_model})", bio_ok, bio_msg))

    # 4. NLTK data
    nltk_ok, nltk_msg = _check_nltk()
    checks.append(("NLTK punkt tokenizer", nltk_ok, nltk_msg))

    # 5. Disk space
    disk_ok, disk_msg = _check_disk_space(config.storage.output_dir)
    checks.append(("Disk space", disk_ok, disk_msg))

    # 6. SQLite registry
    db_ok, db_msg = _check_registry(config.storage.db_path)
    checks.append(("Paper registry (SQLite)", db_ok, db_msg))

    # Display results
    table = Table(border_style="dim")
    table.add_column("Component", style="bold")
    table.add_column("Status", width=8)
    table.add_column("Details")

    all_ok = True
    for name, ok, msg in checks:
        if ok:
            table.add_row(name, "[green]✓ OK[/green]", msg)
        else:
            table.add_row(name, "[red]✗ FAIL[/red]", f"[red]{msg}[/red]")
            all_ok = False

    console.print(table)

    if all_ok:
        console.print("\n[bold green]All checks passed.[/bold green]\n")
    else:
        console.print("\n[bold red]Some checks failed — see above.[/bold red]\n")
        sys.exit(1)


def _check_grobid(url: str) -> tuple[bool, str]:
    """Ping the GROBID service."""
    try:
        import httpx
        resp = httpx.get(f"{url}/api/isalive", timeout=5)
        if resp.status_code == 200:
            return True, f"Running at {url}"
        return False, f"HTTP {resp.status_code} at {url}"
    except Exception as exc:
        return False, f"Cannot reach {url} — {exc}"


def _check_spacy_model(model_name: str) -> tuple[bool, str]:
    """Check whether a spaCy model is installed."""
    try:
        import spacy
        spacy.load(model_name)
        return True, "Loaded successfully"
    except OSError:
        return False, f"Model '{model_name}' not installed.  Run: python -m spacy download {model_name}"
    except Exception as exc:
        return False, f"Error loading model: {exc}"


def _check_nltk() -> tuple[bool, str]:
    """Check whether NLTK punkt tokenizer data is available."""
    try:
        import nltk
        nltk.data.find("tokenizers/punkt_tab")
        return True, "punkt tokenizer available"
    except LookupError:
        return False, "NLTK punkt data missing.  Run: python -c \"import nltk; nltk.download('punkt_tab')\""
    except Exception as exc:
        return False, f"NLTK check error: {exc}"


def _check_disk_space(output_dir: str) -> tuple[bool, str]:
    """Check available disk space in the output directory."""
    try:
        path = Path(output_dir).resolve()
        # Use the drive root if the directory doesn't exist yet
        check_path = path if path.exists() else path.anchor or "."
        usage = shutil.disk_usage(check_path)
        free_gb = usage.free / (1024 ** 3)
        if free_gb < 1.0:
            return False, f"Only {free_gb:.1f} GB free — need at least 1 GB"
        return True, f"{free_gb:.1f} GB free"
    except Exception as exc:
        return False, f"Cannot check disk space: {exc}"


def _check_registry(db_path: str) -> tuple[bool, str]:
    """Check whether the SQLite registry can be opened."""
    try:
        registry = PaperRegistry(db_path)
        count = len(registry.list_papers())
        registry.close()
        return True, f"{count} paper(s) registered"
    except Exception as exc:
        return False, f"Cannot open registry: {exc}"


# ======================================================================
# Entry point
# ======================================================================

if __name__ == "__main__":
    cli()
