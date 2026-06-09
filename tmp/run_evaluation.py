"""Run Module 1 evaluation on all 8 corpus papers and produce comparison report."""

import json
import time
from pathlib import Path

from researchmind.models.intermediates import PipelineConfig
from researchmind.models.enums import CanonicalLabel, ResolutionStatus
from researchmind.pipeline import IngestionPipeline

EVAL_PAPERS_DIR = Path("eval_papers")
OUTPUT_DIR = Path("eval_output/sro_v2")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PAPERS = [
    "1406.2661_gan.pdf",
    "1412.6980_adam.pdf",
    "1502.03167_batchnorm.pdf",
    "1505.04597_unet.pdf",
    "1512.03385_resnet.pdf",
    "1706.03762_attention.pdf",
    "1810.04805_bert.pdf",
    "dropout_jmlr.pdf",
]

# Load config & enable CrossRef with mailto
config = PipelineConfig.load("config/default.yaml")
config.crossref.enabled = True
config.crossref.mailto = "researchmind-eval@example.com"
config.crossref.rate_limit = 2
config.crossref.retry_attempts = 3
config.crossref.retry_backoff_seconds = 2.0
config.crossref.resolve_threshold = 0.70
config.crossref.ambiguous_threshold = 0.50
config.quality.manual_review_threshold = 0.5

pipeline = IngestionPipeline(config)

# Previous evaluation summary (from evaluation_summary.json)
PREVIOUS = {
    "1406.2661_gan.pdf":    {"route": "grobid_primary",     "confidence": 0.7993, "sections": 10, "chunks": 13, "refs": 31, "citations": 40, "entities": 27, "claims": 11, "requires_review": False},
    "1412.6980_adam.pdf":   {"route": "grobid_primary",     "confidence": 0.7958, "sections": 14, "chunks": 20, "refs": 23, "citations": 31, "entities": 29, "claims": 23, "requires_review": False},
    "1502.03167_batchnorm.pdf": {"route": "grobid_with_fallback", "confidence": 0.2334, "sections": 6, "chunks": 34, "refs": 0, "citations": 0, "entities": 53, "claims": 34, "requires_review": True},
    "1505.04597_unet.pdf":  {"route": "grobid_primary",     "confidence": 0.8765, "sections": 6, "chunks": 11, "refs": 14, "citations": 23, "entities": 16, "claims": 15, "requires_review": False},
    "1512.03385_resnet.pdf":{"route": "grobid_primary",     "confidence": 0.8538, "sections": 18, "chunks": 27, "refs": 50, "citations": 135, "entities": 98, "claims": 38, "requires_review": False},
    "1706.03762_attention.pdf":{"route": "grobid_primary",  "confidence": 0.8373, "sections": 24, "chunks": 25, "refs": 41, "citations": 58, "entities": 32, "claims": 20, "requires_review": False},
    "1810.04805_bert.pdf":  {"route": "grobid_primary",     "confidence": 0.8411, "sections": 27, "chunks": 35, "refs": 58, "citations": 92, "entities": 117, "claims": 37, "requires_review": False},
    "dropout_jmlr.pdf":     {"route": "grobid_primary",     "confidence": 0.86,   "sections": 41, "chunks": 48, "refs": 36, "citations": 63, "entities": 86, "claims": 60, "requires_review": False},
}


def count_label(sections, label: CanonicalLabel) -> int:
    return sum(1 for s in sections if s.canonical_label == label)


results = []

