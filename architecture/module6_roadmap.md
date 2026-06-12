# Module 6 Implementation Roadmap

**Date:** 2026-06-11
**Architecture Audit Verdict:** READY WITH FIXES (all violations resolved)
**Total estimated effort:** 17 days

---

## Phase 0: Project Scaffolding (0.5 day)

### Tasks
- [ ] Create `src/researchmind/synthesis/__init__.py` with package exports
- [ ] Create `tests/test_synthesis_*.py` stubs (one per module)
- [ ] Define `StrEnum` backport in `__init__.py` (consistent with M4/M5 pattern)
- [ ] Export `_generate_id()` helper for deterministic CRC32 ID generation

### Dependencies
- None (new package)

### Acceptance
- `python -c "from researchmind.synthesis import *"` succeeds
- `_generate_id("prefix", "a", "b")` returns deterministic, reproducible string

---

## Phase 1: Data Models (1 day)

### Files
- `src/researchmind/synthesis/models.py`

### Components
| Model | Fields | Deterministic ID |
|---|---|---|
| `ReviewType(StrEnum)` | 8 values: GENERAL, METHOD, DATASET, CONSENSUS, CONTRADICTION, RESEARCH_GAP, COMPARATIVE, LANDSCAPE | N/A (enum) |
| `ThemeType(StrEnum)` | 5 values: METHOD, DATASET, METRIC, CONCEPT, MIXED | N/A (enum) |
| `ReviewRequest` | review_id, review_type, title, corpus_ids, max_findings_per_section, min_confidence, include_abstract, include_bibliography, include_traceability_report, custom_sections | review_id caller-provided |
| `ReviewFinding` | finding_id, finding_type, statement, confidence, evidence_ids, source_document_ids, source_document_titles, supporting_count, contradicting_count, neutral_count, metadata | CRC32: `section_type::theme_label::index` |
| `ReviewSection` | section_id, section_type, title, summary, findings, paragraphs, confidence, word_count, is_mandatory | CRC32: `review_type::section_type::sequence` |
| `ReviewResult` | review_id, review_type, title, abstract, sections, total_findings, total_evidence_items, total_documents_cited, total_words, confidence, traceability_verified, traceability_failures, warnings, errors, bibliography, source_attribution | review_id copied from request; no timestamps |
| `EvidenceBundle` | bundle_id, theme, evidence_items, source_document_ids, aggregate_confidence, finding_type | CRC32: `theme_label::finding_type` |
| `ThemeCluster` | theme_id, label, entity_cluster_ids, entity_labels, document_ids, relation_types, evidence_count, confidence | CRC32: `component_label::entity_count` |

### Key design decisions
- All IDs deterministic via `zlib.crc32` (consistent with M5)
- No `generated_at`, no `datetime.now()`, no `uuid`
- `AggregatedEvidence` reused from M5 (`researchmind.query.models`)
- Pydantic v2: `field_validator` (not `validator`), `model_config`
- Python 3.9: `from __future__ import annotations`, StrEnum backport

### Dependencies
- Phase 0 (scaffolding)

### Tests
- `tests/test_synthesis_models.py` — model creation, validation, serialization, determinism

### Acceptance criteria
- All 7 models instantiate without validation errors
- Determinism: same inputs → same IDs across runs
- Serialization round-trip: model → dict → model preserves all fields
- Edge cases: empty lists, zero values, boundary confidence values

---

## Phase 2: Theme Detector (2 days)

### Files
- `src/researchmind/synthesis/theme_detector.py`

### Components
| Component | Description |
|---|---|
| `ThemeDetector` | Top-level class |
| `detect_themes(graph, max_themes, min_cluster_size)` | Main entry point |
| `_build_co_occurrence_matrix(graph)` | COMPARES_WITH edge analysis |
| `_find_connected_components(matrix)` | Deterministic graph components |
| `_label_theme(component, graph)` | Highest-degree entity label |
| `_classify_theme_type(cluster_labels)` | METHOD/DATASET/METRIC/CONCEPT/MIXED |
| `_compute_theme_confidence(component)` | Mean edge confidence |

