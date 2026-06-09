# SRO → RUO Field Mapping

**Version:** 1.0.0  
**RUO Schema:** 2.1.0  
**Converter:** `src/researchmind/conversion/sro_to_ruo.py`

---

## 1. Overview

This document describes every field-level transformation from the
**Structured Research Object (SRO)** — the output of the Module 1
ingestion pipeline — into the **ResearchMind Unified Object (RUO)**,
the unified representation used by all downstream modules.

The converter also integrates **Module 2 enrichment outputs**:
`ExtractedFact[]`, `SemanticTriple[]`, `EvidenceRecord[]`,
`EvidenceChain[]`, and `ProvenanceRecord[]`.

---

## 2. Conventions

| Notation | Meaning |
|----------|---------|
| `→`      | Direct copy (same name, same type) |
| `↦`      | Transformed (renamed, reshaped, or computed) |
| `✗`      | No SRO equivalent; default/empty |
| `🆕`     | New field introduced by the converter |
| `⚠`      | Information loss or truncation |

All generated RUO documents pass **Pydantic validation** with no errors.

---

## 3. Top-Level Mapping

```
SRO                                        RUO
├── meta: SROMeta                ──────→  ├── meta: RUOMeta
├── header: SROHeader            ──────→  ├── header: RUOHeader
├── abstract: SROAbstract        ──────→  ├── abstract: RUOAbstract
├── body: SROBody                ──────→  ├── body: RUOBody
├── references: SROReference[]   ──────→  ├── references: RUOReference[]
├── citations: SROCitation[]     ──────→  ├── citations: RUOCitation[]
├── entities: SROEntity[]        ──────→  ├── entities: RUOEntity[]
├── candidate_claims: SROCandidateClaim[] → ├── claims: RUOClaim[]
├── quality: SROQuality          ──────→  ├── quality: RUOQuality
✗                                        ├── triples: SemanticTriple[]
✗                                        ├── provenance: ProvenanceRecord[]
✗                                        ├── annotations: Annotation[]
🆕                                       ├── schema_version: str
🆕                                       ├── lineage: list[str]
```

---

## 4. Field-by-Field Mappings

### 4.1 Meta & Source File

#### `SROSourceFile` → `RUOSourceFile` (1:1, no loss)

| SRO field         | RUO field         | Rule     |
|-------------------|-------------------|----------|
| `filename`        | `filename`        | →        |
| `sha256`          | `sha256`          | →        |
| `page_count`      | `page_count`      | →        |
| `has_text_layer`  | `has_text_layer`  | →        |
| `is_scanned`      | `is_scanned`      | →        |
| `size_bytes`      | `size_bytes`      | →        |

#### `SROMeta` → `RUOMeta`

| SRO field              | RUO field            | Rule     | Notes |
|------------------------|----------------------|----------|-------|
| `sro_id`               | `ruo_id`             | ↦        | Prefixed: `ruo_{sro_id}` |
| `sro_id`               | `sro_id`             | →        | Preserved for traceability |
| ✗                      | `corpus_ids`         | 🆕       | Empty default `[]` |
| `schema_version`       | `schema_version`     | ↦        | Overwritten with `RUO_SCHEMA_VERSION` |
| `created_at`           | `created_at`         | 🆕       | Set to conversion timestamp |
| `updated_at`           | `updated_at`         | 🆕       | Set to conversion timestamp |
| `pipeline_version`     | `pipeline_version`   | →        | |
| `source_file`          | `source_file`        | ↦        | See §4.1 above |
| `extraction_route`     | `extraction_route`   | →        | Same enum |
| ✗                      | `document_type`      | ↦        | Copied from `header.document_type` |
| ✗                      | `language`           | ↦        | Copied from `header.language` (default `"en"`) |
| ✗                      | `arxiv_categories`   | 🆕       | Empty default `[]` ⚠ |
| ✗                      | `research_fields`    | 🆕       | Empty default `[]` ⚠ |
| `processing_time_ms`   | `processing_time_ms` | →        | |
| ✗                      | `pipeline_stages`    | 🆕       | `[StageStatus.SUCCESS]` |

