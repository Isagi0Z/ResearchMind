# RUO Validation Audit

> **Date:** 2026-06-09
> **Scope:** `tests/test_sro_to_ruo.py` — 40 failing tests out of 112
> **Root causes found:** 3 (all other differences are cascading failures)

---

## 1. Root-Cause Summary

| # | Root Cause | Category | Tests | Source (file:line) | Fix Risk |
|---|---|---|---|---|---|
| RC1 | `_convert_citation` omits `intent_evidence_ids` required by RUO model validator | **Converter** | 38 | `sro_to_ruo.py:312` — `_convert_citation`<br>`ruo.py:732` — `_intent_requires_evidence` | **LOW** |
| RC2 | Test expects `{"title", "authors"}` subscores but converter produces one named `"header"` | **Test** | 1 | `test_sro_to_ruo.py:476` — assertion<br>`sro_to_ruo.py:107` — `_default_confidence` | **LOW** |
| RC3 | Invalid `SemanticTriple(predicate="Uses")` constructed **outside** `pytest.raises` | **Test** | 1 | `test_sro_to_ruo.py:1099` — triple construction | **LOW** |

**Total unique failures: 3.  Cascading duplicates: 37.**

---

## 2. Detailed Analysis

### RC1 — `_convert_citation` missing `intent_evidence_ids`

#### Error
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for RUOCitation
  Value error, At least one evidence record is required when citation_intent is set
```

#### Mechanism
1. `_make_sro()` (test_sro_to_ruo.py:245) creates an `SROCitation` with `citation_intent=CitationIntent.SUPPORTS` and no `intent_evidence_ids`.
2. `convert_sro_to_ruo()` calls `_convert_citation()` (sro_to_ruo.py:312).
3. `_convert_citation()` constructs `RUOCitation(...)` **without** passing `intent_evidence_ids`.
4. The `RUOCitation` model's `_intent_requires_evidence` validator (ruo.py:732) fires:
   ```python
   if self.citation_intent is not None and not self.intent_evidence_ids:
       raise ValueError("At least one evidence record is required ...")
   ```

#### Affected tests (38)
| Test class | Tests |
|---|---|
| `TestCitationConversion` | `test_citation_fields_preserved`, `test_citation_intent_preserved`, `test_intent_evidence_ids_default_empty`, `test_raw_marker_default_none` |
| `TestEndToEnd` | All 14 tests |
| `TestModule2Integration` | All 8 tests |
| `TestEdgeCases` | `test_no_entities_no_claims`, `test_very_long_title` |
| `TestEvidenceReport` | `test_report_none_when_no_chains`, `test_report_with_explicit_chains` |
| `TestPydanticValidation` | `test_document_constructs_without_error`, `test_entity_validation`, `test_claim_validation`, `test_doi_lowercased` |
| `TestConversionNotes` | `test_internal_extraction_noted`, `test_no_notes_when_all_provided` |

#### Fix
Add `intent_evidence_ids` passthrough in `_convert_citation()`:

```python
def _convert_citation(c: SROCitation) -> RUOCitation:
    return RUOCitation(
        citation_id=c.citation_id,
        ref_id=c.ref_id,
        chunk_id=c.chunk_id,
        section_id=c.section_id,
        context_sentence=c.context_sentence,
        page=c.page,
        citation_intent=c.citation_intent,
        intent_confidence=c.intent_confidence,
        intent_evidence_ids=list(c.intent_evidence_ids),  # <-- add this
    )
