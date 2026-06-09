# Entity Resolution — Architecture & Design

> **Version:** 1.0  
> **Module:** M3-2  
> **Date:** 2026-06-09  

---

## 1. Overview

Entity resolution (ER) identifies `RUOEntity` references across documents in a `RUOCorpus` that refer to the same real-world concept (method, dataset, metric, person, etc.) and groups them into **clusters** with a single **canonical representation**.

**Deterministic only** — no LLMs, embeddings, vector databases, or external APIs. All matching uses text normalization, alias dictionaries, and token-level similarity via **RapidFuzz**.

---

## 2. Resolution Pipeline

```
Input: List[RUOEntity] (from one or more documents)
   │
   ├── Stage 1: Exact Normalization
   │   - Lowercase, strip, collapse whitespace
   │   - Group by (normalized_text, label)
   │   - Confidence = 1.0
   │
   ├── Stage 2: Alias Dictionary Lookup
   │   - Load aliases from config/entity_aliases.yaml
   │   - Map variant surface forms → canonical text
   │   - Confidence = 0.95
   │
   ├── Stage 3: Token Similarity Clustering
   │   - Token-set similarity via RapidFuzz
   │   - Pairwise comparison within same label group
   │   - Confidence = similarity_score / 100.0
   │
   ├── Stage 4: Entity-Type Protection
   │   - Applied at every stage
   │   - Only same-label merges by default
   │   - Configurable label compatibility matrix
   │
   └── Stage 5: Corpus-Wide Cluster Generation
       - Transitive closure of all pairwise merges
       - Final EntityCluster objects
       - ResolutionResult with statistics
```

### 2.1 Stage 1 — Exact Normalization

**Normalization function:**
1. Strip leading/trailing whitespace
2. Lowercase
3. Collapse internal whitespace sequences to single space
4. Remove common noise: trailing punctuation (`.`, `,`, `;`, `:`)

**Matching rule:** Two entities match exactly if their normalized texts are identical **and** their `EntityLabel` values are compatible (see Stage 4).

**Confidence:** `1.0`

**Edge cases:**
- `"BERT"` and `"bert"` match (case normalization)
- `"Batch Normalization"` and `"batch  normalization"` match (whitespace collapse)
- `"GAN."` and `"GAN"` match (trailing period stripped)
- `"Attention"` and `"attention is all you need"` do NOT match (exact match required)

### 2.2 Stage 2 — Alias Dictionary Lookup

The alias dictionary (`config/entity_aliases.yaml`) maps known variants to canonical forms:

```yaml
aliases:
  - canonical: "batch normalization"
    variants: ["batch norm", "batchnorm"]
    label: method
```

**Matching rule:** For each unresolved entity, check if its normalized text matches any variant in the alias dictionary. If matched:
1. Create a cluster keyed by the canonical text
2. Apply entity-type protection (variant's `EntityLabel` must match the alias entry's label)
3. Set confidence to `0.95`

**Priority:** If multiple alias entries match the same entity text, prefer the longest canonical text (most specific match).

### 2.3 Stage 3 — Token Similarity Clustering

For entities that remain unresolved after Stages 1–2:

1. Group entities by `EntityLabel`
2. Within each label group, compute pairwise **token-set similarity** using `rapidfuzz.fuzz.token_set_ratio`
3. If similarity `>= fuzzy_threshold` (default: `85`), mark as a match
4. Build a graph of matches; entities in the same connected component form a cluster

**Token-set ratio** handles:
- Word reordering (`"neural network"` ↔ `"network neural"`)
- Added/removed words (`"convolutional neural network"` ↔ `"neural network"`)
- Partial phrase matches (`"generative adversarial network"` ↔ `"gan"` is not matched here — Stage 2 handles abbreviations)

**Confidence:** `similarity_score / 100.0`

**Efficiency:** O(n²) within each label group. For a corpus of ~10k entities across 13 labels, worst-case ~3.8M comparisons, which is acceptable for a one-time resolution pass.

### 2.4 Stage 4 — Entity-Type Protection

Prevents merging entities of different semantic types.

**Default compatibility rules:**
- Always compatible: same `EntityLabel`
- Never compatible: different `EntityLabel` (strict mode)

**Extended compatibility matrix** (configurable):

| Label A | Compatible Labels |
|---------|------------------|
| `METHOD` | `METHOD`, `TOOL` |
| `TOOL` | `TOOL`, `METHOD` |
| `DATASET` | `DATASET` |
| `METRIC` | `METRIC` |
| `PERSON` | `PERSON`, `ORGANIZATION` |
| `ORGANIZATION` | `ORGANIZATION`, `PERSON` |
| All others | Self only |

The compatibility check is applied at every stage — no cross-type merges ever occur unless the compatibility matrix explicitly allows it.

### 2.5 Stage 5 — Corpus-Wide Cluster Generation

After all pairwise matches are computed:
1. Build a graph where nodes are entity references and edges are matches (from any stage)
2. Compute connected components
3. Each component → one `EntityCluster`
4. The canonical text for a cluster is chosen by:
   - Longest variant by character count
   - Tie-break: highest confidence
   - Tie-break: lexicographic order
