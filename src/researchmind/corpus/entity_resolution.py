"""Deterministic cross-document entity resolution for RUOCorpus.

Resolution stages:
    1. Exact normalization — lowercased, stripped, whitespace-collapsed
    2. Alias dictionary lookup — YAML-configured known variant mappings
    3. Token similarity clustering — RapidFuzz token-set ratio
    4. Entity-type protection — same-label-only (configurable compatibility)
    5. Corpus-wide cluster generation — transitive closure over all matches
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from researchmind.models.enums import EntityLabel
from researchmind.models.ruo import RUOEntity

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    fuzz = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_FUZZY_THRESHOLD: float = 85.0
"""Minimum token-set similarity (0-100) for a fuzzy match."""

_ALIAS_PATH: str = "config/entity_aliases.yaml"
"""Default path (relative to project root) for the alias dictionary."""

_PUNCT_RE: re.Pattern = re.compile(r"[.,;:!?'\"()]+$")
_WHITESPACE_RE: re.Pattern = re.compile(r"\s+")

# ---------------------------------------------------------------------------
# Label compatibility matrix
# ---------------------------------------------------------------------------

LABEL_COMPATIBILITY: dict[str, set[str]] = {
    EntityLabel.METHOD.value: {EntityLabel.METHOD.value, EntityLabel.TOOL.value},
    EntityLabel.TOOL.value: {EntityLabel.TOOL.value, EntityLabel.METHOD.value},
    EntityLabel.DATASET.value: {EntityLabel.DATASET.value},
    EntityLabel.METRIC.value: {EntityLabel.METRIC.value},
    EntityLabel.PERSON.value: {EntityLabel.PERSON.value, EntityLabel.ORGANIZATION.value},
    EntityLabel.ORGANIZATION.value: {EntityLabel.ORGANIZATION.value, EntityLabel.PERSON.value},
    EntityLabel.MATERIAL.value: {EntityLabel.MATERIAL.value},
    EntityLabel.DISEASE.value: {EntityLabel.DISEASE.value},
    EntityLabel.DRUG.value: {EntityLabel.DRUG.value},
    EntityLabel.GENE_PROTEIN.value: {EntityLabel.GENE_PROTEIN.value, EntityLabel.METHOD.value},
    EntityLabel.ORGANISM.value: {EntityLabel.ORGANISM.value},
    EntityLabel.LOCATION.value: {EntityLabel.LOCATION.value},
    EntityLabel.OTHER.value: {EntityLabel.OTHER.value},
}

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def normalize_entity_text(text: str) -> str:
    """Normalize entity text for matching.

    Steps:
        1. Strip leading/trailing whitespace
        2. Lowercase
        3. Collapse internal whitespace
        4. Remove trailing punctuation (.,;:!?'")
    """
    raw = text.strip().lower()
    raw = _WHITESPACE_RE.sub(" ", raw)
    raw = _PUNCT_RE.sub("", raw)
    return raw.strip()


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class CanonicalEntity(BaseModel):
    """Canonical representation of a resolved entity."""

    model_config = ConfigDict(frozen=True)

    canonical_id: str
    canonical_text: str
    label: EntityLabel
    variants: list[str]
    entity_ids: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    resolution_method: str = Field(
        pattern=r"^(exact|alias|fuzzy|hybrid)$"
    )


class EntityAlias(BaseModel):
    """A single surface-form variant within a cluster."""

    model_config = ConfigDict(frozen=True)

    canonical_id: str
    variant: str
    confidence: float = Field(ge=0.0, le=1.0)


class EntityCluster(BaseModel):
    """A cluster of entity references resolved to the same concept."""

    model_config = ConfigDict(frozen=True)

    cluster_id: str
    canonical_entity: CanonicalEntity
    members: list[EntityAlias]
    size: int = Field(ge=1)


class ResolutionResult(BaseModel):
    """Full result of a corpus-wide entity resolution pass."""

    model_config = ConfigDict(frozen=True)

    clusters: list[EntityCluster]
    unresolved: list[RUOEntity]
    total_entities: int = Field(ge=0)
    resolved_count: int = Field(ge=0)
    cluster_count: int = Field(ge=0)
    resolution_rate: float = Field(ge=0.0, le=1.0)
    stage_counts: dict[str, int] = Field(default_factory=dict)
    alias_hits: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


class EntityResolver:
    """Deterministic entity resolver using exact, alias, and fuzzy matching."""

    def __init__(
        self,
        alias_path: str | Path | None = None,
        fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
        label_compatibility: dict[str, set[str]] | None = None,
    ) -> None:
        self.alias_path = Path(alias_path) if alias_path else Path(_ALIAS_PATH)
        self.fuzzy_threshold = fuzzy_threshold
        self._label_compat: dict[str, set[str]] = (
            label_compatibility or LABEL_COMPATIBILITY
        )
        # variant (normalized) -> canonical text (normalized)
        self._alias_map: dict[str, str] = {}
        # variant (normalized) -> original canonical text (for display)
        self._canonical_for_alias: dict[str, str] = {}
        # variant (normalized) -> EntityLabel
        self._alias_label: dict[str, EntityLabel] = {}
        self._load_aliases()

    # ------------------------------------------------------------------
    # Alias loading
    # ------------------------------------------------------------------

    def _load_aliases(self) -> None:
        """Load alias dictionary from YAML."""
        path = self.alias_path
        if not path.exists():
            return
        if yaml is None:
            return

        with open(path, encoding="utf-8") as fh:
            data: dict[str, list[dict[str, Any]]] = yaml.safe_load(fh) or {}

        raw_aliases = data.get("aliases", [])
        for entry in raw_aliases:
            canonical: str = normalize_entity_text(entry["canonical"])
            label_str: str = entry.get("label", "other")
            try:
                label = EntityLabel(label_str)
            except ValueError:
                continue
            variants: list[str] = entry.get("variants", [])
            # Register the canonical text itself so text matching the
            # canonical form also joins the alias group
            if canonical and canonical not in self._alias_map:
                self._alias_map[canonical] = canonical
                self._canonical_for_alias[canonical] = entry["canonical"]
                self._alias_label[canonical] = label
            for variant in variants:
                norm_v = normalize_entity_text(variant)
                if norm_v and norm_v not in self._alias_map:
                    self._alias_map[norm_v] = canonical
                    self._canonical_for_alias[norm_v] = entry["canonical"]
                    self._alias_label[norm_v] = label

    # ------------------------------------------------------------------
    # Label compatibility check
    # ------------------------------------------------------------------

    def _labels_compatible(
        self, label_a: EntityLabel, label_b: EntityLabel
    ) -> bool:
        """Return True if two entity labels are compatible for merging."""
        if label_a == label_b:
            return True
        compat = self._label_compat.get(label_a.value, set())
        return label_b.value in compat

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(
        self,
        entities: list[RUOEntity],
    ) -> ResolutionResult:
        """Run the full resolution pipeline on a list of entities."""
        if not entities:
            return ResolutionResult(
                clusters=[],
                unresolved=[],
                total_entities=0,
                resolved_count=0,
                cluster_count=0,
                resolution_rate=1.0,
                stage_counts={},
            )

        # 0. Deduplicate by entity_id (keep highest confidence)
        seen: dict[str, RUOEntity] = {}
        for ent in entities:
            eid = ent.entity_id
            if eid not in seen or ent.confidence > seen[eid].confidence:
                seen[eid] = ent
        deduped = list(seen.values())

        total = len(deduped)
        by_eid: dict[str, RUOEntity] = {e.entity_id: e for e in deduped}
        all_ids = [e.entity_id for e in deduped]

        # Union-Find
        parent: dict[str, str] = {eid: eid for eid in all_ids}

        def _find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def _union(x: str, y: str) -> None:
            rx, ry = _find(x), _find(y)
            if rx != ry:
                parent[ry] = rx

        # ----------------------------------------------------------
        # Stage 1: Exact normalization
        # ----------------------------------------------------------
        exact_groups: dict[str, list[str]] = {}
        for eid in all_ids:
            ent = by_eid[eid]
            norm = normalize_entity_text(ent.text)
            exact_groups.setdefault(norm, []).append(eid)

        for _norm, group in exact_groups.items():
            if len(group) < 2:
                continue
            # Union entities with compatible labels
            for i in range(len(group)):
                ent_i = by_eid[group[i]]
                for j in range(i + 1, len(group)):
                    ent_j = by_eid[group[j]]
                    if self._labels_compatible(ent_i.label, ent_j.label):
                        _union(group[i], group[j])

        # ----------------------------------------------------------
        # Stage 2: Alias dictionary lookup
        # ----------------------------------------------------------
        alias_hits: list[dict[str, Any]] = []
        alias_groups: dict[str, list[str]] = {}
        """Maps canonical_norm -> list of entity IDs that matched it via alias."""
        for eid in all_ids:
            ent = by_eid[eid]
            norm = normalize_entity_text(ent.text)
            canonical_norm = self._alias_map.get(norm)
            if canonical_norm is None:
                continue
            alias_label = self._alias_label.get(norm)
            if alias_label is None:
                continue
            if not self._labels_compatible(ent.label, alias_label):
                continue
            alias_key = f"{canonical_norm}|{alias_label.value}"
            alias_groups.setdefault(alias_key, []).append(eid)
            alias_hits.append({
                "entity_id": eid,
                "entity_text": ent.text,
                "canonical": self._canonical_for_alias.get(norm, canonical_norm),
                "label": alias_label.value,
                "confidence": 0.95,
            })

        for _alias_key, group in alias_groups.items():
            if len(group) > 1:
                root = group[0]
                for eid in group[1:]:
                    _union(root, eid)

        # ----------------------------------------------------------
        # Stage 3: Token similarity clustering
        # ----------------------------------------------------------
        # Find singleton roots (single entity not merged by stages 1 or 2)
        root_members: dict[str, list[str]] = {}
        for eid in all_ids:
            root = _find(eid)
            root_members.setdefault(root, []).append(eid)

        singleton_roots = {
            root for root, members in root_members.items()
            if len(members) == 1
        }

        # Group singleton entities by label
        singletons: list[str] = [
            members[0] for root, members in root_members.items()
            if len(members) == 1
        ]
        by_label: dict[str, list[str]] = {}
        for eid in singletons:
            ent = by_eid[eid]
            by_label.setdefault(ent.label.value, []).append(eid)

        # Pairwise fuzzy matching within each label group
        fuzzy_pairs: list[tuple[str, str]] = []
        for label_val, ids in by_label.items():
            if len(ids) < 2:
                continue
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    a, b = ids[i], ids[j]
                    ent_a, ent_b = by_eid[a], by_eid[b]
                    if not self._labels_compatible(ent_a.label, ent_b.label):
                        continue
                    sim = _token_similarity(ent_a.text, ent_b.text)
                    if sim >= self.fuzzy_threshold:
                        fuzzy_pairs.append((a, b))

        for a, b in fuzzy_pairs:
            _union(a, b)

        # ----------------------------------------------------------
        # Stage 4: Entity-type protection
        # Already enforced at every stage via _labels_compatible
        # ----------------------------------------------------------

        # ----------------------------------------------------------
        # Stage 5: Build clusters
        # ----------------------------------------------------------
        # Recompute root memberships after all unions
        final_root_members: dict[str, list[str]] = {}
        for eid in all_ids:
            root = _find(eid)
            final_root_members.setdefault(root, []).append(eid)

        cluster_list: list[EntityCluster] = []
        unresolved_eids: list[str] = []

        for root, members in final_root_members.items():
            if len(members) > 1:
                cluster = self._build_cluster(root, members, by_eid)
                cluster_list.append(cluster)
            else:
                unresolved_eids.append(members[0])

        unresolved_entities = [by_eid[eid] for eid in unresolved_eids]

        resolved_count = total - len(unresolved_entities)
        resolution_rate = resolved_count / total if total > 0 else 1.0

        # Compute per-stage counts
        stage_counts: dict[str, int] = {"exact": 0, "alias": 0, "fuzzy": 0}
        for eid in all_ids:
            root = _find(eid)
            members = final_root_members.get(root, [])
            if len(members) <= 1:
                continue
            method = self._determine_method_for_entity(eid, members, by_eid)
            stage_counts[method] = stage_counts.get(method, 0) + 1

        return ResolutionResult(
            clusters=cluster_list,
            unresolved=unresolved_entities,
            total_entities=total,
            resolved_count=resolved_count,
            cluster_count=len(cluster_list),
            resolution_rate=resolution_rate,
            stage_counts=stage_counts,
            alias_hits=alias_hits,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _determine_method_for_entity(
        self,
        eid: str,
        all_member_eids: list[str],
        by_eid: dict[str, RUOEntity],
    ) -> str:
        """Classify how this entity was resolved.

        Priority order: exact > alias > fuzzy.
        """
        ent = by_eid.get(eid)
        if ent is None:
            return "fuzzy"
        norm = normalize_entity_text(ent.text)
        # Check exact match first (same normalized text, different entity)
        for other_id in all_member_eids:
            if other_id == eid:
                continue
            other_ent = by_eid.get(other_id)
            if other_ent and normalize_entity_text(other_ent.text) == norm:
                return "exact"
        # Then check alias
        if norm in self._alias_map:
            return "alias"
        return "fuzzy"

    def _build_cluster(
        self,
        root: str,
        member_eids: list[str],
        by_eid: dict[str, RUOEntity],
    ) -> EntityCluster:
        """Build an EntityCluster from a list of member entity IDs under a root."""
        entities = [by_eid[eid] for eid in member_eids if eid in by_eid]
        if not entities:
            cid = f"ec_{uuid.uuid4().hex[:12]}"
            return EntityCluster(
                cluster_id=cid,
                canonical_entity=CanonicalEntity(
                    canonical_id=f"ce_{uuid.uuid4().hex[:12]}",
                    canonical_text="",
                    label=EntityLabel.OTHER,
                    variants=[],
                    entity_ids=[],
                    confidence=0.0,
                    resolution_method="fuzzy",
                ),
                members=[],
                size=0,
            )

        # Canonical text: longest variant wins (tie-break: lexicographic)
        by_text: dict[str, list[RUOEntity]] = {}
        for ent in entities:
            t = ent.text.strip()
            by_text.setdefault(t, []).append(ent)
        longest_text = max(by_text.keys(), key=lambda t: (len(t), t))

        # Label: majority vote
        label_counts: dict[str, int] = {}
        for ent in entities:
            label_counts[ent.label.value] = label_counts.get(ent.label.value, 0) + 1
        majority_label_str = max(label_counts, key=label_counts.get)
        majority_label = EntityLabel(majority_label_str)

        # Confidence: MINIMUM of member confidences
        min_conf = min(ent.confidence for ent in entities)

        # Resolution method: classify each entity by how it was resolved
        entity_methods = {
            self._determine_method_for_entity(ent.entity_id, member_eids, by_eid)
            for ent in entities
        }
        has_exact = "exact" in entity_methods
        has_alias = "alias" in entity_methods
        has_fuzzy = "fuzzy" in entity_methods

        if has_exact and (has_alias or has_fuzzy):
            method = "hybrid"
        elif has_alias:
            method = "alias"
        elif has_fuzzy:
            method = "fuzzy"
        else:
            method = "exact"

        all_variants = sorted(set(ent.text.strip() for ent in entities))
        all_entity_ids = sorted(ent.entity_id for ent in entities)

        ce_id = f"ce_{uuid.uuid4().hex[:12]}"
        canonical_entity = CanonicalEntity(
            canonical_id=ce_id,
            canonical_text=longest_text,
            label=majority_label,
            variants=all_variants,
            entity_ids=all_entity_ids,
            confidence=min_conf,
            resolution_method=method,
        )

        members = [
            EntityAlias(
                canonical_id=ce_id,
                variant=ent.text.strip(),
                confidence=ent.confidence,
            )
            for ent in entities
        ]

        cid = f"ec_{uuid.uuid4().hex[:12]}"
        return EntityCluster(
            cluster_id=cid,
            canonical_entity=canonical_entity,
            members=members,
            size=len(members),
        )


# ---------------------------------------------------------------------------
# Token similarity
# ---------------------------------------------------------------------------


def _token_similarity(a: str, b: str) -> float:
    """Compute token similarity in [0, 100] using RapidFuzz.

    Normalizes both inputs first (lowercase, strip), then uses
    token_sort_ratio which handles reordering and case correctly.
    """
    if fuzz is None:
        return 0.0  # pragma: no cover
    na, nb = normalize_entity_text(a), normalize_entity_text(b)
    return float(fuzz.token_sort_ratio(na, nb))
