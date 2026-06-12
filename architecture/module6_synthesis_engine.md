# Module 6 — Literature Review & Research Synthesis Engine Architecture

**Status:** Design Document  
**Date:** 2026-06-11  
**Version:** 1.0  

---

## Table of Contents

1. [Scope](#1-scope)
2. [Review Types](#2-review-types)
3. [Data Models](#3-data-models)
4. [Synthesis Pipeline](#4-synthesis-pipeline)
5. [Theme Detection](#5-theme-detection)
6. [Finding Generation](#6-finding-generation)
7. [Review Construction](#7-review-construction)
8. [Traceability Contract](#8-traceability-contract)
9. [Confidence Model](#9-confidence-model)
10. [Failure Modes](#10-failure-modes)
11. [Integration Plan](#11-integration-plan)
12. [Evaluation Plan](#12-evaluation-plan)

---

## 1. Scope

### 1.1 Position in Pipeline

```
PDF → M1: Extraction → SRO → M2: Understanding → RUO
  → M3: Corpus Intelligence → CorpusGraph + Entity Clusters + Relations
    → M4: Reasoning Engine → MultiHop / Consensus / Contradiction / Gap Results
      → M5: Query System → ResearchAnswer (question-driven)
        → **M6: Synthesis Engine ← YOU ARE HERE**
          → ReviewResult (structured document)
```

Module 6 sits above the entire M1–M5 stack. It consumes the outputs of all previous modules and produces structured, evidence-backed literature reviews. Unlike M5 (which answers individual questions), M6 generates comprehensive synthesis documents.

### 1.2 What Module 6 IS Responsible For

| Capability | Description |
|---|---|
| **Structured review generation** | Produce complete literature review documents with title, abstract, sections, and bibliography |
| **Theme detection** | Identify research themes, topics, and sub-areas from entity clusters, relations, and document metadata |
| **Evidence grouping** | Aggregate related evidence (consensus, contradiction, gaps) into thematic findings |
| **Finding generation** | Produce deterministic, evidence-backed finding statements per theme |
| **Review section assembly** | Construct mandatory and optional sections from findings |
| **Cross-document synthesis** | Combine information across all corpus documents into coherent narratives |
| **Traceability enforcement** | Every sentence in the review maps to source evidence → chunk → document |
| **Confidence scoring** | Compute deterministic confidence at finding, section, and review level |

### 1.3 What Module 6 Does NOT Do

| Out of Scope | Rationale |
|---|---|
| Natural language generation | No LLMs, no embeddings, no generative models — only template + slot-filling |
| Novel insight discovery | Cannot invent findings not supported by corpus evidence |
| Fact-checking or verification | Relies entirely on M1–M5 evidence chains |
| Document ingestion | Module 1 responsibility |
| Query answering | Module 5 responsibility |
| Reasoning execution | Module 4 responsibility |
| Corpus mutation | Read-only — never modifies RUO documents, graphs, or indexes |
| Citation graph construction | Uses existing M3 document relations |
| Plagiarism detection | Out of scope |
| Writing-style customization | Single output template; no tone/voice control |

### 1.4 Inputs Consumed

| Input | Source Module | Type | Usage in M6 |
|---|---|---|---|
| `CorpusGraphResult` | M3 | `CorpusGraphResult` | Entity cluster labels, edge types, node metadata for theme detection |
| `ResolutionResult` | M3 | `ResolutionResult` | Entity cluster membership, canonical labels, cluster size |
| `DocumentRelationResult` | M3 | `DocumentRelationResult` | Cross-document relation evidence |
| Multi-hop results | M4 | `ReasoningResult` | Entity relationships, graph paths |
| Consensus results | M4 | `ConsensusResult` | Per-entity consensus classifications and ratios |
| Contradiction results | M4 | `ContradictionResult` | Direct/indirect contradiction data |
| Gap analysis results | M4 | `GapAnalysisResult` | Research gap items of all 5 types |
| `AggregatedEvidence` | M5 | `list[AggregatedEvidence]` | Evidence with traceability metadata |
| `ResearchAnswer` | M5 | `list[ResearchAnswer]` | Query answers that can seed review sections |
| `RUODocument` list | M2/M3 | `list[RUODocument]` | Document metadata (title, authors, year, abstract) |
| `RUOClaim` list | M2 | `list[RUOClaim]` | Per-document claims for finding generation |

### 1.5 System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      MODULE 6 — SYNTHESIS ENGINE                         │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    ReviewOrchestrator                               │ │
│  │  - generate(review_request) → ReviewResult                         │ │
│  │  - Pipeline: select_corpus → collect_evidence → detect_themes      │ │
│  │    → group_evidence → generate_findings → build_sections →         │ │
│    → verify_traceability → assemble_review                            │ │
│  └──────┬──────────┬──────────┬──────────┬──────────┬─────────────────┘ │
│         │          │          │          │          │                    │
│         ▼          ▼          ▼          ▼          ▼                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ Corpus   │ │ Evidence │ │ Theme    │ │ Finding  │ │ Section      │  │
│  │ Selector │ │ Collector│ │ Detector │ │ Generator│ │ Builder      │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
│                                                              │          │
│                                                              ▼          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    Traceability Verifier                           │ │
│  │  - verify_review(review) → (verified, failures)                   │ │
│  │  - Every finding → Evidence → Chunk → Document                    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  Consumes: CorpusGraph | ConsensusResult | ContradictionResult |        │
│            GapAnalysisResult | ReasoningResult | RUODocument | RUOClaim │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Review Types

### 2.1 ReviewType Enum

```python
from __future__ import annotations

from enum import Enum

try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):
        pass


class ReviewType(StrEnum):
    """Review categories that Module 6 can generate."""

    GENERAL = "general"
    """Comprehensive literature review covering all themes."""

    METHOD = "method"
    """Method-focused review: techniques, architectures, algorithms."""

    DATASET = "dataset"
    """Dataset-focused review: benchmarks, corpora, evaluation data."""

    CONSENSUS = "consensus"
    """Agreement analysis: what the field broadly agrees on."""

    CONTRADICTION = "contradiction"
    """Disagreement analysis: open debates and conflicting results."""

    RESEARCH_GAP = "research_gap"
    """Gap analysis: under-studied areas and missing comparisons."""

    COMPARATIVE = "comparative"
    """Side-by-side comparison of methods, datasets, or approaches."""

    LANDSCAPE = "landscape"
    """High-level research landscape summary with trends."""
```

### 2.2 Review Type Properties

| ReviewType | Mandatory Sections | Typical Length | Primary Data Source |
|---|---|---|---|
| GENERAL | All standard sections | 2000–5000 words | All M4 engines |
| METHOD | Methods Landscape, Comparative, Gaps | 1000–3000 words | Multi-hop, entity clusters |
| DATASET | Datasets, Usage, Gaps | 500–2000 words | Entity clusters (dataset label) |
| CONSENSUS | Consensus, Comparative | 500–1500 words | ConsensusEngine |
| CONTRADICTION | Contradictions, Comparative | 500–1500 words | ContradictionEngine |
| RESEARCH_GAP | Research Gaps, Future Work | 300–1000 words | ResearchGapEngine |
| COMPARATIVE | Methods Landscape, Comparative, Datasets | 1000–2500 words | Multi-hop + Consensus |
| LANDSCAPE | Abstract, Introduction, Methods, Gaps, Conclusion | 1000–2000 words | All engines (summary) |

### 2.3 Section Requirements by ReviewType

```python
# Mandatory and optional sections per review type.
# Keys: ReviewType name. Values: (mandatory_sections, optional_sections)

_SECTION_REQUIREMENTS: dict[str, tuple[list[str], list[str]]] = {
    "general": (
        ["abstract", "introduction", "methods_landscape", "conclusion"],
        ["datasets", "consensus", "contradictions", "research_gaps"],
    ),
    "method": (
        ["abstract", "methods_landscape", "comparative"],
        ["introduction", "datasets", "research_gaps", "conclusion"],
    ),
    "dataset": (
        ["abstract", "datasets"],
        ["introduction", "methods_landscape", "research_gaps", "conclusion"],
    ),
    "consensus": (
        ["abstract", "consensus"],
        ["introduction", "methods_landscape", "conclusion"],
    ),
    "contradiction": (
        ["abstract", "contradictions"],
        ["introduction", "methods_landscape", "conclusion"],
    ),
    "research_gap": (
        ["abstract", "research_gaps"],
        ["introduction", "methods_landscape", "future_work", "conclusion"],
    ),
    "comparative": (
        ["abstract", "comparative"],
        ["introduction", "methods_landscape", "datasets", "conclusion"],
    ),
    "landscape": (
        ["abstract", "introduction", "conclusion"],
        ["methods_landscape", "datasets", "consensus", "contradictions", "research_gaps"],
    ),
}
```

---

## 3. Data Models

### 3.1 ReviewRequest

```python
from pydantic import BaseModel, Field, field_validator
from typing import Any


class ReviewRequest(BaseModel):
    """Request to generate a literature review / synthesis document."""

    review_id: str
    review_type: str  # ReviewType enum value
    title: str = ""
    corpus_ids: list[str] = Field(default_factory=list)
    max_findings_per_section: int = Field(default=10, ge=1, le=50)
    min_confidence: float = Field(default=0.3, ge=0.0, le=1.0)
    include_abstract: bool = True
    include_bibliography: bool = True
    include_traceability_report: bool = False
    custom_sections: list[str] = Field(default_factory=list)

    @field_validator("review_type")
    @classmethod
    def _validate_review_type(cls, v: str) -> str:
        normalized = v.strip().lower()
        known = {rt.value for rt in ReviewType}
        if normalized not in known:
            raise ValueError(f"Unknown review_type '{v}'. Must be one of {sorted(known)}")
        return normalized
```

### 3.2 ReviewFinding

```python
class ReviewFinding(BaseModel):
    """A single evidence-backed finding in a review section."""

    finding_id: str
    finding_type: str  # "consensus", "contradiction", "gap", "method", "dataset", "relation"
    statement: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list)
    source_document_titles: list[str] = Field(default_factory=list)
    supporting_count: int = 0
    contradicting_count: int = 0
    neutral_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("finding_id")
    @classmethod
    def _validate_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("finding_id must be non-empty")
        return v
```

### 3.3 ReviewSection

```python
class ReviewSection(BaseModel):
    """A section of a literature review document."""

    section_id: str
    section_type: str  # "abstract", "introduction", "methods_landscape", etc.
    title: str
    summary: str = ""
    findings: list[ReviewFinding] = Field(default_factory=list)
    paragraphs: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    word_count: int = 0
    is_mandatory: bool = False

    @field_validator("section_id")
    @classmethod
    def _validate_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("section_id must be non-empty")
        return v
```

### 3.4 ReviewResult

```python
class ReviewResult(BaseModel):
    """The complete output of the synthesis engine.

    review_id is copied from ReviewRequest.review_id (caller-provided).
    No timestamps, no UUIDs — deterministic by design.
    """

    review_id: str
    review_type: str
    title: str

    # Core content
    abstract: str = ""
    sections: list[ReviewSection] = Field(default_factory=list)

    # Statistics
    total_findings: int = 0
    total_evidence_items: int = 0
    total_documents_cited: int = 0
    total_words: int = 0

    # Quality
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    traceability_verified: bool = False
    traceability_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    # Sources
    bibliography: list[str] = Field(default_factory=list)
    source_attribution: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def _validate_title(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("title must be non-empty")
        return v

    @field_validator("review_type")
    @classmethod
    def _validate_review_type(cls, v: str) -> str:
        normalized = v.strip().lower()
        known = {rt.value for rt in ReviewType}
        if normalized not in known:
            raise ValueError(f"Unknown review_type '{v}'")
        return normalized
```

### 3.5 Supporting Models

All IDs in Module 6 are generated deterministically using `zlib.crc32`,
consistent with the M5 pattern.

```python
import zlib


def _generate_id(prefix: str, *parts: str) -> str:
    """Deterministic ID generation via CRC32.
    
    Consistent with M5 pattern (query/engine.py, query/synthesizer.py).
    """
    raw = "::".join(parts)
    h = zlib.crc32(raw.encode()) & 0xFFFFFFFF
    return f"{prefix}_{h:012x}"
```

```python
class EvidenceBundle(BaseModel):
    """A group of related evidence items for a single theme or finding."""

    bundle_id: str
    theme: str
    evidence_items: list[AggregatedEvidence] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list)
    aggregate_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    finding_type: str = ""


class ThemeCluster(BaseModel):
    """A detected research theme with associated entities and evidence."""

    theme_id: str
    label: str
    entity_cluster_ids: list[str] = Field(default_factory=list)
    entity_labels: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    relation_types: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
```

`AggregatedEvidence` is reused from M5 (`researchmind.query.models.AggregatedEvidence`).

**ID Generation Rules:**

| Field | Prefix | CRC32 Key | Example |
|---|---|---|---|
| `EvidenceBundle.bundle_id` | `"bnd"` | `theme_label::finding_type` | `bnd_a1b2c3d4e5f6` |
| `ThemeCluster.theme_id` | `"thm"` | `component_label::entity_count` | `thm_123456789abc` |
| `ReviewSection.section_id` | `"sec"` | `review_type::section_type::sequence` | `sec_def012345678` |
| `ReviewFinding.finding_id` | `"find"` | `section_type::theme_label::index` | `find_90abcdef1234` |

Note: `ReviewRequest.review_id` is caller-provided (not generated).
`ReviewResult.review_id` is copied from the request.

---

## 4. Synthesis Pipeline

### 4.1 Pipeline Diagram

```
ReviewRequest
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 1. CORPUS SELECTION                                          │
│    • Filter documents by corpus_ids (or use all)             │
│    • Validate minimum document count (≥ 1)                   │
│    • Return selected CorpusGraphResult + document list       │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. EVIDENCE COLLECTION                                       │
│    • Collect from M4: consensus for entity clusters          │
│    • Collect from M4: contradiction for candidate entities   │
│    • Collect from M4: gap analysis on corpus                 │
│    • Collect from M4: multi-hop exploration from top entities│
│    • Collect from M5: recent query answers (if available)    │
│    • Return: consolidated EvidenceBundle list                │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. THEME DETECTION                                           │
│    • Extract entity clusters from graph                      │
│    • Group clusters by edge types (co-occurrence patterns)   │
│    • Cluster entities into research themes                   │
│    • Rank themes by evidence density                         │
│    • Return: list[ThemeCluster] sorted by confidence         │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. EVIDENCE GROUPING                                         │
│    • Assign each EvidenceBundle to a ThemeCluster            │
│    • For each theme, group by finding_type                   │
│      (consensus / contradiction / gap / method / dataset)    │
│    • Deduplicate evidence across groups                      │
│    • Return: (theme → {finding_type → [EvidenceBundle]})     │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 5. FINDING GENERATION                                        │
│    • For each (theme, finding_type) group:                   │
│      - Generate finding statement via template               │
│      - Compute finding confidence                            │
│      - Attach evidence_ids and source_document_ids           │
│    • Rank findings within each section by confidence         │
│    • Apply max_findings_per_section limit                    │
│    • Return: list[ReviewFinding] per section                 │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 6. SECTION CONSTRUCTION                                      │
│    • Select sections per ReviewType (mandatory + optional)   │
│    • For each section:                                       │
│      - Build section title                                   │
│      - Compose summary paragraph from findings               │
│      - Assemble paragraphs from finding templates            │
│      - Compute section confidence                            │
│    • Build abstract from section summaries                   │
│    • Return: list[ReviewSection] in document order           │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 7. TRACEABILITY VERIFICATION                                  │
│    • Verify every ReviewFinding.evidence_ids resolves        │
│    • Verify Finding → Evidence → Chunk → Document chain      │
│    • Drop findings with broken traces                        │
│    • Apply confidence downgrades for degraded traces         │
│    • Return: (verified_sections, failure_count)              │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ 8. FINAL REVIEW ASSEMBLY                                     │
│    • Assemble ReviewResult from verified sections            │
│    • Compute overall confidence                              │
│    • Build bibliography from cited documents                 │
│    • Build source_attribution index                          │
│    • Compute statistics (total_findings, word_count, etc.)   │
│    • Return: ReviewResult                                    │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
ReviewResult
```

### 4.2 Stage Specifications

| Stage | Input | Output | Deterministic | Error Mode |
|---|---|---|---|---|
| 1. Corpus Selection | `ReviewRequest`, `CorpusManager` | Filtered documents + graph | Yes | Empty corpus → return error |
| 2. Evidence Collection | Documents, graph, M4 engines | `list[EvidenceBundle]` | Yes | Engine failure → partial collection |
| 3. Theme Detection | Graph, entity clusters | `list[ThemeCluster]` | Yes | Sparse graph → few themes |
| 4. Evidence Grouping | Themes, evidence bundles | `dict[str, dict[str, list]]` | Yes | Unmatched evidence → dropped |
| 5. Finding Generation | Grouped evidence | `list[ReviewFinding]` | Yes | No evidence → empty section |
| 6. Section Construction | Findings, `ReviewType` | `list[ReviewSection]` | Yes | Missing mandatory section → error |
| 7. Traceability Verification | Sections, document store | Verified sections | Yes | Broken chain → downgrade/drop |
| 8. Final Assembly | Verified sections | `ReviewResult` | Yes | Assembly error → partial result |

### 4.3 Orchestrator Interface

```python
class ReviewOrchestrator:
    """Top-level orchestrator for Module 6."""

    def __init__(
        self,
        corpus_manager: Any,
        graph: Any,
        consensus_engine: Any,
        contradiction_engine: Any,
        gap_engine: Any,
        multi_hop_reasoner: Any,
        document_store: Any,
    ) -> None:
        ...

    def generate(self, request: ReviewRequest) -> ReviewResult:
        """Generate a literature review from a ReviewRequest.
        
        Runs the full 8-stage pipeline. Never raises — failures
        are captured in ReviewResult.errors / ReviewResult.warnings.
        """
        ...
```

---

## 5. Theme Detection

### 5.1 Overview

Theme detection discovers research topics by analyzing entity clusters, their co-occurrence patterns, and the relations that connect them. No ML, no embeddings, no LLMs.

### 5.2 Algorithm: Entity Co-Occurrence Clustering

```python
def detect_themes(
    graph: CorpusGraphResult,
    max_themes: int = 10,
    min_cluster_size: int = 2,
) -> list[ThemeCluster]:
    """Deterministic theme detection using graph structure.

    1. Collect all entity_cluster nodes from the graph.
    2. Build a co-occurrence matrix from COMPARES_WITH edges.
    3. Group entity clusters into themes via connected components
       on the co-occurrence subgraph.
    4. For each component:
       a. Label = highest-degree entity label in the component.
       b. Entity IDs = all entity_cluster_ids in the component.
       c. Documents = union of documents that mention any entity.
       d. Relation types = union of edge types within component.
       e. Confidence = mean edge confidence within component.
    5. Sort themes by confidence descending.
    6. Apply max_themes limit.
    """
```

### 5.3 Theme Labeling

| Rule | Priority | Example |
|---|---|---|
| Use highest-degree entity label | 1 | "Adam" (degree 30) > "SGD" (degree 12) |
| Use document title for document-linked clusters | 2 | "BERT: Pre-training..." |
| Fall back to "Theme {n}" | 3 | "Theme 1" |

### 5.4 Theme Types

Detected themes receive a classification:

```python
class ThemeType(StrEnum):
    METHOD = "method"          # Entity clusters are predominantly methods
    DATASET = "dataset"        # Entity clusters are predominantly datasets
    METRIC = "metric"          # Entity clusters are predominantly metrics
    CONCEPT = "concept"        # Entity clusters are theoretical concepts
    MIXED = "mixed"            # Multiple entity types present
```

Classification is determined by the majority `EntityLabel` among the theme's entity clusters.

### 5.5 Empty Corpus Handling

If `len(entity_clusters) < 2` or `len(graph.edges) == 0`, theme detection returns a single "Uncategorized" theme containing all entities. A warning is added.

---

## 6. Finding Generation

### 6.1 Finding Templates

Each finding type has a deterministic template. Slot values come from evidence metadata, entity labels, and graph properties.

#### 6.1.1 Consensus Finding

```
Template: "There is {strength} consensus that {entity_label}
           is {classification} across {doc_count} document(s).
           Support: {support_pct:.0f}% ({support_count}),
           Contradict: {contradict_pct:.0f}% ({contradict_count})."

strength mapping:
  support_ratio >= 0.8 → "strong"
  support_ratio >= 0.6 → "moderate"
  support_ratio >= 0.4 → "weak"
  else                 → "insufficient"
```

#### 6.1.2 Contradiction Finding

```
Template: "Conflicting results found for {entity_label}:
           {direct_count} direct and {indirect_count} indirect
           contradiction(s) (confidence: {confidence:.2f})."

If direct_count > 0:
  "{doc_a} and {doc_b} disagree on {entity_label}."
```

#### 6.1.3 Research Gap Finding

```
Template per gap type:

  isolated_entity:       "{entity_label} is not linked to any
                          related concept in the corpus."
  missing_comparison:    "{entity_a} and {entity_b} are not
                          directly compared in any document."
  low_confidence_claim:  "{entity_label} claims lack supporting
                          evidence (confidence: {confidence:.2f})."
  under_studied_dataset: "{dataset} appears in only {count}
                          document(s)."
  unconnected_document:  "{title} shares no entities with other
                          documents."
```

#### 6.1.4 Method Finding

```
Template: "{entity_label} is discussed in {doc_count}
           document(s) in the context of {relation_types}.
           Key related entities: {related_entities}."
```

#### 6.1.5 Dataset Finding

```
Template: "{dataset} is used by {doc_count} document(s)
           including {doc_titles}. Common tasks: {tasks}."
```

#### 6.1.6 Relation Finding

```
Template: "{source_entity} is {relation_type} to {target_entity}
           (confidence: {confidence:.2f})."
```

### 6.2 Finding Generation Algorithm

```python
def generate_findings(
    theme: ThemeCluster,
    evidence_bundles: list[EvidenceBundle],
    max_findings_per_section: int = 10,
) -> list[ReviewFinding]:
    """Generate findings for a single theme.

    1. If theme has consensus evidence → generate consensus findings.
    2. If theme has contradiction evidence → generate contradiction findings.
    3. If theme has gap evidence → generate gap findings.
    4. If theme has entity clusters with method/dataset label
       → generate method/dataset findings.
    5. For each entity pair with an edge → generate relation findings.
    6. Sort all findings by confidence descending.
    7. Apply max_findings_per_section limit.
    8. Return list[ReviewFinding] with unique finding_ids.
    """
```

### 6.3 Finding ID Generation

```python
import zlib

def _generate_finding_id(section_type: str, theme_label: str, index: int) -> str:
    raw = f"{section_type}::{theme_label}::{index}"
    h = zlib.crc32(raw.encode()) & 0xFFFFFFFF
    return f"find_{h:012x}"
```

---

## 7. Review Construction

### 7.1 Document Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    REVIEW DOCUMENT                           │
├─────────────────────────────────────────────────────────────┤
│ Title: "{topic}: A Literature Review"                        │
│                                                              │
│ Abstract  (from section summaries)                           │
├─────────────────────────────────────────────────────────────┤
│ 1. Introduction [mandatory]                                  │
│    • Corpus overview (doc count, entity count, time span)    │
│    • Review scope and methodology                            │
├─────────────────────────────────────────────────────────────┤
│ 2. Methods Landscape [mandatory if method/dataset present]   │
│    • Per-theme method descriptions                           │
│    • Entity-relation summaries                               │
│    • Key technique comparisons                               │
├─────────────────────────────────────────────────────────────┤
│ 3. Datasets [mandatory for DATASET type]                     │
│    • Dataset catalog with usage counts                       │
│    • Dataset-entity associations                             │
├─────────────────────────────────────────────────────────────┤
│ 4. Consensus [mandatory for CONSENSUS type]                  │
│    • Per-entity agreement analysis                           │
│    • Strong/moderate/weak classifications                    │
├─────────────────────────────────────────────────────────────┤
│ 5. Contradictions [mandatory for CONTRADICTION type]         │
│    • Direct and indirect contradictions                      │
│    • Document-level dispute mapping                          │
├─────────────────────────────────────────────────────────────┤
│ 6. Research Gaps [mandatory for RESEARCH_GAP type]           │
│    • Gap catalog by type                                     │
│    • Suggestions for future work                             │
├─────────────────────────────────────────────────────────────┤
│ 7. Comparative Analysis [mandatory for COMPARATIVE type]     │
│    • Side-by-side method/dataset comparisons                 │
│    • Trade-off summaries                                     │
├─────────────────────────────────────────────────────────────┤
│ 8. Conclusion [mandatory]                                   │
│    • Summary of key findings                                 │
│    • Limitations of current corpus                           │
│    • Recommended future directions                           │
├─────────────────────────────────────────────────────────────┤
│ Bibliography [optional]                                      │
│ • List of all cited documents with titles, authors, years    │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 Section Builder

```python
def build_sections(
    review_type: str,
    findings_by_type: dict[str, list[ReviewFinding]],
    corpus_metadata: dict,
    max_findings: int = 10,
) -> list[ReviewSection]:
    """Build review sections for a given ReviewType.

    1. Look up mandatory and optional sections from _SECTION_REQUIREMENTS.
    2. For each section type:
       a. Filter findings_by_type for matching finding types.
       b. Apply max_findings limit.
       c. Build section title from section type.
       d. Compose summary = first paragraph summarizing all findings.
       e. Build paragraph list = one paragraph per finding.
       f. Compute section confidence = min(finding confidences).
       g. Compute word count.
    3. Sort sections in document order.
    4. Return list[ReviewSection].
    """
```

### 7.3 Section Document Order

```python
_SECTION_ORDER = [
    "abstract",
    "introduction",
    "methods_landscape",
    "datasets",
    "consensus",
    "contradictions",
    "comparative",
    "research_gaps",
    "future_work",
    "conclusion",
]

_SECTION_TITLES = {
    "abstract": "Abstract",
    "introduction": "Introduction",
    "methods_landscape": "Methods Landscape",
    "datasets": "Datasets",
    "consensus": "Consensus Analysis",
    "contradictions": "Contradictions",
    "comparative": "Comparative Analysis",
    "research_gaps": "Research Gaps",
    "future_work": "Future Work Directions",
    "conclusion": "Conclusion",
}
```

### 7.4 Abstract Composition

```python
def compose_abstract(sections: list[ReviewSection]) -> str:
    """Compose abstract from section summaries.

    Format:
      "This review analyzes {doc_count} documents on {title}.
       {Section 2 summary}
       {Section 3 summary}
       ...
       Overall confidence: {overall_confidence:.2f}."

    `title` is derived from ReviewRequest.title. If empty, falls back
    to a review-type-based default (e.g., "Literature Review").
    """
```

---

## 8. Traceability Contract

### 8.1 Contract Definition

Every sentence in every generated review section must be traceable to a source document.

```
Review Sentence
  → ReviewFinding
    → AggregatedEvidence.evidence_id
      → AggregatedEvidence.source_document_id
        → RUODocument (exists in corpus)
          → RUOChunk (trace ID resolves to chunk)
```

### 8.2 Verification Algorithm

```python
def verify_review(
    review: ReviewResult,
    corpus: Any,
    chunk_index: dict[str, str],  # trace_id → document_id
) -> tuple[bool, list[str]]:
    """Verify traceability of every finding in a review.

    1. For each section:
       a. For each finding:
          i. If finding.evidence_ids is empty → FAILURE
          ii. For each evidence_id:
              - Resolve to AggregatedEvidence via evidence index
              - If evidence has no source_document_id → FAILURE
              - If evidence has trace IDs:
                * Each trace ID must resolve to a chunk
                * The chunk's parent must be source_document_id
              - If evidence has no trace IDs:
                * If evidence_type requires trace (path_edge, contradiction) → FAILURE
                * Otherwise (consensus_entry, gap_item) → ACCEPT
       b. If any finding in the section has failures → section warning
    2. Return (all_pass, failure_list)
    """
```

### 8.3 Failure Handling

| Condition | Action | Confidence Impact |
|---|---|---|
| Empty evidence_ids | Drop finding | N/A (removed) |
| Missing source_document_id | Drop finding | N/A (removed) |
| Broken trace chain | Keep finding | × 0.8 |
| Unresolvable evidence_id | Drop finding | N/A (removed) |
| Circular trace | Break cycle | None |

### 8.4 No-Evidence Policy

If a section has zero findings remaining after traceability verification, that section is replaced with:

```
"Insufficient evidence to construct this section from the current corpus."
```

The section is retained (to preserve document structure) with confidence = 0.0 and a warning.

---

## 9. Confidence Model

### 9.1 Finding Confidence

| Finding Type | Formula | Notes |
|---|---|---|
| Consensus finding | `C = consensus_result.consensus_confidence` | Direct from M4 |
| Contradiction finding | `C = contradiction_result.aggregate_confidence` | Direct from M4 |
| Gap finding (isolated) | `C = gap.confidence` | Direct from M4 gap item |
| Gap finding (missing comparison) | `C = gap.confidence` | Direct from M4 |
| Gap finding (low confidence claim) | `C = 1 - claim.confidence` | Inverse of claim confidence |
| Gap finding (under-studied dataset) | `C = 1 - (doc_count / threshold)` | Linear below threshold |
| Gap finding (unconnected document) | `C = min(1.0, entity_count / max_count)` | Normalized entity count |
| Method finding | `C = max(entity_edges.confidence)` | Best-connected edge |
| Dataset finding | `C = mean(entity_edges.confidence)` | Average over edges |
| Relation finding | `C = edge.confidence` | Direct from graph edge |

All finding confidences are clamped to `[0.0, 1.0]`.

### 9.2 Section Confidence

```
C_section = min(C_finding for all findings in section)
```

The weakest finding bounds the section — no section can be more confident than its least-confident finding.

If a section has no findings, `C_section = 0.0`.

### 9.3 Overall Review Confidence

```
C_review = min(C_section for all mandatory sections)
```

Only mandatory sections contribute to overall confidence. Optional sections that are empty or low-confidence do not affect the overall verdict.

### 9.4 Traceability Downgrade

After traceability verification, if any findings have broken traces:

```
C_post = C_pre * (0.9 ** failure_count)
```

### 9.5 Reference Implementation

```python
def compute_review_confidence(
    sections: list[ReviewSection],
    mandatory_types: list[str],
    traceability_failures: int = 0,
) -> float:
    """Compute overall review confidence."""
    mandatory_confidences = [
        s.confidence for s in sections
        if s.section_type in mandatory_types and s.findings
    ]
    if not mandatory_confidences:
        return 0.0
    base = min(mandatory_confidences)
    if traceability_failures > 0:
        base *= 0.9 ** traceability_failures
    return max(0.0, base)
```

---

## 10. Failure Modes

### 10.1 Pipeline Failures

| # | Failure | Description | Impact | Mitigation |
|---|---|---|---|---|
| F-01 | **Empty corpus** | No documents match `corpus_ids` or corpus has no documents | Review cannot be generated | Return error with `"No documents in corpus"` |
| F-02 | **Insufficient documents** | Only 1 document in corpus | No cross-document synthesis possible | Generate document summary instead of review; add warning |
| F-03 | **No entity clusters** | Entity resolution produced 0 clusters | No theme detection possible | Skip theme detection; use document titles as themes |
| F-04 | **No graph edges** | Graph has 0 edges | No relations to analyze | Generate document catalog instead of review |
| F-05 | **Engine unavailable** | Consensus / Contradiction / Gap engine is None | Missing finding types | Skip unavailable finding types; add warning |

### 10.2 Evidence Collection Failures

| # | Failure | Description | Impact | Mitigation |
|---|---|---|---|---|
| F-06 | **Empty consensus results** | Consensus engine returns no data for any entity | No consensus section | Omit consensus section if optional; add warning if mandatory |
| F-07 | **Empty contradiction results** | No contradictions found in corpus | No contradiction section | Return "No contradictions found" placeholder |
| F-08 | **Empty gap results** | No gaps detected | No gap section | Return "No gaps identified" placeholder |
| F-09 | **Evidence dedup removes all** | Only overlapping evidence across themes | Empty evidence bundles | Log warning; re-insert top survivor |
| F-10 | **All evidence below min_confidence** | Every evidence item below threshold | Evidence bundles empty | Use lowest-above-zero if exists; else 0.0 |

### 10.3 Theme Detection Failures

| # | Failure | Description | Impact | Mitigation |
|---|---|---|---|---|
| F-11 | **Too many themes** | > max_themes distinct components | Truncated theme list | Keep top `max_themes` by confidence |
| F-12 | **Single large theme** | One component contains > 80% of entities | No meaningful grouping | Sub-cluster by edge type within component |
| F-13 | **Theme label collision** | Two themes assigned same label | Confusing output | Append numeric suffix |
| F-14 | **All entities in one document** | Cross-document co-occurrence = 0 | No cross-doc themes | Fall back to per-document themes |

### 10.4 Finding Generation Failures

| # | Failure | Description | Impact | Mitigation |
|---|---|---|---|---|
| F-15 | **Finding template slot missing** | Required slot value not in evidence | Partial finding | Use `"[unknown]"` placeholder |
| F-16 | **Finding ID collision** | CRC32 hash collides between findings | Duplicate IDs | Append index suffix |
| F-17 | **Empty finding group** | No evidence for a finding type in a theme | Finding not generated | Skip; not an error |
| F-18 | **Excessive findings** | > max_findings_per_section candidates | Truncation | Keep top `max_findings` by confidence |

### 10.5 Section Building Failures

| # | Failure | Description | Impact | Mitigation |
|---|---|---|---|---|
| F-19 | **Missing mandatory section** | Required section type has no findings | Review incomplete | Generate empty section with warning |
| F-20 | **Empty mandatory section** | Section has findings but all confidence = 0.0 | Degraded review | Include with confidence = 0.0; add warning |
| F-21 | **Abstract generation fails** | No sections with summaries | No abstract | Use first `min(3, len(sections))` section titles |
| F-22 | **Bibliography empty** | No findings reference any document | No citations | Use all corpus document titles |

### 10.6 Traceability Failures

| # | Failure | Description | Impact | Mitigation |
|---|---|---|---|---|
| F-23 | **Untraceable finding** | Finding has no evidence_ids | Finding removed | Drop finding, log failure |
| F-24 | **Missing evidence record** | evidence_id not in evidence index | Broken evidence chain | Drop finding, log failure |
| F-25 | **Missing source document** | source_document_id not in corpus | Broken document chain | Drop finding, log error |
| F-26 | **Mass traceability failure** | > 50% of findings fail traceability | Review quality degraded | Keep remaining; add prominent warning |
| F-27 | **Chunk resolution failure** | Trace ID does not match any chunk | Incomplete chain | Accept with ×0.8 confidence penalty |

### 10.7 System Failures

| # | Failure | Description | Impact | Mitigation |
|---|---|---|---|---|
| F-28 | **Corpus graph stale** | Graph not rebuilt after document update | Outdated themes | Trigger graph rebuild; add warning |
| F-29 | **Concurrent generation limit** | > 3 simultaneous review generations | Performance | Queue excess, process sequentially |
| F-30 | **Review too long** | Generated review > 10000 words | Truncation | Truncate lowest-confidence sections |
| F-31 | **Disk/resource exhaustion** | Out of memory during generation | Unstable | Fail gracefully with error message |

---

## 11. Integration Plan

### 11.1 File Structure

```
src/researchmind/synthesis/
├── __init__.py                     # Package exports
├── models.py                       # ReviewRequest, ReviewFinding, ReviewSection,
│                                   #   ReviewResult, EvidenceBundle, ThemeCluster
├── orchestrator.py                 # ReviewOrchestrator (top-level pipeline)
├── theme_detector.py               # ThemeDetector — theme discovery
├── evidence_collector.py           # EvidenceCollector — gather from M4/M5
├── finding_generator.py            # FindingGenerator — template-driven findings
├── section_builder.py              # SectionBuilder — review section construction
├── traceability.py                 # TraceabilityVerifier — enforce contract
├── confidence.py                   # Confidence computer — finding/section/review

tests/
├── test_synthesis_models.py
├── test_theme_detector.py
├── test_evidence_collector.py
├── test_finding_generator.py
├── test_section_builder.py
├── test_traceability.py
├── test_confidence.py
├── test_orchestrator.py
```

### 11.2 Dependency Graph

```
                    ┌──────────────────────────────────────┐
                    │      ReviewOrchestrator              │
                    │   (top-level pipeline orchestrator)  │
                    └────┬──────────┬──────────┬───────────┘
                         │          │          │
               ┌─────────▼──┐ ┌─────▼─────┐ ┌─▼───────────┐
               │ Theme      │ │ Evidence  │ │ Traceability│
               │ Detector   │ │ Collector │ │ Verifier    │
               └─────────┬──┘ └─────┬─────┘ └─────────────┘
                         │          │
               ┌─────────▼──────────▼──┐
               │   FindingGenerator    │
               │   (templates + fill)  │
               └─────────┬─────────────┘
                         │
               ┌─────────▼─────────────┐
               │   SectionBuilder      │
               │   (assemble sections) │
               └─────────┬─────────────┘
                         │
               ┌─────────▼─────────────┐
               │   Confidence Computer │
               └───────────────────────┘
```

### 11.3 Reuse Strategy

| Existing Component | How M6 Reuses It |
|---|---|
| `CorpusGraphResult` | Entity clusters, edge types, node metadata for theme detection |
| `CorpusManager.get_documents()` | Document metadata for bibliography and section context |
| `ConsensusEngine.analyze()` | Per-entity consensus data for consensus findings |
| `ContradictionEngine.analyze()` | Contradiction data for contradiction findings |
| `ResearchGapEngine.analyze()` | Gap data for gap findings |
| `MultiHopReasoner.reason()` | Entity relationships for method/dataset findings |
| `AggregatedEvidence` (M5) | Evidence with traceability metadata (reused directly) |
| `ResearchAnswer` (M5) | Seed content for review sections (optional) |
| `RUODocument` model | Document metadata (title, authors, year) |
| `RUOClaim` model | Claim data for finding context |
| `EntityResolver` (M3) | Cluster metadata for theme labeling |
| `DocumentRelationResult` (M3) | Cross-document relation evidence |
| `TraceabilityVerifier` pattern (M5) | Adapted for review-level traceability |

### 11.4 Dependencies on M1–M5

| Dependency | Required | Fallback If Missing |
|---|---|---|
| M3 `CorpusGraphResult` | **Yes** — theme detection requires it | Review cannot be generated |
| M3 `CorpusManager` | **Yes** — document access | Review cannot be generated |
| M4 `ConsensusEngine` | No — consensus section becomes unavailable | Skip CONSENSUS review type |
| M4 `ContradictionEngine` | No — contradiction section becomes unavailable | Skip CONTRADICTION type |
| M4 `ResearchGapEngine` | No — gap section becomes unavailable | Skip RESEARCH_GAP type |
| M4 `MultiHopReasoner` | No — method/dataset findings degraded | Use entity labels only |
| M5 `AggregatedEvidence` | No — evidence falls back to direct M4 results | No traceability metadata |
| M2 `RUOClaim` | No — claim-level detail unavailable | Use graph edges only |

### 11.5 Implementation Order

| Phase | Files | Depends On | Estimated Effort |
|---|---|---|---|
| **Phase 1: Models** | `models.py`, `__init__.py` | None | 1 day |
| **Phase 2: Theme Detector** | `theme_detector.py` | Phase 1, M3 `CorpusGraphResult` | 2 days |
| **Phase 3: Evidence Collector** | `evidence_collector.py` | Phase 1, M4 engines | 2 days |
| **Phase 4: Finding Generator** | `finding_generator.py` | Phase 1, 2, 3 | 3 days |
| **Phase 5: Section Builder** | `section_builder.py` | Phase 1, 4 | 2 days |
| **Phase 6: Traceability** | `traceability.py` | Phase 1, M3 document store | 1 day |
| **Phase 7: Confidence** | `confidence.py` | Phase 1, 4, 5 | 1 day |
| **Phase 8: Orchestrator** | `orchestrator.py` | Phases 2–7 | 2 days |
| **Phase 9: Tests** | `tests/test_synthesis_*.py` | Phases 1–8 | 3 days |

**Total estimated effort: 17 days**

### 11.6 Integration Checkpoints

| Checkpoint | Criteria | Validation |
|---|---|---|
| CP-1 | All Pydantic models load without validation errors | `python -c "from researchmind.synthesis.models import *"` |
| CP-2 | Theme detection produces ≥ 2 themes on 8-paper corpus | Integration test |
| CP-3 | Evidence collector gathers data from all 4 M4 engines | Integration test with mock engines |
| CP-4 | Finding generator produces all 6 finding types | Unit test with known evidence |
| CP-5 | Section builder produces all mandatory sections | Unit test per ReviewType |
| CP-6 | Traceability verifier catches broken evidence chains | Unit test: 5 broken-chain scenarios |
| CP-7 | Confidence computer returns correct values | Unit test: known inputs → known outputs |
| CP-8 | Full pipeline: generate 3 review types on 8-paper corpus | End-to-end integration test |

---

## 12. Evaluation Plan

### 12.1 Evaluation Dimensions

| Dimension | Metric | Target | Measurement |
|---|---|---|---|
| **Section completeness** | Mandatory sections present | 100% | Automated: count mandatory vs. actual |
| **Finding traceability** | Findings with valid evidence chains | ≥ 95% | Automated: `TraceabilityVerifier.verify()` |
| **Confidence calibration** | Confidence correlates with evidence quality | ≥ 0.8 Spearman | Statistical on 100 findings |
| **Determinism** | Same request → same review | 100% | Run twice, compare hashes per section |
| **Theme detection relevance** | Themes match manual annotation | ≥ 70% | Manual review of 10 themes |
| **No-fabrication guarantee** | Every statement maps to evidence | 100% | Audit: random sample of 50 sentences |
| **Empty-section rate** | Sections with "Insufficient evidence" | ≤ 30% | Count across all review types |
| **Generation time** | P50 / P95 latency | < 30s / < 120s | Timing harness |
| **Review quality** | Human-evaluated coherence | ≥ 3.5 / 5 | Expert review of 3 generated reviews |

### 12.2 Test Corpus

| Corpus | Size | Purpose |
|---|---|---|
| 8-paper evaluation corpus | 57 nodes, 1458 edges | Primary — identical to M3/M4/M5 evaluation |
| 20-paper ML methods corpus | ~200 nodes, ~5000 edges | Mid-scale validation (future) |
| 100-paper multi-domain corpus | ~1000 nodes, ~30000 edges | Scale testing (future) |

The 8-paper corpus is sufficient for initial validation. Module 6 should produce meaningful output even on this small corpus (at minimum: methods landscape, consensus, contradictions, and gaps).

### 12.3 Test Review Types

| ReviewType | Expected Sections | Minimum Findings | Acceptance |
|---|---|---|---|
| GENERAL | 6+ | 20 | All mandatory sections present |
| METHOD | 5+ | 15 | Methods Landscape populated with entity data |
| DATASET | 4+ | 10 | At least 3 datasets identified |
| CONSENSUS | 4+ | 8 | Consensus section has ≥ 3 entities |
| CONTRADICTION | 4+ | 5 | At least 2 contradictions found |
| RESEARCH_GAP | 4+ | 8 | At least 2 gap types covered |
| COMPARATIVE | 4+ | 10 | At least 3 comparative statements |
| LANDSCAPE | 4+ | 12 | Summary covers all major themes |

### 12.4 Automated Evaluation Script

```python
class SynthesisEvaluator:
    """Evaluates Module 6 against a test corpus."""

    def run(
        self,
        orchestrator: ReviewOrchestrator,
        review_types: list[str],
    ) -> dict:
        """Run evaluation for all ReviewTypes.
        
        Returns metrics dict with per-type results and aggregate scores.
        """
        ...

    def _check_traceability(self, review: ReviewResult) -> dict:
        """Verify every finding has valid evidence chains."""
        ...

    def _check_determinism(self, orchestrator, request, runs=2) -> dict:
        """Verify same request produces identical output."""
        ...

    def _measure_confidence_calibration(self, findings) -> dict:
        """Check confidence values are within [0, 1] and correlate."""
        ...
```

### 12.5 Acceptance Criteria

Module 6 is **READY** when:

```
[✓] All 8 ReviewTypes produce valid ReviewResult objects
[✓] Traceability rate ≥ 95%
[✓] Determinism: 100% (identical inputs → identical outputs)
[✓] Confidence bounds: 0 violations (all in [0, 1])
[✓] No-evidence policy enforced: no fabricated statements
[✓] All 9 checkpoints pass
[✓] All mandatory sections present for each ReviewType
[✓] Generation completes without unhandled exceptions
[✓] Total test coverage (unit + integration) ≥ 80%
```

Module 6 is **READY WITH FIXES** when:

```
[~] Traceability rate ≥ 80% but < 95%
[~] Determinism ≥ 95% but < 100%
[~] ≤ 2 acceptance criteria partially met
```

Module 6 is **NOT READY** when:

```
[X] Traceability rate < 80%
[X] Determinism < 95%
[X] Any fabricated (untraceable) statement found
[X] ≥ 3 acceptance criteria failed
```

### 12.6 Test Data Generation

For unit testing, a `make_review_fixtures()` helper creates known inputs:

```python
def make_review_fixtures() -> dict:
    """Create deterministic test fixtures for Module 6 unit tests.
    
    Returns:
        - graph: Small CorpusGraphResult with 3 documents, 10 entity clusters
        - theme_clusters: 3 pre-computed ThemeCluster objects
        - evidence_bundles: 6 EvidenceBundle objects (one per finding type)
        - findings: 12 ReviewFinding objects with known confidence values
        - review_request: ReviewRequest for GENERAL type
    """
```

---

## Appendix A: Template Library

### A.1 Finding Templates (Full)

```python
_FINDING_TEMPLATES: dict[str, dict[str, str]] = {
    "consensus": {
        "answer": (
            "There is {strength} consensus that {entity_label} is "
            "{classification} across {doc_count} document(s). "
            "Support: {support_pct:.0f}% ({support_count} docs), "
            "Contradict: {contradict_pct:.0f}% ({contradict_count} docs)."
        ),
        "insufficient": (
            "Insufficient evidence to determine consensus on {entity_label} "
            "(only {doc_count} document(s) available)."
        ),
    },
    "contradiction": {
        "answer": (
            "Conflicting results found for {entity_label}: "
            "{direct_count} direct and {indirect_count} indirect "
            "contradiction(s) (aggregate confidence: {confidence:.2f})."
        ),
        "none": "No contradictions found for {entity_label}.",
    },
    "gap_isolated": {
        "answer": (
            "{entity_label} is not linked to any related concept in the "
            "current corpus, suggesting an isolated research area."
        ),
    },
    "gap_missing_comparison": {
        "answer": (
            "No direct comparison exists between {entity_a} and {entity_b} "
            "in the corpus, representing a missing comparative analysis."
        ),
    },
    "gap_low_confidence": {
        "answer": (
            "Claims about {entity_label} have low supporting evidence "
            "(confidence: {confidence:.2f}), indicating a need for "
            "further validation."
        ),
    },
    "gap_under_studied": {
        "answer": (
            "{dataset} appears in only {doc_count} document(s), "
            "suggesting it is under-studied relative to other datasets."
        ),
    },
    "gap_unconnected": {
        "answer": (
            "{title} shares no entities with other documents in the "
            "corpus, suggesting it addresses an isolated topic."
        ),
    },
    "method": {
        "answer": (
            "{entity_label} is discussed in {doc_count} document(s) "
            "in the context of {relation_types}. "
            "Key related entities include {related_entities}."
        ),
    },
    "dataset": {
        "answer": (
            "{dataset} is employed by {doc_count} document(s) "
            "including {doc_titles}. "
            "Associated methods: {related_methods}."
        ),
    },
    "relation": {
        "answer": (
            "{source_entity} is {relation_type} to {target_entity} "
            "(confidence: {confidence:.2f})."
        ),
    },
}
```

### A.2 Section Summary Templates

```python
_ABSTRACT_TEMPLATE: str = (
    "This review analyzes {doc_count} documents on {title}. "
    "{section_summaries} "
    "Overall confidence: {confidence:.2f}."
)

_SECTION_SUMMARIES: dict[str, str] = {
    "introduction": (
        "This review analyzes {doc_count} documents "
        "covering {theme_count} research themes. "
        "The corpus spans entities in {method_count} methods, "
        "{dataset_count} datasets, and {metric_count} metrics."
    ),
    "methods_landscape": (
        "The corpus discusses {method_count} key methods "
        "across {doc_count} documents. "
        "Dominant relation types include {relation_types}."
    ),
    "consensus": (
        "Consensus analysis of {entity_count} entities reveals "
        "{strong_count} areas of strong agreement and "
        "{weak_count} areas of weak or insufficient evidence."
    ),
    "contradictions": (
        "Contradiction analysis identified {total_count} "
        "contradictions ({direct_count} direct, "
        "{indirect_count} indirect) across the corpus."
    ),
    "research_gaps": (
        "Gap analysis identified {total_gaps} gaps across "
        "{gap_types} categories, including {isolated_count} "
        "isolated entities and {missing_count} missing comparisons."
    ),
}
```

---

## Appendix B: Index Requirements

| Index | Key | Value | Used By |
|---|---|---|---|
| entity_label → entity_cluster_id | entity label (str) | `list[cluster_id]` | Theme detection |
| entity_cluster_id → document_ids | cluster_id | `list[doc_id]` | Evidence grouping |
| document_id → entity_cluster_ids | doc_id | `list[cluster_id]` | Section construction |
| document_id → document metadata | doc_id | title, authors, year | Bibliography |
| evidence_id → AggregatedEvidence | evidence_id | `AggregatedEvidence` | Traceability verification |
| trace_id → document_id | trace_id (chunk ref) | doc_id | Chunk resolution |
| relation_type → edge list | `RelationType` | `list[edge_id]` | Theme relation analysis |
| finding_type → finding list | "consensus" / etc. | `list[ReviewFinding]` | Section grouping |

All indexes are buildable via a single pass over the `CorpusGraphResult` and document store. No schema changes required.

---

## Appendix C: Glossary

| Term | Definition |
|---|---|
| **Finding** | An atomic, evidence-backed statement about the corpus |
| **Theme** | A research topic or area discovered by grouping related entity clusters |
| **Evidence Bundle** | A collection of related `AggregatedEvidence` items for a single theme |
| **Traceability Contract** | The guarantee that every finding maps to a source document chunk |
| **Section** | A named part of the review document containing related findings |
| **ReviewType** | The category of review to generate (general, method, dataset, etc.) |
| **Confidence Bounds** | All confidence values are clamped to `[0.0, 1.0]` |
| **No-Evidence Policy** | No statement is generated without supporting evidence |