5. Generate `ResolutionResult` with statistics

**Transitive closure example:**
- Entity A ("BERT") matches B ("bert") via exact
- Entity B ("bert") matches C ("berts") via fuzzy
- Result: A, B, C in same cluster with canonical "BERT"

---

## 3. Data Models

### 3.1 `CanonicalEntity`

```python
class CanonicalEntity(BaseModel):
    canonical_id: str          # Unique ID: "ce_{uuid4_short}"
    canonical_text: str        # Canonical surface form
    label: EntityLabel         # Entity type
    variants: list[str]        # All surface forms seen
    entity_ids: list[str]      # All RUOEntity.entity_id values
    confidence: float          # Aggregate confidence
    resolution_method: str     # "exact" | "alias" | "fuzzy" | "hybrid"
```

**`resolution_method` semantics:**
| Value | Meaning |
|-------|---------|
| `exact` | All members matched via exact normalization |
| `alias` | At least one member matched via alias dictionary |
| `fuzzy` | At least one member matched via token similarity |
| `hybrid` | Multiple matching methods used |

### 3.2 `EntityAlias`

```python
class EntityAlias(BaseModel):
    canonical_id: str   # Points to the canonical entity
    variant: str        # Surface form variant
    confidence: float   # Confidence of this variant → canonical mapping
```

### 3.3 `EntityCluster`

```python
class EntityCluster(BaseModel):
    cluster_id: str            # Unique ID: "ec_{uuid4_short}"
    canonical_entity: CanonicalEntity
    members: list[EntityAlias]   # One per RUOEntity in the cluster
    size: int                    # Number of members
```

### 3.4 `ResolutionResult`

```python
class ResolutionResult(BaseModel):
    clusters: list[EntityCluster]   # All resolved clusters
    unresolved: list[RUOEntity]     # Entities not matched to any cluster
    total_entities: int             # Input count
    resolved_count: int             # Entities in clusters
    cluster_count: int              # Number of clusters
    resolution_rate: float          # resolved_count / total_entities
    stage_counts: dict[str, int]    # Entities resolved per stage
    alias_hits: list[dict]          # Which aliases were matched (for audit)
```

---

## 4. Token Similarity Algorithm

Uses `rapidfuzz.fuzz.token_set_ratio(a, b)`:

```python
from rapidfuzz import fuzz

def token_similarity(a: str, b: str) -> float:
    """Return a score in [0, 100]."""
    return fuzz.token_set_ratio(a, b)
```

**Why `token_set_ratio`:**
- Best for entity names where word order may vary
- Handles plural/singular variations when combined with normalization
- Robust against added/removed modifier words

**Threshold:** Default `85.0` (configurable via `fuzzy_threshold` parameter).

---

## 5. Confidence Model

| Method | Base Confidence | Notes |
|--------|----------------|-------|
| Exact match | `1.0` | Deterministic, no ambiguity |
| Alias lookup | `0.95` | Slight uncertainty — aliases are manually curated but context-independent |
| Token similarity | `score / 100.0` | Proportional to similarity score |
| Aggregate cluster | `min(member confidences)` | Conservative — weakest link |

---

## 6. Integration with CorpusManager

The `EntityResolver` operates **independently** of `CorpusManager` — it takes a list of `RUOEntity` and returns `ResolutionResult`.

**Suggested workflow:**

```python
resolver = EntityResolver()
entities = list(chain.from_iterable(
    doc.entities for doc in corpus_manager.get_documents()
))
result = resolver.resolve(entities)
```

The resolver has no coupling to the corpus layer — it can resolve entities from a single document, a subset, or the full corpus.

---

## 7. Configuration: `config/entity_aliases.yaml`

Format:

```yaml
aliases:
  - canonical: "canonical name"
    variants:
      - "variant 1"
      - "variant 2"
    label: method        # EntityLabel value
```

**Loading:** Via `yaml.safe_load()`, following the existing pattern in `section_normalizer.py`.

---

## 8. Performance Considerations

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| Normalization | O(n) | Single pass |
| Alias lookup | O(n * k) | k = avg variants per alias |
| Pairwise fuzzy | O(m²) | m = entities per label group |
| Connected components | O(v + e) | Union-find on match graph |

**Optimization for large corpora (>10k entities):**
- Parallelize per-label fuzzy matching
- Filter: skip entities with highly dissimilar lengths
- Use `cdist` from RapidFuzz for batch comparison

---

## 9. Edge Cases

| Case | Handling |
|------|----------|
| Empty entity list | Returns empty `ResolutionResult` |
| Single entity | Returns one cluster with one member, unresolved empty |
| All entities identical | Single cluster with all members, confidence 1.0 |
| No matches | All entities in `unresolved`, empty `clusters` |
| Case-only differences | Stage 1 (lowercase normalization) catches these |
| Abbreviations | Stage 2 (alias dict) handles known abbreviations |
| Typos/minor variations | Stage 3 (fuzzy, threshold 85) captures these |
| Cross-label same text | Type protection prevents merge (e.g., "BERT" as METHOD vs PERSON) |
| Self-match | Entity never compared to itself |
| Duplicate input entities | If same `entity_id` appears twice, deduplicated |