---

### 4.2 Header & Authors

#### `SROAuthor` → `RUOAuthor` (1:1, no loss)

| SRO field          | RUO field          | Rule |
|--------------------|--------------------|------|
| `full_name`        | `full_name`        | →    |
| `given_name`       | `given_name`       | →    |
| `surname`          | `surname`          | →    |
| `affiliations`     | `affiliations`     | →    |
| `email`            | `email`            | →    |
| `orcid`            | `orcid`            | →    |
| `is_corresponding` | `is_corresponding` | →    |
| ✗                  | `evidence_ids`     | 🆕   | Empty default `[]` |

#### `SROHeader` → `RUOHeader`

| SRO field                  | RUO field            | Rule     | Notes |
|----------------------------|----------------------|----------|-------|
| `title`                    | `title`              | →        | |
| `authors`                  | `authors`            | ↦        | See §4.2 above |
| `document_type`            | `document_type`      | →        | |
| `doi`                      | `doi`                | →        | |
| `arxiv_id`                 | `arxiv_id`           | →        | |
| `pmid`                     | `pmid`               | →        | |
| `publication_date`         | `publication_date`   | →        | |
| `venue`                    | `venue`              | →        | |
| `venue_type`               | `venue_type`         | →        | |
| `volume`                   | `volume`             | →        | |
| `issue`                    | `issue`              | →        | |
| `pages`                    | `pages`              | →        | |
| `keywords`                 | `keywords`           | →        | |
| `title_confidence`         | `confidence`         | ↦        | **Transformed** — see below |
| `authors_confidence`       | `confidence`         | ↦        | Combined into `ComponentConfidence` |
| ✗                          | `evidence_ids`       | 🆕       | Empty default `[]` |

**Confidence construction:**
```python
ComponentConfidence(
    component="header",
    score=(title_confidence + authors_confidence) / 2,
    subscores=[
        ComponentSubscore(name="title", value=title_confidence, weight=0.5),
        ComponentSubscore(name="authors", value=authors_confidence, weight=0.5),
    ],
)
```
⚠ Individual `title_confidence` and `authors_confidence` are preserved
as subscores but the top-level `score` is their average.

---

### 4.3 Abstract

#### `SROAbstract` → `RUOAbstract`

| SRO field           | RUO field            | Rule     | Notes |
|---------------------|----------------------|----------|-------|
| `raw_text`          | `raw_text`           | →        | |
| `is_structured`     | `is_structured`      | →        | |
| `structured`        | `structured`         | ↦        | 1:1 sub-field copy (background, objective, methods, results, conclusion) |
| `confidence`        | `confidence`         | ↦        | Wrapped in `ComponentConfidence(component="abstract", score=confidence, subscores=[...])` |
| ✗                   | `evidence_ids`       | 🆕       | Empty default `[]` |

---

### 4.4 Body

#### `SROSection` → `RUOSection`

| SRO field              | RUO field            | Rule     | Notes |
|------------------------|----------------------|----------|-------|
| `section_id`           | `section_id`         | →        | |
| `parent_section_id`    | `parent_section_id`  | →        | |
| `level`                | `level`              | →        | |
| `position`             | `position`           | →        | |
| `original_header`      | `original_header`    | →        | |
| `canonical_label`      | `canonical_label`    | →        | |
| `label_confidence`     | `label_confidence`   | →        | |
| `page_start`           | `page_start`         | →        | |
| `page_end`             | `page_end`           | →        | |
| `content`              | `content`            | →        | |
| ✗                      | `extraction_method`  | 🆕       | Set to `ExtractionMethod.GROBID` (fixed default) |
| ✗                      | `evidence_ids`       | 🆕       | Empty default `[]` |

#### `SROChunk` → `RUOChunk`