### Algorithm
1. Extract entity clusters from `CorpusGraphResult`
2. Build co-occurrence matrix from COMPARES_WITH edges
3. Connected components on co-occurrence subgraph
4. For each component: label (highest-degree), entities (union), documents (union), relation types (union), confidence (mean)
5. Sort by confidence descending, apply max_themes limit
6. If < 2 entity clusters: single "Uncategorized" theme with warning

### Dependencies
- Phase 1 (models)
- M3 `CorpusGraphResult` (read-only)

### Tests
- `tests/test_theme_detector.py`
  - 3+ distinct themes on 8-paper corpus
  - Empty graph → single Uncategorized theme
  - Single entity → single theme
  - Max themes truncation
  - Theme labeling: highest-degree entity wins
  - Determinism: repeat → identical output

### Acceptance criteria
- Detects ≥ 2 themes on 8-paper evaluation corpus
- All themes have non-empty entity_cluster_ids and labels
- Deterministic: identical graph → identical theme list
- ThemeType classification matches majority entity label

---

## Phase 3: Evidence Collector (2 days)

### Files
- `src/researchmind/synthesis/evidence_collector.py`

### Components
| Component | Description |
|---|---|
| `EvidenceCollector` | Top-level class |
| `collect(corpus, graph, m4_engines)` | Main entry point |
| `_collect_consensus(clusters, consensus_engine)` | Per-cluster consensus |
| `_collect_contradictions(clusters, contradiction_engine)` | Per-cluster contradictions |
| `_collect_gaps(gap_engine)` | Full corpus gap analysis |
| `_collect_multi_hop(clusters, multi_hop_reasoner)` | Entity neighborhood |
| `_consolidate(raw_bundles)` | Merge, dedup, rank evidence |
| `_deduplicate_evidence(bundles)` | Dedup by (evidence_id, type) |
| `_compute_bundle_confidence(items)` | Min-of-maxes aggregation |

### M4 engine wrappers
Each wrapper calls the corresponding M4 engine and converts output to `EvidenceBundle` lists:
- `ConsensusEngine.analyze(cluster_id)` → bundles with finding_type="consensus"
- `ContradictionEngine.analyze(cluster_id)` → bundles with finding_type="contradiction"
- `ResearchGapEngine.analyze()` → bundles with finding_type="gap"
- `MultiHopReasoner.reason(cluster_id)` → bundles with finding_type="method"/"dataset"

### Dependencies
- Phase 1 (models)
- M4 engines (ConsensusEngine, ContradictionEngine, ResearchGapEngine, MultiHopReasoner)

### Tests
- `tests/test_evidence_collector.py`
  - Collection from all 4 M4 engines with mock data
  - Engine unavailable → skip gracefully with warning
  - Empty engine results → empty bundles (not crash)
  - Deduplication: same evidence_id appears once
  - Bundle confidence aggregation
  - Determinism: same inputs → identical bundles

### Acceptance criteria
- Collects evidence from all 4 M4 engines without error
- Engine failure → partial collection with warning (not crash)
- No duplicate evidence_ids in output
- Each bundle has non-empty evidence_items or is omitted

---

## Phase 4: Finding Generator (3 days)

### Files
- `src/researchmind/synthesis/finding_generator.py`

### Components
| Component | Description |
|---|---|
| `FindingGenerator` | Top-level class |
| `generate_findings(theme, evidence_bundles, max_findings_per_section)` | Per-theme generation |
| `_generate_consensus_finding(bundle)` | Consensus template |
| `_generate_contradiction_finding(bundle)` | Contradiction template |
| `_generate_gap_finding(bundle)` | Gap template (5 subtypes) |
| `_generate_method_finding(theme, graph)` | Method template |
| `_generate_dataset_finding(theme, graph)` | Dataset template |
| `_generate_relation_finding(entity_a, entity_b, edge)` | Relation template |
| `_compute_finding_confidence(finding_type, data)` | Per-type confidence formula |

### Finding templates (6 types)
| Type | Source | Confidence Formula |
|---|---|---|
| consensus | ConsensusEngine | `consensus_confidence` |
| contradiction | ContradictionEngine | `aggregate_confidence` |
| gap | ResearchGapEngine | Per gap type formulas (section 9.1) |
| method | Graph entity clusters | `max(entity_edges.confidence)` |
| dataset | Graph entity clusters | `mean(entity_edges.confidence)` |
| relation | Graph edges | `edge.confidence` |