for pdf_name in PAPERS:
    pdf_path = EVAL_PAPERS_DIR / pdf_name
    print(f"\n{'='*60}")
    print(f"Processing: {pdf_name}")
    print(f"{'='*60}")

    start = time.time()
    try:
        sro = pipeline.process(pdf_path)
        elapsed = round(time.time() - start, 2)
        print(f"  Done in {elapsed}s")

        # Save SRO JSON
        sro_path = OUTPUT_DIR / pdf_name.replace(".pdf", ".json")
        with open(sro_path, "w", encoding="utf-8") as f:
            f.write(sro.model_dump_json(indent=2))
        print(f"  Saved SRO to {sro_path}")

        # -- Extract metrics --
        route = sro.meta.extraction_route.value
        title = sro.header.title

        # Sections
        sections = sro.body.sections
        n_sections = len(sections)
        label_counts = {lbl: count_label(sections, lbl) for lbl in CanonicalLabel}

        # Chunks
        chunks = sro.body.chunks
        n_chunks = len(chunks)
        n_non_other = sum(1 for s in sections if s.canonical_label != CanonicalLabel.OTHER)
        n_other = n_sections - n_non_other

        # Refs
        refs = sro.references
        n_refs = len(refs)
        n_resolved = sum(1 for r in refs if r.resolution_status == ResolutionStatus.RESOLVED)
        n_ambiguous = sum(1 for r in refs if r.resolution_status == ResolutionStatus.AMBIGUOUS)
        n_unresolved = sum(1 for r in refs if r.resolution_status == ResolutionStatus.UNRESOLVED)

        # Citations
        citations = sro.citations
        n_citations = len(citations)
        n_linked = sum(1 for c in citations if c.ref_id is not None)

        # Entities / Claims
        entities = sro.entities
        claims = sro.candidate_claims
        n_entities = len(entities)
        n_claims = len(claims)

        confidence = sro.quality.overall_confidence
        requires_review = sro.quality.requires_manual_review

        prev = PREVIOUS.get(pdf_name, {})
        prev_confidence = prev.get("confidence", 0)

        # Section classification quality
        non_other_pct = (n_non_other / n_sections * 100) if n_sections else 0
        prev_non_other = prev.get("sections", 0) - (prev.get("other_sections", 0))
        # approximate prev non-other from report data
        prev_other_map = {
            "1810.04805_bert.pdf": 20,
            "1706.03762_attention.pdf": 15,
            "dropout_jmlr.pdf": 29,
        }
        prev_other = prev_other_map.get(pdf_name, 0)
        prev_sections = prev.get("sections", 0)
        prev_non_other_pct = ((prev_sections - prev_other) / prev_sections * 100) if prev_sections else 0

        print(f"  Route: {route}")
        print(f"  Sections: {n_sections} (non-other={n_non_other}, other={n_other})")
        print(f"  Chunks: {n_chunks}")
        print(f"  Refs: {n_refs} (resolved={n_resolved}, ambiguous={n_ambiguous}, unresolved={n_unresolved})")
        print(f"  Citations: {n_citations} (linked={n_linked})")
        print(f"  Confidence: {confidence:.4f}")
        print(f"  Requires review: {requires_review}")

        results.append({
            "file": pdf_name,
            "status": "success",
            "route": route,
            "title": title,
            "sections": n_sections,
            "sections_non_other": n_non_other,
            "sections_other": n_other,
            "chunks": n_chunks,
            "refs": n_refs,
            "refs_resolved": n_resolved,
            "refs_ambiguous": n_ambiguous,
            "refs_unresolved": n_unresolved,
            "citations": n_citations,
            "citations_linked": n_linked,
            "citations_unlinked": n_citations - n_linked,
            "entities": n_entities,
            "claims": n_claims,
            "confidence": round(confidence, 4),
            "requires_review": requires_review,
            "label_counts": {lbl.value: cnt for lbl, cnt in label_counts.items() if cnt > 0},
            "seconds": elapsed,
        })

    except Exception as exc:
        elapsed = round(time.time() - start, 2)
        import traceback
        print(f"  FAILED after {elapsed}s: {exc}")
        traceback.print_exc()
        results.append({
            "file": pdf_name,
            "status": "failed",
            "error": str(exc),
            "seconds": elapsed,
        })