| SRO field                | RUO field              | Rule     | Notes |
|--------------------------|------------------------|----------|-------|
| `chunk_id`               | `chunk_id`             | →        | |
| `text`                   | `text`                 | →        | |
| `word_count`             | `word_count`           | →        | |
| `section_id`             | `section_id`           | →        | |
| `canonical_label`        | `canonical_label`      | →        | |
| `page_start`             | `page_start`           | →        | |
| `page_end`               | `page_end`             | →        | |
| `paragraph_index`        | `paragraph_index`      | →        | |
| `reading_order`          | `reading_order`        | →        | |
| `extraction_method`      | `extraction_method`    | →        | |
| `extraction_confidence`  | `extraction_confidence`| →        | |
| `entity_ids`             | `entity_ids`           | →        | |
| `claim_ids`              | `claim_ids`            | →        | |
| ✗                        | `evidence_ids`         | 🆕       | Empty default `[]` |
| ✗                        | `embedding`            | 🆕       | `None` (not computed) ⚠ |
| ✗                        | `embedding_model`      | 🆕       | `None` (not computed) ⚠ |

#### `SROTable` → `RUOTable`

| SRO field                | RUO field            | Rule     | Notes |
|--------------------------|----------------------|----------|-------|
| `table_id`               | `table_id`           | →        | |
| `caption`                | `caption`            | →        | |
| `section_id`             | `section_id`         | →        | |
| `page`                   | `page`               | →        | |
| `raw_content`            | `raw_content`        | →        | |
| `extraction_confidence`  | `confidence`         | →        | |
| ✗                        | `evidence_ids`       | 🆕       | Empty default `[]` |

#### `SROFigure` → `RUOFigure`

| SRO field          | RUO field         | Rule |
|--------------------|-------------------|------|
| `figure_id`        | `figure_id`       | →    |
| `caption`          | `caption`         | →    |
| `section_id`       | `section_id`      | →    |
| `page`             | `page`            | →    |
| `image_path`       | `image_path`      | →    |
| ✗                  | `evidence_ids`    | 🆕   |

---

### 4.5 References

#### `SROReference` → `RUOReference`

| SRO field              | RUO field              | Rule     | Notes |
|------------------------|------------------------|----------|-------|
| `ref_id`               | `ref_id`               | →        | |
| `raw_text`             | `raw_text`             | →        | |
| `resolution_status`    | `resolution_status`    | →        | |
| `resolution_source`    | `resolution_source`    | →        | |
| `ref_confidence`       | `ref_confidence`       | →        | |
| `title`                | `title`                | →        | |
| `authors`              | `authors`              | →        | |
| `year`                 | `year`                 | →        | |
| `venue`                | `venue`                | →        | |
| `doi`                  | `doi`                  | →        | |
| `url`                  | `url`                  | →        | |
| ✗                      | `arxiv_id`             | 🆕       | `None` ⚠ |
| ✗                      | `pmid`                 | 🆕       | `None` ⚠ |
| ✗                      | `evidence_ids`         | 🆕       | Empty default `[]` |
| ✗                      | `target_ruo_id`        | 🆕       | `None` ⚠ |

---

### 4.6 Citations

#### `SROCitation` → `RUOCitation`

| SRO field              | RUO field              | Rule     | Notes |
|------------------------|------------------------|----------|-------|
| `citation_id`          | `citation_id`          | →        | |
| `ref_id`               | `ref_id`               | →        | |
| `chunk_id`             | `chunk_id`             | →        | |
| `section_id`           | `section_id`           | →        | |
| `context_sentence`     | `context_sentence`     | →        | |
| `page`                 | `page`                 | →        | |
| `citation_intent`      | `citation_intent`      | →        | |
| `intent_confidence`    | `intent_confidence`    | →        | |
| ✗                      | `intent_evidence_ids`  | 🆕       | Empty default `[]` ⚠ |
| ✗                      | `raw_marker`           | 🆕       | `None` ⚠ |

---

### 4.7 Entities

#### `SROEntity` → `RUOEntity`

