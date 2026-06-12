# Module 6 Evaluation Plan

**References:** Architecture (Section 12), M5 Evaluation Pattern (`audit/run_m5_eval.py`, `eval_output/module5_evaluation.md`, `eval_output/module5_metrics.json`)

---

## 1. Evaluation Script: `audit/run_m6_eval.py`

Follows the same structure as `run_m5_eval.py`:

```
run_m6_eval.py
├── 1. Load 8-paper corpus (reuse load_corpus from audit/run_final_eval.py)
├── 2. Wire M4 engines (MultiHopReasoner, ConsensusEngine, ContradictionEngine, ResearchGapEngine)
├── 3. Wire M5 QueryEngine (for AggregatedEvidence source)
├── 4. Wire M6 ReviewOrchestrator
├── 5. Run evaluation tasks:
│   ├── Task 1: Section Completeness — all 8 ReviewTypes
│   ├── Task 2: Finding Traceability — 50 random findings
│   ├── Task 3: Determinism — 8 review types × 2 runs
│   ├── Task 4: Confidence Bounds — all findings across all reviews
│   ├── Task 5: No-Fabrication — all findings
│   ├── Task 6: Pipeline Edge Cases — empty corpus, single doc, sparse graph
│   └── Task 7: Performance — P50/P95 timing
├── 6. Compute scores
├── 7. Generate eval_output/module6_evaluation.md
└── 8. Generate eval_output/module6_metrics.json
```

---

## 2. Evaluation Tasks

### Task 1: Section Completeness

Generate all 8 ReviewTypes. Verify mandatory sections present.

| ReviewType | Expected Mandatory Sections | Min Findings |
|---|---|---|
| GENERAL | abstract, introduction, methods_landscape, conclusion | 20 |
| METHOD | abstract, methods_landscape, comparative | 15 |
| DATASET | abstract, datasets | 10 |
| CONSENSUS | abstract, consensus | 8 |
| CONTRADICTION | abstract, contradictions | 5 |
| RESEARCH_GAP | abstract, research_gaps | 8 |
| COMPARATIVE | abstract, comparative | 10 |
| LANDSCAPE | abstract, introduction, conclusion | 12 |

Success rate = (present mandatory sections) / (total mandatory sections across all types).

### Task 2: Finding Traceability

Sample 50 findings across all review types. For each:
- Check `finding.evidence_ids` is non-empty
- Resolve each `evidence_id` to `AggregatedEvidence` in the evidence index
- Check `AggregatedEvidence.source_document_id` exists in corpus
- Check trace chain (if required by evidence_type)

Success rate = findings with fully valid chains / total sampled.

### Task 3: Determinism

Run each of the 8 ReviewTypes twice. Compare:
- per-section finding count
- per-section confidence
- section word count
- overall confidence

All must be identical across runs. Success = 100%.

### Task 4: Confidence Bounds

Collect all `ReviewFinding.confidence`, `ReviewSection.confidence`, `ReviewResult.confidence` values across all reviews. Verify all in [0.0, 1.0].

### Task 5: No-Fabrication

Every `ReviewFinding.statement` must map to at least one `AggregatedEvidence` item. Verified by traceability check (Task 2). Additional audit: random sample of 20 statements, verify template structure matches expected finding type.

### Task 6: Pipeline Edge Cases

| Edge Case | Input | Expected Behavior |
|---|---|---|
| Empty corpus | corpus_ids = ["nonexistent"] | Error ReviewResult with "No documents in corpus" |
| Single document | Filter to 1 document via corpus_ids | Generates document summary (not crash); warns about insufficient cross-doc synthesis |
| Sparse graph (no edges) | Mock graph with 0 edges | Single Uncategorized theme; document catalog output |
| All engines None | All M4 engines = None | Empty sections with warnings (not crash) |
| max_findings = 1 | Limit findings per section to 1 | Each section has ≤ 1 finding |
| min_confidence = 0.9 | High confidence threshold | Only high-confidence findings included (possibly empty sections) |

### Task 7: Performance

Measure wall-clock time for:
- Each of the 8 review types (single run)
- Full suite of all 8 types (sequential)

Report P50 and P95 across runs. Targets: P50 < 30s, P95 < 120s on 8-paper corpus.

---