### Dependencies
- Phase 1 (models)
- Phase 2 (themes)
- Phase 3 (evidence bundles)
- M3 `CorpusGraphResult` (for method/dataset/relation findings)

### Tests
- `tests/test_finding_generator.py`
  - All 6 finding types produce valid ReviewFinding objects
  - Template slot filling: missing slot → `"[unknown]"` placeholder
  - Finding ID determinism: CRC32 matches across runs
  - Max findings per section limit enforced
  - Finding confidence computation matches formula
  - No evidence → empty finding list (not crash)
  - Finding ID collision → suffix appended

### Acceptance criteria
- Produces all 6 finding types with valid templates
- Every finding has confidence in [0.0, 1.0]
- Finding IDs deterministic and unique
- Template placeholders for missing slots (no KeyError)

---

## Phase 5: Section Builder (2 days)

### Files
- `src/researchmind/synthesis/section_builder.py`

### Components
| Component | Description |
|---|---|
| `SectionBuilder` | Top-level class |
| `build_sections(review_type, findings_by_type, corpus_metadata, max_findings)` | Per-review-type assembly |
| `_get_section_requirements(review_type)` | Lookup mandatory/optional |
| `_build_section(section_type, findings, meta)` | Single section construction |
| `_compose_summary(section_type, findings, meta)` | Summary paragraph |
| `_compose_paragraphs(findings)` | One paragraph per finding |
| `_compute_section_confidence(findings)` | `min(finding.confidence)` |
| `_compose_abstract(sections, doc_count, title)` | Full abstract |
| `_build_bibliography(sections, corpus)` | Cited document list |

### Section types (10)
Mandatory and optional per ReviewType (defined in `_SECTION_REQUIREMENTS`):
- abstract, introduction, methods_landscape, datasets, consensus, contradictions, comparative, research_gaps, future_work, conclusion

### Dependencies
- Phase 1 (models)
- Phase 4 (findings)
- M3 corpus manager (document titles for bibliography)

### Tests
- `tests/test_section_builder.py`
  - All 8 ReviewTypes produce correct mandatory sections
  - Missing mandatory section → empty section with warning
  - Section confidence = min(finding confidences)
  - Section word count computed correctly
  - Abstract composed from section summaries
  - Bibliography built from cited document IDs
  - Section order follows `_SECTION_ORDER`
  - Edge case: no findings → "Insufficient evidence" placeholder

### Acceptance criteria
- All 8 ReviewTypes produce valid section lists
- Mandatory sections always present (possibly empty with placeholder)
- Section confidence = min of finding confidences
- Abstract composes without error on empty corpus

---

## Phase 6: Traceability Verifier (1 day)

### Files
- `src/researchmind/synthesis/traceability.py`

### Components
| Component | Description |
|---|---|
| `TraceabilityVerifier` | Top-level class (adapted from M5 pattern) |
| `verify_review(review, corpus, chunk_index)` | Full review verification |
| `_verify_finding(finding, corpus, chunk_index)` | Single finding check |
| `_resolve_evidence(evidence_id, evidence_index)` | Evidence lookup |
| `_resolve_chunk(trace_id, document)` | Chunk resolution |
| `_apply_downgrade(finding, failure_count)` | Confidence × (0.9^failures) |
| `_apply_no_evidence_placeholder(section)` | "Insufficient evidence" |

### Traceability chain
```
ReviewFinding
  → AggregatedEvidence.evidence_id
    → AggregatedEvidence.source_document_id
      → RUODocument (exists in corpus)
        → RUOChunk (trace ID resolves)
```

### Dependencies
- Phase 1 (models)
- M3 document store / corpus manager
- M5 `AggregatedEvidence` (trace field)

### Tests
- `tests/test_traceability.py`
  - Intact chain → PASS
  - Missing evidence_id → finding dropped
  - Missing source_document_id → finding dropped
  - Broken trace chain → ×0.8 confidence penalty
  - Unresolvable evidence_id → finding dropped
  - Mass failure (50%+) → review warning
  - Gap items without source_document_id → ACCEPT (by design)
  - Determinism: same review → same traceability verdict

