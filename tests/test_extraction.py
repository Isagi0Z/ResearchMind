"""Quick integration test — runs the pipeline through fallback extraction."""
from pathlib import Path
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(name)s: %(message)s")

# Suppress noisy loggers
for name in ("httpx", "httpcore", "urllib3", "PIL"):
    logging.getLogger(name).setLevel(logging.WARNING)

pdf_path = Path(r"D:\RM\tests\test_data\sample_paper.pdf")

# --- Test 1: PyMuPDF Extractor ---
print("\n=== Test 1: PyMuPDF Extraction ===")
from researchmind.extraction.pymupdf_extractor import extract_with_pymupdf

sections = extract_with_pymupdf(pdf_path)
print(f"Extracted {len(sections)} sections:")
for i, s in enumerate(sections):
    preview = s.paragraphs[0][:60] + "..." if s.paragraphs else "(empty)"
    print(f"  [{i}] header=\"{s.header[:50]}\"  paras={len(s.paragraphs)}  pages={s.page_start}-{s.page_end}")

# --- Test 2: Section Normalizer ---
print("\n=== Test 2: Section Normalization ===")
from researchmind.structuring.section_normalizer import normalize_sections

sro_sections = normalize_sections(sections)
print(f"Normalised {len(sro_sections)} sections:")
for s in sro_sections:
    print(f"  {s.section_id}: {s.canonical_label.value} (conf={s.label_confidence:.2f}) <- \"{s.original_header[:40]}\"")

# --- Test 3: Chunker ---
print("\n=== Test 3: Chunking ===")
from researchmind.structuring.chunker import chunk_sections
from researchmind.models.intermediates import ChunkingConfig

chunks = chunk_sections(sro_sections, ChunkingConfig(min_words=20, max_words=300))
print(f"Created {len(chunks)} chunks:")
for c in chunks:
    print(f"  {c.chunk_id}: {c.word_count} words, section={c.section_id}, label={c.canonical_label.value}")

# --- Test 4: NER (pattern matching only, no spaCy model needed) ---
print("\n=== Test 4: NER (pattern-only) ===")
from researchmind.enrichment.ner_extractor import extract_entities
from researchmind.models.intermediates import NERConfig

ner_config = NERConfig(general_model="en_core_web_sm", enable_biomedical=False, enable_custom_patterns=True)
entities = extract_entities(chunks, ner_config)
print(f"Extracted {len(entities)} entities:")
for e in entities[:10]:
    print(f"  {e.entity_id}: \"{e.text}\" [{e.label.value}] (conf={e.confidence:.2f}, source={e.source})")
if len(entities) > 10:
    print(f"  ... and {len(entities) - 10} more")

# --- Test 5: Claim Detection ---
print("\n=== Test 5: Claim Detection ===")
from researchmind.enrichment.claim_detector import detect_claims

claims = detect_claims(chunks, sro_sections)
print(f"Detected {len(claims)} candidate claims:")
for c in claims[:5]:
    print(f"  {c.claim_id}: [{c.claim_type.value}] conf={c.confidence:.2f}")
    print(f"    \"{c.sentence[:80]}...\"")
if len(claims) > 5:
    print(f"  ... and {len(claims) - 5} more")

# --- Test 6: Full Pipeline (GROBID will fail → fallback) ---
print("\n=== Test 6: Full Pipeline Integration ===")
from researchmind.models.intermediates import PipelineConfig
from researchmind.pipeline import IngestionPipeline

config = PipelineConfig()
# Disable CrossRef (no network needed for test)
config.crossref.enabled = False
# Use pattern-only NER (no spaCy models needed)
config.ner.general_model = "en_core_web_sm"
config.ner.enable_biomedical = False
config.ner.enable_custom_patterns = True

pipeline = IngestionPipeline(config)

try:
    sro = pipeline.process(pdf_path)
    print(f"\n✓ Pipeline completed successfully!")
    print(f"  SRO ID:       {sro.meta.sro_id}")
    print(f"  Title:        {sro.header.title[:60]}")
    print(f"  Authors:      {len(sro.header.authors)}")
    print(f"  Sections:     {len(sro.body.sections)}")
    print(f"  Chunks:       {len(sro.body.chunks)}")
    print(f"  References:   {len(sro.references)}")
    print(f"  Citations:    {len(sro.citations)}")
    print(f"  Entities:     {len(sro.entities)}")
    print(f"  Claims:       {len(sro.candidate_claims)}")
    print(f"  Confidence:   {sro.quality.overall_confidence:.2%}")
    print(f"  Review needed: {sro.quality.requires_manual_review}")
    print(f"  Processing:   {sro.meta.processing_time_ms}ms")
    
    # Save the SRO to the temp dir (not tracked by git) to keep working tree clean
    import json
    out_path = Path(r"D:\RM\.tmp\test_output.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(sro.model_dump_json(indent=2), encoding="utf-8")
    print(f"\n  SRO saved to: {out_path}")

    
    # Check pipeline log
    print(f"\n  Pipeline stages:")
    for entry in sro.quality.pipeline_log:
        print(f"    {entry.stage}: {entry.status.value} ({entry.duration_ms}ms)")
        if entry.warnings:
            for w in entry.warnings:
                print(f"      ⚠ {w[:80]}")
    
    print("\n✓ ALL TESTS PASSED!")
    
except Exception as exc:
    print(f"\n✗ Pipeline failed: {exc}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
