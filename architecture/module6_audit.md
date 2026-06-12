# Module 6 Architecture Audit

**Audit Date:** 2026-06-11
**Auditor:** Automated review against M1–M5 baseline constraints
**Status:** READY WITH FIXES (2 violations, 3 warnings)

---

## Audit Dimensions

### D1: No LLMs, embeddings, or generative models

| Check | Status | Evidence |
|---|---|---|
| Theme detection uses ML? | PASS | Connected components on COMPARES_WITH edges — pure graph algorithm |
| Finding generation uses LLM? | PASS | Template + slot-filling from evidence metadata |
| Any embedding or vector comparison? | PASS | None found |
| Any external API calls? | PASS | None found |

**Verdict: PASS**

---

### D2: Deterministic only — no UUIDs, no random ordering, no timestamps

| Check | Status | Evidence |
|---|---|---|
| Finding IDs use CRC32/sha256? | PASS | Section 6.3: `zlib.crc32` for finding IDs |
| No `uuid` imports in data models? | PASS | No UUID pattern in architecture |
| No `random.*` calls? | PASS | No random usage |
| Timestamps in result models? | **FAILURE** | `ReviewResult.generated_at` uses ISO-8601 timestamp (Section 3.4) |
| Model IDs generated deterministically? | **WARNING** | `bundle_id`, `theme_id`, `section_id` generation not specified |

**Verdict: FAILURE** — must fix `generated_at` and specify deterministic generation for all IDs

---

### D3: Pydantic v2 compatible

| Check | Status | Evidence |
|---|---|---|
| Uses `BaseModel` (not v1)? | PASS | All models use `BaseModel` |
| Uses `field_validator` (not v1 `validator`)? | PASS | `@field_validator` used throughout |
| Uses `Field(default_factory=...)` correctly? | PASS | Yes, e.g., `Field(default_factory=list)` |
| No v1-only patterns? | PASS | None found |

**Verdict: PASS**

---

### D4: Python 3.9 compatible

| Check | Status | Evidence |
|---|---|---|
| StrEnum backport pattern? | PASS | Section 2.1 shows the standard `try/except` + `class StrEnum(str, Enum)` pattern |
| `from __future__ import annotations` for list/dict types? | PASS | Section 2.1 imports it |
| `list[str]` / `dict[str, Any]` type hints? | PASS | Used throughout, valid with `from __future__ import annotations` |
| No match/case statements? | PASS | No switch/match statements |
| No 3.10+ specific features? | PASS | None found |

**Verdict: PASS**

---

### D5: No reflection, no switch statements

| Check | Status | Evidence |
|---|---|---|
| Dispatch via dict maps? | PASS | Section routing, template selection use dict dispatch |
| No `match`/`case`? | PASS | None used |
| No `getattr`/`setattr` for control flow? | PASS | None found |

**Verdict: PASS**

---

### D6: Reuses existing models and engines correctly

| Check | Status | Evidence |
|---|---|---|
| `AggregatedEvidence` reused from M5? | PASS | Section 3.5 explicitly states reuse |
| `CorpusGraphResult` consumed from M3? | PASS | Section 1.4 inputs table |
| M4 engines consumed directly? | PASS | Sections 1.4, 11.3 integration plan |
| `RUODocument`/`RUOClaim` consumed? | PASS | Section 1.4 inputs table |
| No duplicate model definitions? | PASS | All new models unique to M6 |

**Verdict: PASS**

---

### D7: Traceability enforcement

| Check | Status | Evidence |
|---|---|---|
| Traceability contract defined? | PASS | Section 8: 3-hop chain (Finding → Evidence → Chunk → Document) |
| Verification algorithm specified? | PASS | Section 8.2: `verify_review()` |
| Failure handling defined? | PASS | Section 8.3: drop/downgrade per failure type |
| No-evidence policy enforced? | PASS | Section 8.4: "Insufficient evidence" placeholder |

**Verdict: PASS**

---

### D8: Confidence bounds

