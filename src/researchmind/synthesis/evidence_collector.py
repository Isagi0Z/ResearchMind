"""Evidence Collector — gather evidence from corpus documents.

Extracts claims, triples, and evidence records from documents
associated with each theme and packages them into EvidenceBundle lists.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from researchmind.query.models import AggregatedEvidence
from researchmind.synthesis.models import EvidenceBundle, ThemeCluster, _generate_id


def _get_documents(corpus: Any) -> list[Any]:
    """Extract document list from corpus regardless of access pattern."""
    if hasattr(corpus, "get_documents"):
        try:
            return corpus.get_documents()
        except Exception:
            return []
    docs = getattr(corpus, "documents", None)
    if isinstance(docs, list):
        return docs
    return []


def _extract_claims_as_evidence(doc: Any) -> list[AggregatedEvidence]:
    """Convert document claims into AggregatedEvidence items."""
    results: list[AggregatedEvidence] = []
    claims = getattr(doc, "claims", None)
    if not isinstance(claims, list):
        return results
    meta = getattr(doc, "meta", None)
    doc_id = getattr(meta, "ruo_id", "") if meta else ""
    doc_title = ""
    header = getattr(doc, "header", None)
    if header:
        doc_title = getattr(header, "title", "") or ""
    for claim in claims:
        cid = getattr(claim, "claim_id", "") or ""
        sentence = getattr(claim, "sentence", "") or ""
        confidence = getattr(claim, "confidence", 0.0) or 0.0
        if not cid and not sentence:
            continue
        confidence = max(0.0, min(1.0, float(confidence)))
        trace = [cid] if cid else []
        evidence = AggregatedEvidence(
            evidence_id=f"claim_{cid}" if cid else _generate_id("ev", doc_id, sentence[:64]),
            source_text=sentence,
            confidence=confidence,
            source_document_id=doc_id,
            source_document_title=doc_title,
            evidence_type="claim",
            source_engine="evidence_collector",
            trace=trace,
        )
        results.append(evidence)
    return results


def _extract_triples_as_evidence(doc: Any) -> list[AggregatedEvidence]:
    """Convert document triples into AggregatedEvidence items."""
    results: list[AggregatedEvidence] = []
    triples = getattr(doc, "triples", None)
    if not isinstance(triples, list):
        return results
    meta = getattr(doc, "meta", None)
    doc_id = getattr(meta, "ruo_id", "") if meta else ""
    doc_title = ""
    header = getattr(doc, "header", None)
    if header:
        doc_title = getattr(header, "title", "") or ""
    for triple in triples:
        tid = getattr(triple, "triple_id", "") or ""
        subject = getattr(triple, "subject_text", "") or ""
        predicate = getattr(triple, "predicate", "") or ""
        obj = getattr(triple, "object_text", "") or ""
        confidence = getattr(triple, "confidence", 0.0) or 0.0
        if not tid and not subject and not predicate and not obj:
            continue
        confidence = max(0.0, min(1.0, float(confidence)))
        source_text = f"{subject} {predicate} {obj}".strip()
        trace = [tid] if tid else []
        evidence = AggregatedEvidence(
            evidence_id=f"triple_{tid}" if tid else _generate_id("ev", doc_id, source_text[:64]),
            source_text=source_text,
            confidence=confidence,
            source_document_id=doc_id,
            source_document_title=doc_title,
            evidence_type="triple",
            source_engine="evidence_collector",
            trace=trace,
        )
        results.append(evidence)
    return results


def _extract_evidence_records(doc: Any) -> list[AggregatedEvidence]:
    """Extract evidence records from document if available."""
    results: list[AggregatedEvidence] = []
    records = getattr(doc, "evidence_records", None)
    if not isinstance(records, list):
        return results
    meta = getattr(doc, "meta", None)
    doc_id = getattr(meta, "ruo_id", "") if meta else ""
    doc_title = ""
    header = getattr(doc, "header", None)
    if header:
        doc_title = getattr(header, "title", "") or ""
    for record in records:
        eid = getattr(record, "evidence_id", "") or ""
        source_text = getattr(record, "source_text", "") or ""
        confidence = getattr(record, "confidence", 0.0) or 0.0
        if not eid and not source_text:
            continue
        confidence = max(0.0, min(1.0, float(confidence)))
        etype = getattr(record, "evidence_type", None)
        etype_str = etype.value if hasattr(etype, "value") else str(etype) if etype else ""
        trace = [eid] if eid else []
        evidence = AggregatedEvidence(
            evidence_id=f"rec_{eid}" if eid else _generate_id("ev", doc_id, source_text[:64]),
            source_text=source_text,
            confidence=confidence,
            source_document_id=doc_id,
            source_document_title=doc_title,
            evidence_type=etype_str or "evidence_record",
            source_engine="evidence_collector",
            trace=trace,
        )
        results.append(evidence)
    return results


def _extract_metadata_evidence(doc: Any) -> list[AggregatedEvidence]:
    """Extract AggregatedEvidence items from document metadata if present."""
    results: list[AggregatedEvidence] = []
    meta = getattr(doc, "meta", None)
    doc_id = getattr(meta, "ruo_id", "") if meta else ""
    aggregated = getattr(doc, "aggregated_evidence", None)
    if isinstance(aggregated, list):
        for item in aggregated:
            if isinstance(item, AggregatedEvidence):
                if not item.source_document_id:
                    item.source_document_id = doc_id
                results.append(item)
            elif isinstance(item, dict):
                try:
                    ae = AggregatedEvidence(**item)
                    if not ae.source_document_id:
                        ae.source_document_id = doc_id
                    results.append(ae)
                except Exception:
                    pass
    return results


def _collect_document_evidence(doc: Any) -> list[AggregatedEvidence]:
    """Collect all evidence items from a single document."""
    results: list[AggregatedEvidence] = []
    results.extend(_extract_claims_as_evidence(doc))
    results.extend(_extract_triples_as_evidence(doc))
    results.extend(_extract_evidence_records(doc))
    results.extend(_extract_metadata_evidence(doc))
    return results


def _match_theme(
    evidence: AggregatedEvidence,
    theme: ThemeCluster,
) -> bool:
    """Check if evidence matches a theme via entity, text, or metadata overlap."""
    text = (evidence.source_text or "").lower()
    label_lower = (theme.label or "").lower()

    if label_lower and label_lower in text:
        return True

    for entity_label in theme.entity_labels:
        el = (entity_label or "").lower()
        if el and el in text:
            return True

    for eid in theme.entities:
        eid_lower = eid.lower()
        if eid_lower and (eid_lower in text or eid_lower in evidence.evidence_id.lower()):
            return True

    for eid in theme.entity_cluster_ids:
        eid_lower = eid.lower()
        if eid_lower and (eid_lower in text or eid_lower in evidence.evidence_id.lower()):
            return True

    if evidence.metadata:
        for val in evidence.metadata.values():
            if isinstance(val, str) and label_lower and label_lower in val.lower():
                return True
            if isinstance(val, list):
                for v in val:
                    if isinstance(v, str) and label_lower and label_lower in v.lower():
                        return True

    doc_title = (evidence.source_document_title or "").lower()
    if label_lower and label_lower in doc_title:
        return True

    return False


def _deduplicate(items: list[AggregatedEvidence]) -> list[AggregatedEvidence]:
    """Deduplicate evidence items. Keep highest confidence on conflict."""
    by_id: dict[str, AggregatedEvidence] = {}
    by_text: dict[str, list[AggregatedEvidence]] = defaultdict(list)
    for item in items:
        eid = item.evidence_id
        if eid:
            existing = by_id.get(eid)
            if existing is None or item.confidence > existing.confidence:
                by_id[eid] = item
        else:
            norm = " ".join(item.source_text.split())
            by_text[norm].append(item)

    result: list[AggregatedEvidence] = list(by_id.values())

    for norm, group in by_text.items():
        if not group:
            continue
        best = max(group, key=lambda x: (x.confidence, len(x.trace), x.evidence_id))
        existing_ids = {e.evidence_id for e in result if e.evidence_id}
        if best.evidence_id and best.evidence_id in existing_ids:
            continue
        result.append(best)

    return result


def _normalize_evidence_text(text: str) -> str:
    """Normalize whitespace for comparison."""
    return " ".join(text.split())


class EvidenceCollector:
    """Collects evidence from corpus documents for each theme."""

    def __init__(self) -> None:
        pass

    def collect(
        self,
        corpus: Any,
        graph: Any,
        themes: list[ThemeCluster],
        max_evidence_per_theme: int = 100,
        min_confidence: float = 0.0,
    ) -> list[EvidenceBundle]:
        """Collect evidence for each theme from the corpus.

        Parameters
        ----------
        corpus : CorpusManager or similar
            Corpus containing documents.
        graph : CorpusGraphResult or None
            Graph result for relationship data.
        themes : list[ThemeCluster]
            Themes to collect evidence for.
        max_evidence_per_theme : int
            Maximum evidence items per theme bundle.
        min_confidence : float
            Minimum confidence threshold.

        Returns
        -------
        list[EvidenceBundle]
            One bundle per theme with collected evidence.
        """
        if not themes:
            return []

        documents = _get_documents(corpus)

        doc_map: dict[str, Any] = {}
        for d in documents:
            meta = getattr(d, "meta", None)
            did = getattr(meta, "ruo_id", "") if meta else ""
            if did:
                doc_map[did] = d

        doc_cache: dict[str, list[AggregatedEvidence]] = {}

        def _get_doc_evidence(doc_id: str) -> list[AggregatedEvidence]:
            if doc_id not in doc_cache:
                doc = doc_map.get(doc_id)
                if doc is not None:
                    doc_cache[doc_id] = _collect_document_evidence(doc)
                else:
                    doc_cache[doc_id] = []
            return doc_cache[doc_id]

        bundles: list[EvidenceBundle] = []
        for theme in themes:
            all_evidence: list[AggregatedEvidence] = []

            doc_ids = list(theme.document_ids or [])
            doc_ids.extend(theme.documents or [])

            seen_docs: set[str] = set()
            for did in doc_ids:
                if did in seen_docs:
                    continue
                seen_docs.add(did)
                ev = _get_doc_evidence(did)
                all_evidence.extend(ev)

            all_evidence = _deduplicate(all_evidence)

            filtered = [e for e in all_evidence if _match_theme(e, theme)]

            if min_confidence > 0.0:
                filtered = [e for e in filtered if e.confidence >= min_confidence]

            filtered = _deduplicate(filtered)

            filtered.sort(key=lambda e: (-e.confidence, -len(e.trace), e.evidence_id))

            capped = filtered[:max_evidence_per_theme]

            source_docs: set[str] = set()
            source_entities: set[str] = set()
            for e in capped:
                if e.source_document_id:
                    source_docs.add(e.source_document_id)
                for ent in theme.entity_cluster_ids:
                    source_entities.add(ent)

            if capped:
                agg_conf = sum(e.confidence for e in capped) / len(capped)
            else:
                agg_conf = 0.0

            bundle_id = _generate_id(
                "bnd",
                theme.cluster_id or theme.label,
            )

            bundle = EvidenceBundle(
                bundle_id=bundle_id,
                theme=theme.label,
                evidence_items=capped,
                source_document_ids=sorted(source_docs),
                source_entities=sorted(source_entities),
                aggregate_confidence=max(0.0, min(1.0, agg_conf)),
                evidence_count=len(capped),
                metadata={
                    "theme_label": theme.label,
                    "theme_type": theme.theme_type,
                    "document_count": len(source_docs),
                },
            )
            bundles.append(bundle)

        return bundles


def collect_evidence(
    corpus: Any,
    graph: Any,
    themes: list[ThemeCluster],
    max_evidence_per_theme: int = 100,
    min_confidence: float = 0.0,
) -> list[EvidenceBundle]:
    """Convenience helper for evidence collection.

    See :meth:`EvidenceCollector.collect`.
    """
    return EvidenceCollector().collect(
        corpus=corpus,
        graph=graph,
        themes=themes,
        max_evidence_per_theme=max_evidence_per_theme,
        min_confidence=min_confidence,
    )