### Acceptance criteria
- Detects all 5 failure conditions
- No false positives for valid evidence chains
- Gap items without document ID accepted (not failure)
- Confidence downgrades match formula

---

## Phase 7: Confidence Computer (1 day)

### Files
- `src/researchmind/synthesis/confidence.py`

### Components
| Component | Description |
|---|---|
| `ConfidenceComputer` | Top-level class |
| `compute_finding_confidence(finding_type, data)` | Per-type formula dispatch |
| `compute_section_confidence(findings)` | `min(finding.confidence)` |
| `compute_review_confidence(sections, mandatory_types, failures)` | `min(mandatory) * (0.9^failures)` |
| `_apply_traceability_downgrade(base, failure_count)` | Post-verification adjustment |

### Confidence formulas
Direct from architecture Section 9 — 10 finding type formulas, section min-aggregation, review min-over-mandatory, traceability exponential downgrade.

### Dependencies
- Phase 1 (models)
- Phase 4 (finding generation) — for formula constants
- Phase 6 (traceability) — for failure count

### Tests
- `tests/test_confidence.py`
  - Each finding type formula with known inputs → known outputs
  - Section confidence = min of findings (empty → 0.0)
  - Review confidence = min of mandatory sections
  - Traceability downgrade: `C * (0.9^failures)`
  - All outputs clamped to [0.0, 1.0]
  - Determinism: same inputs → same outputs

### Acceptance criteria
- All 10 confidence formulas produce correct values
- Clamping: inputs outside [0,1] are clamped, not raised
- Empty sections → confidence 0.0
- Traceability downgrade matches architecture spec

---

## Phase 8: Orchestrator (2 days)

### Files
- `src/researchmind/synthesis/orchestrator.py`

### Components
| Component | Description |
|---|---|
| `ReviewOrchestrator` | Top-level pipeline orchestrator |
| `generate(request)` | Full 8-stage pipeline |
| `_select_corpus(request, corpus_manager)` | Stage 1 |
| `_collect_evidence(request, corpus, graph, engines)` | Stage 2 |
| `_detect_themes(request, graph)` | Stage 3 |
| `_group_evidence(themes, evidence_bundles)` | Stage 4 |
| `_generate_findings(themes, grouped_evidence)` | Stage 5 |
| `_build_sections(review_type, findings_by_type, meta)` | Stage 6 |
| `_verify_traceability(sections, corpus)` | Stage 7 |
| `_assemble_review(request, sections, failures)` | Stage 8 |

### Pipeline stages
| Stage | Component | Error Handling |
|---|---|---|
| 1. Corpus Selection | `EvidenceCollector`  | Empty corpus → error result |
| 2. Evidence Collection | `EvidenceCollector` | Partial → warnings |
| 3. Theme Detection | `ThemeDetector` | Sparse → few themes |
| 4. Evidence Grouping | Internal (dict groupby) | Unmatched → dropped |
| 5. Finding Generation | `FindingGenerator` | No evidence → empty section |
| 6. Section Construction | `SectionBuilder` | Missing mandatory → error |
| 7. Traceability Verification | `TraceabilityVerifier` | Broken → downgrade/drop |
| 8. Final Assembly | Internal | Partial → warnings |

### Dependencies
- Phases 1–7 (all prior phases)
- M3 `CorpusManager`, `CorpusGraphResult`
- M4 engines (ConsensusEngine, ContradictionEngine, ResearchGapEngine, MultiHopReasoner)

### Tests
- `tests/test_orchestrator.py`
  - Full pipeline on 8-paper corpus: all 8 ReviewTypes
  - Empty corpus → error ReviewResult
  - Single document → document summary (not crash)
  - All M4 engines unavailable → empty sections with warnings
  - Determinism: identical request → identical ReviewResult
  - Error capture: exceptions → ReviewResult.errors, not raise
  - Pipeline timing: completes within 120s on 8-paper corpus

### Acceptance criteria
- `generate(ReviewRequest)` returns `ReviewResult` (never raises)
- All 8 ReviewTypes produce valid output
- Every finding traceable to a source document
- Determinism: identical inputs → identical output

---