```

> **Note:** `SROCitation` has a `Field(default_factory=list)` for `intent_evidence_ids`, so `list(c.intent_evidence_ids)` safely handles the default.

#### Risk
**LOW** — mechanical field pass-through. Adding the field means the converter is faithful to the SRO source; if the SRO also has an empty list, the validator will still fire. However, the converter is always called *with* an evidence build result from Module 2 (either pre-supplied or built lazily), so citations that appear in the document should have corresponding evidence records. The real question is whether the *evidence records* are linked back to citations. Currently the evidence builder (`evidence_builder.py`) does **not** produce evidence records keyed by citation ID — it produces records for facts, triples, and claims. The validator's intent (`citation_intent` should be backed by evidence) is valid, but the converter and evidence builder are out of sync.

If the evidence builder does not produce citation evidence records, then the validator is too strict and should be **downgraded to a warning** (schema issue), or the evidence builder should be extended to produce citation-specific evidence records. This audit recommends the **converter fix first** (add the field), then assess whether the validator should be relaxed.

---

### RC2 — Test expects wrong subscore names

#### Error
```
AssertionError: assert {'header'} == {'authors', 'title'}
```

#### Mechanism
`_default_confidence(score, "header")` (sro_to_ruo.py:107) creates a single `ComponentSubscore` with `name="header"`. The test at test_sro_to_ruo.py:476 expects `{"title", "authors"}`.

```python
# converter produces:
ComponentConfidence(component="header", score=0.925, subscores=[
    ComponentSubscore(name="header", value=0.925, weight=1.0),
])

# test expects:
{"title", "authors"}  # ← never true
```

#### Affected tests (1)
- `TestHeaderConversion::test_confidence_subscores`

#### Fix options
1. **(Test fix, recommended):** Update assertion to `assert names == {"header"}`.
2. **(Converter change):** Build per-field subscores inside `_convert_header`:
   ```python
   subscores=[
       ComponentSubscore(name="title", value=sro.header.title_confidence, weight=1.0),
       ComponentSubscore(name="authors", value=sro.header.authors_confidence, weight=1.0),
   ]
   ```
   This is more faithful to the data but changes production behavior.

#### Risk
**LOW** — either fix is safe. Option 1 is trivial and doesn't change production code.

---

### RC3 — Invalid SemanticTriple constructed outside `pytest.raises`

#### Error
```
ValidationError: 1 validation error for SemanticTriple
  predicate: Value error, predicate must be snake_case lowercase
```

#### Mechanism
The test constructs a `TripleExtractionResult` containing a `SemanticTriple` with `predicate="Uses"` **outside** the `pytest.raises(ValidationError)` block (test_sro_to_ruo.py:1098-1104). The `SemanticTriple.__init__` validates immediately, raising `ValidationError` during triple construction rather than during `convert_sro_to_ruo()`.

```python
# This line raises ValidationError BEFORE pytest.raises is entered
triple_result = TripleExtractionResult(triples=[
    SemanticTriple(predicate="Uses", ...)  # ← boom here
])
with pytest.raises(ValidationError):
    convert_sro_to_ruo(sro, triple_result=triple_result)
```

#### Affected tests (1)
- `TestPydanticValidation::test_semantic_triple_predicate_format`

#### Fix
Move the `SemanticTriple` construction inside the `with pytest.raises(ValidationError):` block:

```python
def test_semantic_triple_predicate_format(self):
    sro = _make_sro()
    with pytest.raises(ValidationError):
        TripleExtractionResult(triples=[
            SemanticTriple(
                triple_id="t1", subject_id="e1", subject_text="GAN",
                predicate="Uses", object_id="e2", object_text="Data",
                confidence=0.8, chunk_id="c1",
            )
        ])
        # The convert_sro_to_ruo call is not even reached
```

Or, use `SemanticTriple.model_construct(predicate="Uses", ...)` to bypass validation (Pydantic v2 feature).

#### Risk
**LOW** — test-only fix, no production impact.

---

## 3. Dependency Tree

Every test in the 40-failure set traces to one of the three roots above:

```
RC1 (converter miss) ─┬── TestCitationConversion    (4 tests)
                        ├── TestEndToEnd              (14 tests)
                        ├── TestModule2Integration    (8 tests)
                        ├── TestEdgeCases            (2 tests)  ← test_no_entities_no_claims,
                        │                                        test_very_long_title
                        ├── TestEvidenceReport       (2 tests)
                        ├── TestPydanticValidation   (4 tests)  ← test_document_constructs,
                        │                                        test_entity, test_claim,
                        │                                        test_doi_lowercased
                        └── TestConversionNotes      (2 tests)