## 3. Metrics Output Format

### `eval_output/module6_metrics.json`

```json
{
  "corpus": {
    "papers": ["GAN", "Adam", "BatchNorm", "U-Net", "ResNet",
               "Attention", "BERT", "Dropout"],
    "graph_nodes": 57,
    "graph_edges": 1458,
    "doc_count": 8,
    "entity_cluster_count": 49
  },
  "task_results": {
    "SectionCompleteness": {
      "total": 8,
      "mandatory_present": 8,
      "success_rate": 1.0
    },
    "FindingTraceability": {
      "total": 50,
      "valid": 48,
      "rate": 0.96,
      "failures": []
    },
    "Determinism": {
      "total": 8,
      "identical_pairs": 8,
      "rate": 1.0,
      "differences": []
    },
    "ConfidenceBounds": {
      "total_findings": 200,
      "violations": 0
    },
    "NoFabrication": {
      "total_findings": 200,
      "verified": 200,
      "rate": 1.0
    },
    "PipelineEdgeCases": {
      "total": 6,
      "passed": 6,
      "rate": 1.0,
      "failures": []
    },
    "Performance": {
      "total_duration_seconds": 45.0,
      "p50_seconds": 4.5,
      "p95_seconds": 28.0
    }
  },
  "per_review_type": {
    "general": {
      "sections": 6,
      "findings": 25,
      "confidence": 0.45,
      "duration_seconds": 8.2
    },
    "method": { "...": "..." },
    "dataset": { "...": "..." },
    "consensus": { "...": "..." },
    "contradiction": { "...": "..." },
    "research_gap": { "...": "..." },
    "comparative": { "...": "..." },
    "landscape": { "...": "..." }
  },
  "summary": {
    "total_reviews": 8,
    "total_sections": 42,
    "total_findings": 160,
    "avg_confidence": 0.38,
    "traceability_rate": 0.96,
    "determinism_rate": 1.0,
    "no_fabrication_rate": 1.0,
    "pipeline_edge_case_rate": 1.0
  },
  "verdict": "READY"
}
```

---

## 4. Acceptance Gates

| Gate | Metric | Minimum | Blocking? |
|---|---|---|---|
| GATE 1: Determinism | Identical output on repeat | 100% | Yes |
| GATE 2: Traceability | Findings with valid evidence chains | ≥ 95% | Yes |
| GATE 3: Confidence bounds | Values in [0.0, 1.0] | 0 violations | Yes |
| GATE 4: No fabrication | All statements traceable | 0 violations | Yes |
| GATE 5: Section completeness | Mandatory sections present | 100% | No |
| GATE 6: Pipeline edge cases | Graceful handling | 100% | No |

---

## 5. Final Verdict

| Verdict | Criteria |
|---|---|
| **READY** | All 6 gates pass |
| **READY WITH FIXES** | Gates 1-4 pass, 5-6 documented |
| **NOT READY** | Any of gates 1-4 fail |

---

## 6. Test Queries / Review Requests

```python
_EVAL_REQUESTS = [
    # (review_type, title, corpus_ids, max_findings, min_confidence)
    ("general",       "Deep Learning Methods: A Literature Review", [],         10, 0.3),
    ("method",        "Methods Landscape in Deep Learning",         [],         10, 0.3),
    ("dataset",       "Datasets in Deep Learning Research",         [],         10, 0.3),
    ("consensus",     "Consensus Analysis of Deep Learning Claims", [],         10, 0.3),
    ("contradiction", "Contradictions in Deep Learning",            [],         10, 0.3),
    ("research_gap",  "Research Gaps in Deep Learning",             [],         10, 0.3),
    ("comparative",   "Comparative Analysis of Deep Learning Methods", [],      10, 0.3),
    ("landscape",     "Deep Learning Research Landscape",           [],         10, 0.3),
    # Edge case requests
    ("general",       "Empty Corpus Review",                       ["nonexistent"], 10, 0.3),
]

def make_eval_request(review_type, title, corpus_ids, max_findings=10, min_confidence=0.3):
    return ReviewRequest(
        review_id=f"eval_{review_type}",
        review_type=review_type,
        title=title,
        corpus_ids=corpus_ids,
        max_findings_per_section=max_findings,
        min_confidence=min_confidence,
    )
```