# Save results
summary_path = OUTPUT_DIR / "evaluation_summary_v2.json"
with open(summary_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\nSaved summary to {summary_path}")

# Summary comparison
print("\n\n" + "=" * 70)
print("MODULE 1 RE-EVALUATION — AGGREGATE COMPARISON")
print("=" * 70)

new_success = [r for r in results if r["status"] == "success"]
n_new = len(new_success)
n_prev = len(PREVIOUS)

if n_new > 0:
    new_conf = [r["confidence"] for r in new_success]
    new_mean = sum(new_conf) / n_new
    prev_conf = [p["confidence"] for p in PREVIOUS.values()]
    prev_mean = sum(prev_conf) / n_prev

    new_routes = {}
    for r in new_success:
        new_routes[r["route"]] = new_routes.get(r["route"], 0) + 1
    prev_routes = {}
    for p in PREVIOUS.values():
        prev_routes[p["route"]] = prev_routes.get(p["route"], 0) + 1

    print(f"\nPapers processed: {n_new}/{len(PAPERS)}")
    print(f"  (prev: {n_prev}/{len(PAPERS)})")

    print(f"\nMean confidence: {new_mean:.4f}")
    print(f"  (prev: {prev_mean:.4f})")
    print(f"  delta: {new_mean - prev_mean:+.4f}")

    print(f"\nRoute distribution:")
    for route in sorted(set(list(new_routes.keys()) + list(prev_routes.keys()))):
        new_val = new_routes.get(route, 0)
        prev_val = prev_routes.get(route, 0)
        print(f"  {route}: {new_val}  (prev: {prev_val})")

    # Reference resolution
    new_total_refs = sum(r["refs"] for r in new_success)
    new_total_resolved = sum(r["refs_resolved"] for r in new_success)
    new_total_ambiguous = sum(r["refs_ambiguous"] for r in new_success)
    new_total_unresolved = sum(r["refs_unresolved"] for r in new_success)
    prev_total_refs = sum(p["refs"] for p in PREVIOUS.values())
    prev_total_resolved = sum(p.get("refs_resolved", 0) for p in PREVIOUS.values())

    print(f"\nReference resolution:")
    print(f"  Total refs: {new_total_refs}  (prev: {prev_total_refs})")
    print(f"  Resolved: {new_total_resolved}  (prev: {prev_total_resolved} — CrossRef was disabled)")
    print(f"  Ambiguous: {new_total_ambiguous}")
    print(f"  Unresolved: {new_total_unresolved}")

    # Citation linking
    new_total_cits = sum(r["citations"] for r in new_success)
    new_total_linked = sum(r["citations_linked"] for r in new_success)
    prev_total_cits = sum(p["citations"] for p in PREVIOUS.values())
    # Calculate prev linked from report data
    prev_linked_map = {
        "1810.04805_bert.pdf": 77,
        "1412.6980_adam.pdf": 29,
        "1505.04597_unet.pdf": 22,
        "1512.03385_resnet.pdf": 133,
        "dropout_jmlr.pdf": 62,
        "1406.2661_gan.pdf": 40,  # all linked
        "1706.03762_attention.pdf": 58,  # all linked
    }
    prev_linked = sum(
        prev_linked_map.get(p.get("file", p.get("pdf", "")), p["citations"])
        for p in PREVIOUS.values()
    )
    prev_cit_rate = (prev_linked / prev_total_cits * 100) if prev_total_cits else 0

    new_linked_rate = (new_total_linked / new_total_cits * 100) if new_total_cits else 0

    print(f"\nCitation linking:")
    print(f"  Total citations: {new_total_cits}  (prev: {prev_total_cits})")
    print(f"  Linked: {new_total_linked}  (prev: {prev_linked})")
    print(f"  Link rate: {new_linked_rate:.1f}%  (prev: {prev_cit_rate:.1f}%)")

    # Section classification
    new_total_sections = sum(r["sections"] for r in new_success)
    new_total_non_other = sum(r["sections_non_other"] for r in new_success)
    new_non_other_pct = (new_total_non_other / new_total_sections * 100) if new_total_sections else 0
    prev_total_sections = sum(p["sections"] for p in PREVIOUS.values())
    # Rough prev other count from report
    prev_other_approx = 20 + 15 + 29  # BERT, Attention, Dropout
    prev_non_other_pct = ((prev_total_sections - prev_other_approx) / prev_total_sections * 100) if prev_total_sections else 0

    print(f"\nSection classification:")
    print(f"  Total sections: {new_total_sections}  (prev: {prev_total_sections})")
    print(f"  Non-other: {new_total_non_other} ({new_non_other_pct:.1f}%)  (prev approx: {prev_total_sections - prev_other_approx} / {prev_non_other_pct:.1f}%)")

    # Manual review
    new_review = sum(1 for r in new_success if r["requires_review"])
    prev_review = sum(1 for p in PREVIOUS.values() if p["requires_review"])

    print(f"\nManual review required: {new_review}  (prev: {prev_review})")

    # Fallback frequency
    new_fallback = sum(1 for r in new_success if "fallback" in r["route"])
    prev_fallback = sum(1 for p in PREVIOUS.values() if "fallback" in p["route"])

    print(f"\nFallback route: {new_fallback}  (prev: {prev_fallback})")

print("\nDone.")