| SRO field          | RUO field            | Rule     | Notes |
|--------------------|----------------------|----------|-------|
| `entity_id`        | `entity_id`          | →        | |
| `text`             | `text`               | →        | |
| `label`            | `label`              | →        | |
| `chunk_id`         | `chunk_id`           | →        | |
| `sentence`         | `sentence`           | →        | |
| `confidence`       | `confidence`         | →        | |
| `source`           | `source`             | →        | |
| ✗                  | `normalized_id`      | 🆕       | `None` ⚠ |
| ✗                  | `normalized_label`   | 🆕       | `None` ⚠ |
| ✗                  | `kb_source`          | 🆕       | `None` ⚠ |
| ✗                  | `evidence_ids`       | 🆕       | Empty default `[]` |
| ✗                  | `embedding`          | 🆕       | `None` ⚠ |
| ✗                  | `embedding_model`    | 🆕       | `None` ⚠ |

---

### 4.8 Claims

#### `SROCandidateClaim` → `RUOClaim`

| SRO field              | RUO field              | Rule     | Notes |
|------------------------|------------------------|----------|-------|
| `claim_id`             | `claim_id`             | →        | |
| `sentence`             | `sentence`             | →        | |
| `chunk_id`             | `chunk_id`             | →        | |
| `section_id`           | `section_id`           | →        | |
| `canonical_label`      | `canonical_label`      | →        | |
| `claim_type`           | `claim_type`           | →        | |
| `matched_patterns`     | `matched_patterns`     | →        | |
| `confidence`           | `confidence`           | →        | |
| `page`                 | `page`                 | →        | |
| ✗                      | `evidence_chain_id`    | 🆕       | Linked from `EvidenceChain.target_id` or generated as `ec_{claim_id}` |
| ✗                      | `is_contradicted`      | 🆕       | `False` ⚠ |
| ✗                      | `contradiction_detected_at` | 🆕    | `None` ⚠ |
| ✗                      | `is_supported_by`      | 🆕       | Empty `[]` ⚠ |
| ✗                      | `is_replicated`        | 🆕       | `None` ⚠ |
| ✗                      | `normalized_statement` | 🆕       | `None` ⚠ |
| ✗                      | `embedding`            | 🆕       | `None` ⚠ |
| ✗                      | `embedding_model`      | 🆕       | `None` ⚠ |

---

### 4.9 Semantic Triples

`SemanticTriple` objects from the triple extractor are **passed through**
with no transformation. They are the same Pydantic model in both systems.

---

### 4.10 Evidence, Chains & Provenance

All evidence-layer objects (`EvidenceRecord`, `EvidenceChain`,
`ProvenanceRecord`, `EvidenceCoverage`) are **passed through**
with no transformation from the `EvidenceBuildResult`.

---

### 4.11 Quality

#### `SROQuality` → `RUOQuality`

| SRO field                    | RUO field                | Rule     | Notes |
|------------------------------|--------------------------|----------|-------|
| `field_scores.title`         | `confidence.components`  | ↦        | Wrapped as `ComponentConfidence` subscore |
| `field_scores.authors`       | `confidence.components`  | ↦        | Same |
| `field_scores.abstract`      | `confidence.components`  | ↦        | Same |
| `field_scores.sections`      | `confidence.components`  | ↦        | Same |
| `field_scores.references`    | `confidence.components`  | ↦        | Same |
| `field_scores.citations`     | `confidence.components`  | ↦        | Same |
| `field_scores.entities`      | `confidence.components`  | ↦        | Same |
| `field_scores.claims`        | `confidence.components`  | ↦        | Same |
| `overall_confidence`         | `overall_confidence`     | ↦        | Recalculated as mean of field components |
| ✗                            | `evidence_coverage`      | 🆕       | Passed from `EvidenceBuildResult.coverage` |
| `validation_errors`          | `validation.results`     | ↦        | Mapped to `ValidationResult` with severity=ERROR |
| `validation_warnings`        | `validation.results`     | ↦        | Mapped to `ValidationResult` with severity=WARNING |
| `requires_manual_review`     | `requires_manual_review` | →        | |
| `manual_review_reasons`      | `manual_review_reasons`  | →        | |
| `pipeline_log`               | `pipeline_log`           | →        | |
| `llm_calls`                  | `llm_calls`              | →        | |