| Check | Status | Evidence |
|---|---|---|
| All confidence values clamped to [0,1]? | PASS | Section 9.1: "clamped to [0.0, 1.0]" |
| Finding confidence formulas defined? | PASS | Section 9.1 table: 10 finding types with formulas |
| Section confidence = min(findings)? | PASS | Section 9.2 |
| Review confidence = min(mandatory sections)? | PASS | Section 9.3 |
| Traceability downgrade defined? | PASS | Section 9.4: `C * (0.9 ** failure_count)` |

**Verdict: PASS**

---

### D9: Architecture completeness

| Check | Status | Evidence |
|---|---|---|
| All inputs specified? | PASS | Section 1.4: 11 inputs with source, type, usage |
| All outputs specified? | PASS | `ReviewResult` model fully defined |
| All failure modes catalogued? | PASS | Section 10: 31 failure modes across 7 categories |
| Pipeline stages defined? | PASS | Section 4: 8 stages with inputs/outputs/determinism/error modes |
| Integration plan with file structure? | PASS | Section 11.1 |
| Implementation order with phases? | PASS | Section 11.5 |

**Verdict: PASS**

---

## Audit Findings Summary

### VIOLATIONS (must fix before implementation)

| # | Location | Issue | Fix |
|---|---|---|---|
| V1 | Section 3.4 `ReviewResult` | `generated_at: str` (ISO-8601 timestamp) violates determinism constraint | Remove field or make it an empty string default (`""`). Determinism requirement prohibits timestamps. |
| V2 | Section 3.4 `ReviewResult` | `review_id` could be confused with auto-generated; `ReviewResult` has its own `review_id` field separate from `ReviewRequest.review_id` | Clarify that `ReviewResult.review_id` is copied from `ReviewRequest.review_id` (caller-provided). Add validator ensuring non-empty. |

### WARNINGS (document and address)

| # | Location | Issue | Recommendation |
|---|---|---|---|
| W1 | Section 3 models | `bundle_id`/`theme_id`/`section_id` generation not specified | Use `zlib.crc32` (consistent with M5 pattern). E.g., `f"bnd_{crc32(...):012x}"`, `f"thm_{crc32(...):012x}"`, `f"sec_{crc32(...):012x}"` |
| W2 | Section 7.4 `compose_abstract` | Template uses `{topic}` but `ReviewRequest` has `title` not `topic` | Use `ReviewRequest.title` as the topic slot. Add fallback: if title is empty, derive from review_type. |
| W3 | Section 6.1.6 Relation finding | Template uses `{source}` and `{target}` — these could conflict with M4 node terminology | Use `{source_entity}` and `{target_entity}` to avoid ambiguity. Consistent with section 6.1.1–6.1.5 naming. |

### NOTES (informational, no action required)

| # | Location | Note |
|---|---|---|
| N1 | Section 5.4 | `ThemeType` enum defined but not used in any model field — it's for internal classification |
| N2 | Section 4.1 | Pipeline diagram shows `ReviewResult.warnings` and `errors` — these are already in the model |
| N3 | Section 6.2 | `generate_findings` parameter `max_findings` should be `max_findings_per_section` for consistency with `ReviewRequest` |
| N4 | Section 11.2 | Dependency graph doesn't show `ConfidenceComputer` wired to `SectionBuilder` — implied but should be explicit |
| N5 | Section 12.1 | Evaluation dimension "No-fabrication guarantee" — this is enforced by traceability + no-evidence policy |

---

## Verdict: READY WITH FIXES

Module 6 architecture is fundamentally sound. All major design decisions (deterministic pipeline, template-driven generation, weakest-link confidence, traceability contract, no-evidence policy) align with M1–M5 baseline constraints.

### Required fixes (before any code):
1. Remove `generated_at` from `ReviewResult` or make it `""` default
2. Clarify `review_id` flow from request → result
3. Specify deterministic ID generation for all model IDs (bundle_id, theme_id, section_id)
4. Fix abstract template `{topic}` → `{title}` and wire to `ReviewRequest.title`
5. Rename `{source}`/`{target}` → `{source_entity}`/`{target_entity}` in relation finding template

### Recommended before implementation:
- All 5 fixes above applied to architecture document
- Document consistent CRC32 key format across all ID generators
- Verify implementation order phases are still accurate after minor model adjustments