## Phase 9: Tests + Evaluation (3 days)

### Test files
| File | Tests | Phase Coverage |
|---|---|---|
| `tests/test_synthesis_models.py` | 30+ | Phase 1 |
| `tests/test_theme_detector.py` | 25+ | Phase 2 |
| `tests/test_evidence_collector.py` | 25+ | Phase 3 |
| `tests/test_finding_generator.py` | 35+ | Phase 4 |
| `tests/test_section_builder.py` | 30+ | Phase 5 |
| `tests/test_traceability.py` | 20+ | Phase 6 |
| `tests/test_confidence.py` | 20+ | Phase 7 |
| `tests/test_orchestrator.py` | 15+ | Phase 8 |

### Evaluation artifacts
| Artifact | Content |
|---|---|
| `audit/run_m6_eval.py` | Automated evaluation script |
| `eval_output/module6_evaluation.md` | Human-readable report |
| `eval_output/module6_metrics.json` | Machine-readable metrics |

### Evaluation dimensions
| Dimension | Target |
|---|---|
| Section completeness | 100% mandatory sections present |
| Finding traceability | ≥ 95% |
| Determinism | 100% |
| Confidence bounds | 0 violations |
| No fabrication | 0 untraceable statements |
| All 8 ReviewTypes | Valid output |
| Test coverage | ≥ 80% |

### Acceptance gates
| Gate | Criteria |
|---|---|
| GATE 1: Determinism | 100% identical on repeat |
| GATE 2: Traceability | ≥ 95% |
| GATE 3: Confidence bounds | 0 violations |
| GATE 4: Section completeness | All mandatory sections present |
| GATE 5: No fabrication | 0 untraceable statements |
| GATE 6: Coverage | ≥ 80% |

---

## Dependency Graph

```
Phase 0 (Scaffolding)
  └── Phase 1 (Models)
        ├── Phase 2 (Theme Detector)
        ├── Phase 3 (Evidence Collector)
        ├── Phase 6 (Traceability Verifier)
        └── Phase 7 (Confidence Computer)
Phase 2 ──┐
          ├── Phase 4 (Finding Generator) ──┐
Phase 3 ──┘                                │
                                            ├── Phase 5 (Section Builder)
Phase 4 ───────────────────────────────────┘
                                            ├── Phase 8 (Orchestrator)
Phase 5 ───────────────────────────────────┘
Phase 6 ───────────────────────────────────┘
Phase 7 ───────────────────────────────────┘
                                              └── Phase 9 (Tests + Evaluation)
```

---

## Implementation Order

| Phase | Days | Parallelizable | Dependencies Met After |
|---|---|---|---|
| Phase 0: Scaffolding | 0.5 | — | — |
| Phase 1: Models | 1 | — | Phase 0 |
| Phase 2: Theme Detector | 2 | Yes (w/ Phase 3) | Phase 1 |
| Phase 3: Evidence Collector | 2 | Yes (w/ Phase 2) | Phase 1 |
| Phase 4: Finding Generator | 3 | No | Phases 2, 3 |
| Phase 5: Section Builder | 2 | No | Phase 4 |
| Phase 6: Traceability Verifier | 1 | Yes (w/ Phase 7) | Phase 1 |
| Phase 7: Confidence Computer | 1 | Yes (w/ Phase 6) | Phase 1 |
| Phase 8: Orchestrator | 2 | No | Phases 5, 6, 7 |
| Phase 9: Tests + Evaluation | 3 | No | Phase 8 |

**Total: 17 days**
**Parallelizable: Phases 2+3 (2 days), Phases 6+7 (1 day)**
**Calendar minimum: 14 days** (with full parallelism)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| M4 engine API mismatch at integration | Medium | High | Verify engine interfaces before Phase 3; add adapter layer if needed |
| 8-paper corpus too small for meaningful themes | Medium | Medium | Single "Uncategorized" theme fallback; test on larger corpus after implementation |
| CRC32 ID collisions in large reviews | Low | Medium | Collision detection + suffix append in ID generation |
| Traceability verification slow on large reviews | Low | Low | Chunk index preloading; batch verification |
| Abstract composition empty (no sections) | Low | Low | Fallback to review-type-based default |