**Confidence construction:**
```python
ConfidenceBreakdown(
    components=[
        ComponentConfidence("title", score=field_scores.title, ...),
        ComponentConfidence("authors", score=field_scores.authors, ...),
        # ... one per field
    ],
    overall=mean of all component scores,
    component_weights={name: 1/N for each of N components},
)
```

---

### 4.12 Annotations

`ExtractedFact` objects from the fact extractor are converted to
`Annotation` objects:

| ExtractedFact field  | Annotation field   | Rule |
|----------------------|--------------------|------|
| `fact_id`            | `annotation_id`    | ↦    | Prefixed: `fact_{fact_id}` |
| ✗                    | `annotation_type`  | 🆕   | Fixed: `"automated_flag"` |
| `fact_id`            | `target_id`        | →    | |
| ✗                    | `target_type`      | 🆕   | Fixed: `"entity"` |
| ✗                    | `field`            | 🆕   | Fixed: `"fact_type"` |
| `fact_type.value`    | `suggested_value`  | →    | |
| ✗                    | `author`           | 🆕   | Fixed: `"fact_extractor"` |

---

## 5. Information Loss Register

| # | Field | SRO → RUO | Loss |
|---|-------|-----------|------|
| 1 | `arxiv_categories` | 🆕 default `[]` | No SRO source exists |
| 2 | `research_fields` | 🆕 default `[]` | No SRO source exists |
| 3 | `embedding` + `embedding_model` on chunks, entities, claims | 🆕 `None` | Not computed (requires vector model) |
| 4 | `normalized_id`, `normalized_label`, `kb_source` on entities | 🆕 `None` | No KB linking in current pipeline |
| 5 | `is_contradicted`, `is_supported_by`, `is_replicated` on claims | 🆕 defaults | No contradiction detection yet |
| 6 | `evidence_chain_id` on claims | 🆕 derived | May not correspond to actual chain if missing from evidence result |
| 7 | `extraction_method` on sections | 🆕 `GROBID` fixed | Not stored in SROSection |
| 8 | `title_confidence` + `authors_confidence` | ↦ averaged | Individual scores demoted to subscores |
| 9 | `SROHeader.publication_date_raw` | ✗ dropped | RUO has no equivalent |
| 10 | `SROReference.arxiv_id`, `SROReference.pmid` | 🆕 `None` | SRO reference model lacks these |

---

## 6. Cross-Reference Integrity

| Source ID | Target field | Preserved? |
|-----------|-------------|------------|
| `sro_id` | `meta.ruo_id` (prefixed), `meta.sro_id` | ✅ |
| `section_id` | `section.section_id` | ✅ |
| `chunk_id` | `chunk.chunk_id` | ✅ |
| `entity_id` | `entity.entity_id` | ✅ |
| `claim_id` | `claim.claim_id` | ✅ |
| `ref_id` | `reference.ref_id` | ✅ |
| `citation_id` | `citation.citation_id` | ✅ |
| `triple_id` | `triple.triple_id` | ✅ |
| `evidence_id` | `evidence_record.evidence_id` | ✅ |
| `provenance_id` | `provenance_record.provenance_id` | ✅ |
| `evidence_chain.target_id` | `claim.claim_id` | ✅ |

---

## 7. Schema Validation

Every generated `RUODocument` is validated by Pydantic at construction
time. The converter does **not** disable validation. Known invariants:

- `RUOSection.page_end >= page_start` — guaranteed by SRO model
- `RUOChunk.text` non-empty — guaranteed by SRO model
- `RUOClaim.matched_patterns` non-empty — guaranteed by SRO model
- `ConfidenceBreakdown` weight sum = 1.0 — enforced by converter
- `ConfidenceBreakdown` overall = weighted sum — enforced by converter
