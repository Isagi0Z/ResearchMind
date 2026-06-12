"""Traceability Verifier — enforce evidence-to-document traceability.

Every finding in a review must be traceable to source evidence
through evidence_ids, source_document_ids, and trace chains.
"""

from __future__ import annotations

from typing import Any

from researchmind.synthesis.models import ReviewResult

_TRACE_REQUIRED_FINDING_TYPES: set[str] = {"contradiction", "consensus", "relation"}

_GAP_FINDING_TYPES: set[str] = {"gap"}


def _get_documents(corpus: Any) -> list[Any]:
    if hasattr(corpus, "get_documents"):
        try:
            return corpus.get_documents()
        except Exception:
            return []
    docs = getattr(corpus, "documents", None)
    if isinstance(docs, list):
        return docs
    return []


def _build_doc_lookup(corpus: Any) -> dict[str, Any] | None:
    if corpus is None:
        return None
    lookup: dict[str, Any] = {}
    docs = _get_documents(corpus)
    for d in docs:
        if d is None:
            continue
        meta = getattr(d, "meta", None)
        did = getattr(meta, "ruo_id", "") if meta else ""
        if did:
            lookup[did] = d
    return lookup


class TraceabilityVerifier:
    """Verifies the traceability contract for a ReviewResult."""

    def __init__(self) -> None:
        pass

    def verify_review(
        self,
        review: ReviewResult,
        corpus: Any,
        chunk_index: dict[str, str] | None = None,
    ) -> tuple[bool, list[str]]:
        """Verify traceability of every finding in a review.

        Parameters
        ----------
        review : ReviewResult
            The completed review to verify.
        corpus : CorpusManager or similar
            Corpus containing source documents.
        chunk_index : dict or None
            Optional mapping of chunk_id to document_id for chunk validation.

        Returns
        -------
        tuple[bool, list[str]]
            (is_valid, list_of_warnings).
        """
        warnings: list[str] = []
        findings_checked = 0
        findings_failed = 0

        doc_lookup = _build_doc_lookup(corpus)

        sections = getattr(review, "sections", None) or []

        for section in sections:
            findings = getattr(section, "findings", None) or []
            for finding in findings:
                finding_id = getattr(finding, "finding_id", "") or "unknown"
                finding_type = getattr(finding, "finding_type", "") or ""
                evidence_ids = getattr(finding, "evidence_ids", None) or []
                source_doc_ids = getattr(finding, "source_document_ids", None) or []
                trace = getattr(finding, "trace", None) or []

                is_gap = finding_type in _GAP_FINDING_TYPES

                if is_gap:
                    continue

                findings_checked += 1
                finding_failed = False

                if not evidence_ids:
                    warnings.append(
                        f"Finding {finding_id} missing evidence_ids"
                    )
                    finding_failed = True

                if len(evidence_ids) != len(set(evidence_ids)):
                    warnings.append(
                        f"Finding {finding_id} has duplicate evidence_ids"
                    )

                if not source_doc_ids:
                    warnings.append(
                        f"Finding {finding_id} missing source documents"
                    )
                    finding_failed = True
                elif doc_lookup is not None:
                    for doc_id in source_doc_ids:
                        if doc_id not in doc_lookup:
                            warnings.append(
                                f"Finding {finding_id} references "
                                f"unknown document {doc_id}"
                            )
                            finding_failed = True

                if finding_type in _TRACE_REQUIRED_FINDING_TYPES:
                    if not trace:
                        warnings.append(
                            f"Finding {finding_id} of type "
                            f"'{finding_type}' requires non-empty trace"
                        )
                        finding_failed = True
                    else:
                        for entry in trace:
                            if not isinstance(entry, str) or not entry.strip():
                                warnings.append(
                                    f"Finding {finding_id} has "
                                    f"invalid trace entry"
                                )
                                finding_failed = True
                                break

                if chunk_index is not None:
                    for tid in trace:
                        if tid not in chunk_index:
                            warnings.append(
                                f"Missing chunk {tid}"
                            )

                if finding_failed:
                    findings_failed += 1

        stats = {
            "findings_checked": findings_checked,
            "findings_failed": findings_failed,
            "warnings": len(warnings),
        }

        review_meta = getattr(review, "metadata", None)
        if isinstance(review_meta, dict):
            review_meta["traceability"] = stats

        is_valid = findings_failed == 0
        return is_valid, warnings


def verify_review(
    review: ReviewResult,
    corpus: Any,
    chunk_index: dict[str, str] | None = None,
) -> tuple[bool, list[str]]:
    """Convenience helper for traceability verification.

    See :meth:`TraceabilityVerifier.verify_review`.
    """
    return TraceabilityVerifier().verify_review(
        review=review,
        corpus=corpus,
        chunk_index=chunk_index,
    )
