"""Evidence & Provenance Layer for the Understanding Engine.

Generates EvidenceRecord, EvidenceChain, and ProvenanceRecord objects
from SRO entities/claims, ExtractedFacts, and SemanticTriples.

Every claim, fact, and triple is traceable to one or more chunk spans
via deterministic text matching — no LLMs, embeddings, or graph databases.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from researchmind.models.enums import CanonicalLabel, ClaimType, ExtractionMethod
from researchmind.models.ruo import (
    EvidenceChain,
    EvidenceCoverage,
    EvidenceRecord,
    EvidenceSpan,
    ProvenanceRecord,
    SemanticTriple,
)
from researchmind.models.ruo_enums import (
    AggregationMethod,
    DataSource,
    EvidenceTargetType,
    EvidenceType,
    ProvenanceAction,
    ProvenanceAgentType,
)
from researchmind.models.sro import SROCandidateClaim, SROChunk, SROEntity, StructuredResearchObject
from researchmind.understanding.fact_extractor import (
    ExtractedFact,
    FactExtractionResult,
    FactType,
)
from researchmind.understanding.triple_extractor import TripleExtractionResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapping tables
# ---------------------------------------------------------------------------

_FACT_TO_EVIDENCE_TYPE: dict[FactType, EvidenceType] = {
    FactType.METHOD: EvidenceType.DERIVED,
    FactType.DATASET: EvidenceType.DERIVED,
    FactType.METRIC: EvidenceType.DERIVED,
    FactType.CONTRIBUTION: EvidenceType.PARAPHRASE,
    FactType.LIMITATION: EvidenceType.PARAPHRASE,
    FactType.FUTURE_WORK: EvidenceType.PARAPHRASE,
}

_CLAIM_TO_EVIDENCE_TYPE: dict[ClaimType, EvidenceType] = {
    ClaimType.STATISTICAL: EvidenceType.STATISTICAL,
    ClaimType.CAUSAL: EvidenceType.PARAPHRASE,
    ClaimType.COMPARATIVE: EvidenceType.PARAPHRASE,
    ClaimType.METHODOLOGICAL: EvidenceType.PARAPHRASE,
    ClaimType.EXISTENCE: EvidenceType.DIRECT_QUOTE,
    ClaimType.NEGATION: EvidenceType.DIRECT_QUOTE,
}

_EVIDENCE_CHAIN_TYPE_MAP: dict[str, EvidenceTargetType] = {
    "claim": EvidenceTargetType.CLAIM,
    "entity": EvidenceTargetType.ENTITY,
    "fact": EvidenceTargetType.CLAIM,
}

_AGENT_NAME = "researchmind_understanding"
_PIPELINE_STAGE = "understanding"
_PIPELINE_VERSION = "2.1.0"


# ---------------------------------------------------------------------------
# Outcome model
# ---------------------------------------------------------------------------


class EvidenceBuildResult(BaseModel):
    evidence_records: list[EvidenceRecord]
    evidence_chains: list[EvidenceChain]
    provenance_records: list[ProvenanceRecord]
    coverage: EvidenceCoverage

    total_facts: int = 0
    facts_with_evidence: int = 0
    total_triples: int = 0
    triples_with_evidence: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _find_span_in_chunk(
    chunk_text: str, source_text: str,
) -> tuple[int | None, int | None]:
    if not chunk_text or not source_text:
        return None, None
    source_stripped = source_text.strip()
    if not source_stripped:
        return None, None
    idx = chunk_text.find(source_stripped)
    if idx != -1:
        return idx, idx + len(source_stripped)
    idx_lower = chunk_text.lower().find(source_stripped.lower())
    if idx_lower != -1:
        return idx_lower, idx_lower + len(source_stripped)
    norm_chunk = " ".join(chunk_text.split())
    norm_source = " ".join(source_stripped.split())
    if len(norm_source) <= len(norm_chunk):
        idx_norm = norm_chunk.lower().find(norm_source.lower())
        if idx_norm != -1:
            return idx_norm, idx_norm + len(norm_source)
    return None, None


def _lookup_chunk(
    sro: StructuredResearchObject, chunk_id: str | None,
) -> SROChunk | None:
    if chunk_id is None:
        return None
    for c in sro.body.chunks:
        if c.chunk_id == chunk_id:
            return c
    return None


def _lookup_page_from_chunk(
    sro: StructuredResearchObject, chunk_id: str | None,
) -> int | None:
    chunk = _lookup_chunk(sro, chunk_id)
    return chunk.page_start if chunk is not None else None


def _lookup_chunk_text(
    sro: StructuredResearchObject, chunk_id: str | None,
) -> str | None:
    chunk = _lookup_chunk(sro, chunk_id)
    return chunk.text if chunk is not None else None


def _get_extraction_method(
    sro: StructuredResearchObject,
    chunk_id: str | None,
) -> ExtractionMethod:
    chunk = _lookup_chunk(sro, chunk_id)
    return chunk.extraction_method if chunk is not None else ExtractionMethod.GROBID


def _build_span(
    chunk_id: str | None = None,
    section_id: str | None = None,
    page: int | None = None,
    char_start: int | None = None,
    char_end: int | None = None,
    source_text_sha256: str | None = None,
) -> EvidenceSpan | None:
    kwargs: dict[str, Any] = {}
    if chunk_id is not None:
        kwargs["chunk_id"] = chunk_id
    if section_id is not None:
        kwargs["section_id"] = section_id
    if page is not None:
        kwargs["page"] = page
    if char_start is not None:
        kwargs["char_start"] = char_start
    if char_end is not None:
        kwargs["char_end"] = char_end
    if source_text_sha256 is not None:
        kwargs["source_text_sha256"] = source_text_sha256
    if not kwargs:
        return None
    return EvidenceSpan(**kwargs)


def _build_provenance(
    idx: int,
    source_ids: list[str],
    timestamp: datetime,
    action: ProvenanceAction = ProvenanceAction.CREATED,
    agent_type: ProvenanceAgentType = ProvenanceAgentType.PIPELINE_STAGE,
) -> ProvenanceRecord:
    return ProvenanceRecord(
        provenance_id=f"prov_{idx:03d}",
        action=action,
        agent_type=agent_type,
        agent_name=_AGENT_NAME,
        pipeline_stage=_PIPELINE_STAGE,
        pipeline_version=_PIPELINE_VERSION,
        timestamp=timestamp,
        notes=f"Source objects: {', '.join(source_ids)}",
    )


# ---------------------------------------------------------------------------
# EvidenceRecord generation
# ---------------------------------------------------------------------------


def _build_evidence_for_fact(
    fact: ExtractedFact,
    sro: StructuredResearchObject,
    timestamp: datetime,
    provenance_ref: str | None = None,
) -> EvidenceRecord:
    ev_type = _FACT_TO_EVIDENCE_TYPE.get(fact.fact_type, EvidenceType.DERIVED)
    source_text = fact.evidence_text or fact.value
    chunk_text = _lookup_chunk_text(sro, fact.chunk_id)
    char_start, char_end = _find_span_in_chunk(chunk_text or "", source_text)
    page = _lookup_page_from_chunk(sro, fact.chunk_id)
    has_location = fact.chunk_id is not None or fact.section_id is not None or page is not None
    location = _build_span(
        chunk_id=fact.chunk_id,
        section_id=fact.section_id,
        page=page,
        char_start=char_start,
        char_end=char_end,
        source_text_sha256=_compute_sha256(source_text) if has_location else None,
    ) if has_location else None
    return EvidenceRecord(
        evidence_id=f"ev_{fact.fact_id}",
        evidence_type=ev_type,
        source_text=source_text,
        location=location,
        data_source=DataSource.INFERRED,
        extraction_method=_get_extraction_method(sro, fact.chunk_id),
        confidence=fact.confidence,
        timestamp=timestamp,
        provenance_ref=provenance_ref,
    )


def _build_evidence_for_triple(
    triple: SemanticTriple,
    sro: StructuredResearchObject,
    timestamp: datetime,
    provenance_ref: str | None = None,
) -> EvidenceRecord:
    source_text = f"{triple.subject_text} {triple.predicate} {triple.object_text}"
    chunk_text = _lookup_chunk_text(sro, triple.chunk_id)
    char_start, char_end = _find_span_in_chunk(chunk_text or "", source_text)
    page = _lookup_page_from_chunk(sro, triple.chunk_id)
    has_location = triple.chunk_id is not None or page is not None
    location = _build_span(
        chunk_id=triple.chunk_id,
        page=page,
        char_start=char_start,
        char_end=char_end,
        source_text_sha256=_compute_sha256(source_text) if has_location else None,
    ) if has_location else None
    return EvidenceRecord(
        evidence_id=f"ev_{triple.triple_id}",
        evidence_type=EvidenceType.DERIVED,
        source_text=source_text,
        location=location,
        data_source=DataSource.INFERRED,
        extraction_method=_get_extraction_method(sro, triple.chunk_id),
        confidence=triple.confidence,
        timestamp=timestamp,
        provenance_ref=provenance_ref,
    )


def _build_evidence_for_claim(
    claim: SROCandidateClaim,
    sro: StructuredResearchObject,
    timestamp: datetime,
    provenance_ref: str | None = None,
) -> EvidenceRecord:
    ev_type = _CLAIM_TO_EVIDENCE_TYPE.get(claim.claim_type, EvidenceType.PARAPHRASE)
    chunk_text = _lookup_chunk_text(sro, claim.chunk_id)
    char_start, char_end = _find_span_in_chunk(chunk_text or "", claim.sentence)
    page = _lookup_page_from_chunk(sro, claim.chunk_id)
    resolved_page = page or claim.page
    has_location = claim.chunk_id is not None or claim.section_id is not None or resolved_page is not None
    location = _build_span(
        chunk_id=claim.chunk_id,
        section_id=claim.section_id,
        page=resolved_page,
        char_start=char_start,
        char_end=char_end,
        source_text_sha256=_compute_sha256(claim.sentence) if has_location else None,
    ) if has_location else None
    return EvidenceRecord(
        evidence_id=f"ev_{claim.claim_id}",
        evidence_type=ev_type,
        source_text=claim.sentence,
        location=location,
        data_source=DataSource.INFERRED,
        extraction_method=_get_extraction_method(sro, claim.chunk_id),
        confidence=claim.confidence,
        timestamp=timestamp,
        provenance_ref=provenance_ref,
    )


# ---------------------------------------------------------------------------
# EvidenceChain generation
# ---------------------------------------------------------------------------


def _build_claim_fact_triple_chains(
    sro: StructuredResearchObject,
    fact_records: dict[str, EvidenceRecord],
    triple_records: dict[str, EvidenceRecord],
    claim_records: dict[str, EvidenceRecord],
    timestamp: datetime,
) -> list[EvidenceChain]:
    """Claim → Fact → Triple chains."""
    chains: list[EvidenceChain] = []

    for claim in sro.candidate_claims:
        claim_ev = claim_records.get(f"ev_{claim.claim_id}")
        if claim_ev is None:
            continue

        # Find facts in the same chunk/section
        linked_facts = [
            ev for ev in fact_records.values()
            if ev.location and ev.location.chunk_id == claim.chunk_id
        ]
        # Find triples referencing those facts
        linked_triples: list[EvidenceRecord] = []
        triple_ev_ids_used: set[str] = set()
        for fact_ev in linked_facts:
            for t in sro.entities:  # triples don't reference fact_ids directly
                pass
            # Triples with evidence_ids containing the fact_id
            for triple_id, triple_ev in triple_records.items():
                if triple_id in triple_ev_ids_used:
                    continue
                # Check if any linked fact source overlaps with triple evidence_ids
                triple = next(
                    (t for t in (
                        sro.candidate_claims  # can't iterate triples easily from SRO
                    ) if False),
                    None,
                )

        # Simplified: link facts and triples in same chunk
        chain_records: list[EvidenceRecord] = [claim_ev]
        chain_records.extend(linked_facts)
        for triple_id, triple_ev in triple_records.items():
            if triple_ev.location and triple_ev.location.chunk_id == claim.chunk_id:
                if triple_ev not in chain_records:
                    chain_records.append(triple_ev)

        if len(chain_records) > 1:
            confs = [r.confidence for r in chain_records]
            chains.append(EvidenceChain(
                target_id=claim.claim_id,
                target_type=EvidenceTargetType.CLAIM,
                chain=chain_records,
                aggregate_confidence=min(confs),
                aggregation_method=AggregationMethod.MINIMUM,
            ))

    return chains


def _build_fact_triple_chains(
    fact_records: dict[str, EvidenceRecord],
    triple_records: dict[str, EvidenceRecord],
    triple_result: TripleExtractionResult,
    timestamp: datetime,
) -> list[EvidenceChain]:
    """Fact → Triple chains."""
    chains: list[EvidenceChain] = []

    for triple in triple_result.triples:
        # Find facts referenced by the triple's evidence_ids
        linked_facts = [
            ev_rec for ev_id, ev_rec in fact_records.items()
            if any(eid.startswith("fact_") and f"ev_{eid}" == ev_id
                   for eid in triple.evidence_ids)
        ]
        if not linked_facts:
            continue

        triple_ev = triple_records.get(f"ev_{triple.triple_id}")
        if triple_ev is None:
            continue

        for fact_ev in linked_facts:
            chain_records = [fact_ev, triple_ev]
            confs = [r.confidence for r in chain_records]
            chains.append(EvidenceChain(
                target_id=fact_ev.evidence_id,
                target_type=EvidenceTargetType.CLAIM,
                chain=chain_records,
                aggregate_confidence=min(confs),
                aggregation_method=AggregationMethod.MINIMUM,
            ))

    return chains


def _build_entity_triple_chains(
    sro: StructuredResearchObject,
    triple_records: dict[str, EvidenceRecord],
    triple_result: TripleExtractionResult,
    timestamp: datetime,
) -> list[EvidenceChain]:
    """Entity → Triple chains."""
    chains: list[EvidenceChain] = []

    entity_ids = {e.entity_id for e in sro.entities}

    for triple in triple_result.triples:
        if triple.subject_id not in entity_ids and triple.object_id not in entity_ids:
            continue

        triple_ev = triple_records.get(f"ev_{triple.triple_id}")
        if triple_ev is None:
            continue

        # Determine which entity this chain is for
        target_id = (
            triple.subject_id if triple.subject_id in entity_ids
            else triple.object_id
        )

        chains.append(EvidenceChain(
            target_id=target_id,
            target_type=EvidenceTargetType.ENTITY,
            chain=[triple_ev],
            aggregate_confidence=triple.confidence,
            aggregation_method=AggregationMethod.MINIMUM,
        ))

    return chains


# ---------------------------------------------------------------------------
# Coverage computation
# ---------------------------------------------------------------------------


def _compute_coverage(
    sro: StructuredResearchObject,
    claim_records: dict[str, EvidenceRecord],
    entity_ids_with_evidence: set[str],
) -> EvidenceCoverage:
    total_claims = len(sro.candidate_claims)
    claims_with_ev = sum(
        1 for c in sro.candidate_claims
        if f"ev_{c.claim_id}" in claim_records
    )
    total_entities = len(sro.entities)
    entities_with_ev = len(
        [e for e in sro.entities if e.entity_id in entity_ids_with_evidence]
    )

    return EvidenceCoverage(
        total_claims=total_claims,
        claims_with_evidence=claims_with_ev,
        claims_evidence_rate=round(
            claims_with_ev / total_claims if total_claims > 0 else 0.0, 4
        ),
        total_entities=total_entities,
        entities_with_evidence=entities_with_ev,
        entities_evidence_rate=round(
            entities_with_ev / total_entities if total_entities > 0 else 0.0, 4
        ),
        total_citations=len(sro.citations),
        citations_with_intent_evidence=sum(
            1 for c in sro.citations if c.citation_intent is not None
        ),
        citation_intent_evidence_rate=round(
            sum(1 for c in sro.citations if c.citation_intent is not None)
            / len(sro.citations) if sro.citations else 0.0, 4
        ),
        total_references=len(sro.references),
        references_with_resolution_evidence=sum(
            1 for r in sro.references
            if r.resolution_status.value == "resolved"
        ),
        reference_resolution_evidence_rate=round(
            sum(1 for r in sro.references
                if r.resolution_status.value == "resolved")
            / len(sro.references) if sro.references else 0.0, 4
        ),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_evidence(
    sro: StructuredResearchObject,
    fact_result: FactExtractionResult | None = None,
    triple_result: TripleExtractionResult | None = None,
) -> EvidenceBuildResult:
    """Build evidence records, chains, and provenance from an SRO.

    Parameters
    ----------
    sro:
        The structured research object.
    fact_result:
        Pre-extracted facts. If ``None``, facts are extracted internally.
    triple_result:
        Pre-extracted semantic triples. If ``None``, triples are extracted
        internally.

    Returns
    -------
    EvidenceBuildResult
        Container with evidence records, chains, provenance, and coverage.
    """
    from researchmind.understanding.fact_extractor import extract_facts
    from researchmind.understanding.triple_extractor import extract_triples

    if fact_result is None:
        fact_result = extract_facts(sro)
    if triple_result is None:
        triple_result = extract_triples(sro, fact_result)

    timestamp = datetime.now(timezone.utc)
    evidence_records: list[EvidenceRecord] = []
    provenance_records: list[ProvenanceRecord] = []
    prov_counter: list[int] = [0]

    # --- ProvenanceRecords (created first so evidence records can link) ---
    fact_prov_id: str | None = None
    if fact_result.facts:
        prov_counter[0] += 1
        prov = _build_provenance(
            prov_counter[0],
            [f.fact_id for f in fact_result.facts],
            timestamp,
        )
        provenance_records.append(prov)
        fact_prov_id = prov.provenance_id

    triple_prov_id: str | None = None
    if triple_result.triples:
        prov_counter[0] += 1
        prov = _build_provenance(
            prov_counter[0],
            [t.triple_id for t in triple_result.triples],
            timestamp,
        )
        provenance_records.append(prov)
        triple_prov_id = prov.provenance_id

    claim_prov_id: str | None = None
    if sro.candidate_claims:
        prov_counter[0] += 1
        prov = _build_provenance(
            prov_counter[0],
            [c.claim_id for c in sro.candidate_claims],
            timestamp,
        )
        provenance_records.append(prov)
        claim_prov_id = prov.provenance_id

    # --- EvidenceRecords from facts ---
    fact_records: dict[str, EvidenceRecord] = {}
    for fact in fact_result.facts:
        ev = _build_evidence_for_fact(fact, sro, timestamp, fact_prov_id)
        evidence_records.append(ev)
        fact_records[ev.evidence_id] = ev

    # --- EvidenceRecords from triples ---
    triple_records: dict[str, EvidenceRecord] = {}
    for triple in triple_result.triples:
        ev = _build_evidence_for_triple(triple, sro, timestamp, triple_prov_id)
        evidence_records.append(ev)
        triple_records[ev.evidence_id] = ev

    # --- EvidenceRecords from claims ---
    claim_records: dict[str, EvidenceRecord] = {}
    for claim in sro.candidate_claims:
        ev = _build_evidence_for_claim(claim, sro, timestamp, claim_prov_id)
        evidence_records.append(ev)
        claim_records[ev.evidence_id] = ev

    # --- EvidenceChains ---
    evidence_chains: list[EvidenceChain] = []

    # Claim → Fact → Triple
    cft_chains = _build_claim_fact_triple_chains(
        sro, fact_records, triple_records, claim_records, timestamp,
    )
    evidence_chains.extend(cft_chains)

    # Fact → Triple
    ft_chains = _build_fact_triple_chains(
        fact_records, triple_records, triple_result, timestamp,
    )
    evidence_chains.extend(ft_chains)

    # Entity → Triple
    et_chains = _build_entity_triple_chains(
        sro, triple_records, triple_result, timestamp,
    )
    evidence_chains.extend(et_chains)

    # --- Coverage ---
    entity_ids_with_evidence = {
        t.subject_id for chain in et_chains for t in triple_result.triples
        if f"ev_{t.triple_id}" in triple_records
        and (t.subject_id in {e.entity_id for e in sro.entities}
             or t.object_id in {e.entity_id for e in sro.entities})
    }
    coverage = _compute_coverage(
        sro, claim_records, entity_ids_with_evidence,
    )

    logger.info(
        "Evidence build complete: %d records, %d chains, %d provenances",
        len(evidence_records),
        len(evidence_chains),
        len(provenance_records),
    )

    return EvidenceBuildResult(
        evidence_records=evidence_records,
        evidence_chains=evidence_chains,
        provenance_records=provenance_records,
        coverage=coverage,
        total_facts=len(fact_result.facts),
        facts_with_evidence=len(fact_records),
        total_triples=len(triple_result.triples),
        triples_with_evidence=len(triple_records),
    )