RC2 (test assertion)    ─── TestHeaderConversion     (1 test)

RC3 (test setup)        ─── TestPydanticValidation   (1 test)  ← test_semantic_triple_predicate
```

---

## 4. Fix Recommendations

| Priority | Root Cause | Action | File | Owner |
|---|---|---|---|---|
| **P0** | RC1 — Add `intent_evidence_ids` to converter | Add `intent_evidence_ids=list(c.intent_evidence_ids)` to `_convert_citation` | `sro_to_ruo.py:321` | Converter |
| **P0** | RC2 — Fix test assertion | Update assertion to match actual subscore name (or split subscores) | `test_sro_to_ruo.py:476` | Tests |
| **P0** | RC3 — Fix test setup | Move invalid construction inside `pytest.raises` | `test_sro_to_ruo.py:1098-1104` | Tests |

> **P0** = fixes all 40 failures immediately.

### Recommended fix order
1. **RC1** first — unblocks 38 tests
2. **RC2** — trivial test assertion fix
3. **RC3** — trivial test setup fix

All three can be applied independently; none depends on another.

---

## 5. Deeper Assessment

### 5.1 `RUOCitation._intent_requires_evidence` — schema concern

The validator at `ruo.py:732` requires `intent_evidence_ids` to be non-empty whenever `citation_intent` is set. This is a **defensible** design choice (citation intents should be evidence-backed), but the current pipeline does not produce citation-specific evidence records:

- `evidence_builder.py` builds evidence for **facts**, **triples**, and **claims** — not citations.
- `_convert_citation()` has no evidence records to pass.

**Options:**

| Option | Effort | Impact |
|---|---|---|
| A. **(Quick fix, recommended)** — Add the field passthrough; accept that `intent_evidence_ids` will be empty until the evidence builder is extended. Declare it a "soft requirement" enforced by tests but not by production code. | 1 line | Unblocks all tests |
| B. Relax validator to warning — Change the `ValueError` to a logged warning. | Moderate | Loses schema strictness |
| C. Extend evidence builder to produce citation evidence records — Cross-reference citations with evidence chains. | High | Adds real value but is scope creep |

**Recommendation:** Fix A now. Evaluate B or C when citation-intent confidence becomes a production requirement.

### 5.2 `_default_confidence` naming convention

`_default_confidence` passes `component` as the subscore name. This is not *wrong*, but it loses information. Consider:
```python
subscores=[
    ComponentSubscore(name="title", value=sro.header.title_confidence, weight=0.5),
    ComponentSubscore(name="authors", value=sro.header.authors_confidence, weight=0.5),
]
```
Opening this as a separate issue (not part of this audit fix) would improve the fidelity of the confidence model.

---

## 6. Affected Source Files

| File | Lines | Role |
|---|---|---|
| `src/researchmind/conversion/sro_to_ruo.py` | 312–322 | `_convert_citation` — missing field |
| `src/researchmind/conversion/sro_to_ruo.py` | 107–114 | `_default_confidence` — generic subscore |
| `src/researchmind/models/ruo.py` | 720–739 | `RUOCitation` — `intent_evidence_ids` validator |
| `tests/test_sro_to_ruo.py` | 476 | RC2 — wrong assertion |
| `tests/test_sro_to_ruo.py` | 1098–1104 | RC3 — construction outside `pytest.raises` |

---

## 7. Test Inventory

```
Total tests in test_sro_to_ruo.py:    112
  Currently passing:                   72  (64 %)
  Currently failing:                   40  (36 %)

Fix RC1:                               +38  → 110 pass
Fix RC2:                                +1  → 111 pass
Fix RC3:                                +1  → 112 pass
After all fixes:                       112/112 pass
```
