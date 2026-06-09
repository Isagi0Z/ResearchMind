from typing import Optional
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from researchmind.models.enums import ResolutionSource, ResolutionStatus
from researchmind.models.intermediates import CrossRefConfig, RawReference
from researchmind.structuring.reference_resolver import (
    _normalise_doi,
    _score_crossref_candidate,
    resolve_references,
)


def _ref(
    title: str = "",
    authors: Optional[list[str]] = None,
    year: str = "",
    raw_text: str = "",
    doi: Optional[str] = None,
    venue: str = "",
) -> RawReference:
    return RawReference(
        title=title,
        authors=authors or [],
        year=year,
        raw_text=raw_text,
        doi=doi,
        venue=venue,
    )


def _crossref_item(
    doi: str = "10.1234/test",
    title: str = "Test Title",
    family: str = "Author",
    year: int = 2020,
) -> dict:
    return {
        "DOI": doi,
        "title": [title],
        "author": [{"family": family}],
        "issued": {"date-parts": [[year]]},
        "score": 100,
    }


def _successful_response(items: list[dict]) -> httpx.Response:
    return httpx.Response(
        200,
        json={"status": "ok", "message": {"items": items}},
        request=httpx.Request("GET", "https://api.crossref.org/works"),
    )


# ---------------------------------------------------------------------------
# Pre-resolution via GROBID DOI
# ---------------------------------------------------------------------------


def test_grobid_doi_pre_resolved() -> None:
    """A raw reference with a DOI should resolve immediately without CrossRef."""
    raw_refs = [_ref(title="Test", authors=["Author"], doi="10.1234/existing")]
    config = CrossRefConfig(enabled=True)

    results = resolve_references(raw_refs, config)

    assert len(results) == 1
    assert results[0].resolution_status == ResolutionStatus.RESOLVED
    assert results[0].doi == "10.1234/existing"
    assert results[0].resolution_source == ResolutionSource.GROBID_CONSOLIDATION


# ---------------------------------------------------------------------------
# Successful CrossRef resolution
# ---------------------------------------------------------------------------


def test_crossref_successful_resolution() -> None:
    """A well-matching CrossRef candidate produces RESOLVED status."""
    raw_refs = [
        _ref(
            title="Attention Is All You Need",
            authors=["Vaswani, Ashish"],
            year="2017",
            raw_text="Vaswani, A. et al. Attention Is All You Need. 2017.",
        )
    ]
    config = CrossRefConfig(enabled=True, mailto="test@example.com")
    item = _crossref_item(
        doi="10.1234/attention",
        title="Attention Is All You Need",
        family="Vaswani",
        year=2017,
    )

    with patch(
        "researchmind.structuring.reference_resolver._crossref_request",
        new_callable=AsyncMock,
    ) as mock_req:
        mock_req.return_value = _successful_response([item])
        results = resolve_references(raw_refs, config)

    assert len(results) == 1
    assert results[0].resolution_status == ResolutionStatus.RESOLVED
    assert results[0].doi == "10.1234/attention"
    assert results[0].resolution_source == ResolutionSource.CROSSREF_LOOKUP
    assert mock_req.call_count == 1


# ---------------------------------------------------------------------------
# Ambiguous resolution
# ---------------------------------------------------------------------------


def test_crossref_ambiguous_resolution() -> None:
    """A moderate-scoring candidate between resolve and ambiguous thresholds yields AMBIGUOUS."""
    raw_refs = [
        _ref(
            title="Machine Learning",
            authors=["Author"],
            year="2020",
            raw_text="Some reference text.",
        )
    ]
    config = CrossRefConfig(
        enabled=True, mailto="test@example.com",
        resolve_threshold=0.90, ambiguous_threshold=0.50,
    )
    item = _crossref_item(
        doi="10.1234/ml",
        title="Machine Learning Fundamentals",
        family="Writer",
        year=2021,
    )

    with patch(
        "researchmind.structuring.reference_resolver._crossref_request",
        new_callable=AsyncMock,
    ) as mock_req:
        mock_req.return_value = _successful_response([item])
        results = resolve_references(raw_refs, config)

    assert len(results) == 1
    assert results[0].resolution_status == ResolutionStatus.AMBIGUOUS
    assert results[0].doi is not None


# ---------------------------------------------------------------------------
# Unresolved — no candidates
# ---------------------------------------------------------------------------


def test_crossref_unresolved_no_candidates() -> None:
    """Empty CrossRef items list yields UNRESOLVED."""
    raw_refs = [_ref(title="Obscure", authors=["Author"], raw_text="text")]
    config = CrossRefConfig(enabled=True, mailto="test@example.com")

    with patch(
        "researchmind.structuring.reference_resolver._crossref_request",
        new_callable=AsyncMock,
    ) as mock_req:
        mock_req.return_value = _successful_response([])
        results = resolve_references(raw_refs, config)

    assert len(results) == 1
    assert results[0].resolution_status == ResolutionStatus.UNRESOLVED
    assert results[0].doi is None


# ---------------------------------------------------------------------------
# Unresolved — all candidates below ambiguous threshold
# ---------------------------------------------------------------------------


def test_crossref_unresolved_below_threshold() -> None:
    """Candidates that score below ambiguous_threshold yield UNRESOLVED."""
    raw_refs = [
        _ref(
            title="Specific Uncommon Topic",
            authors=["UniqueAuthor"],
            year="2022",
            raw_text="Unique Author. Specific Uncommon Topic. 2022.",
        )
    ]
    config = CrossRefConfig(
        enabled=True, mailto="test@example.com",
        ambiguous_threshold=0.80,
    )
    item = _crossref_item(
        doi="10.1234/other",
        title="Completely Different Topic",
        family="Other",
        year=2000,
    )

    with patch(
        "researchmind.structuring.reference_resolver._crossref_request",
        new_callable=AsyncMock,
    ) as mock_req:
        mock_req.return_value = _successful_response([item])
        results = resolve_references(raw_refs, config)

    assert len(results) == 1
    assert results[0].resolution_status == ResolutionStatus.UNRESOLVED
    assert results[0].doi is None


# ---------------------------------------------------------------------------
# Candidate ranking: higher-scored item selected over lower-scored
# ---------------------------------------------------------------------------


def test_crossref_ranking_prefers_best_candidate() -> None:
    """When CrossRef returns multiple items, the highest-scored one is selected."""
    raw_refs = [
        _ref(
            title="Attention Is All You Need",
            authors=["Vaswani, Ashish"],
            year="2017",
            raw_text="Vaswani, A. Attention Is All You Need. 2017.",
        )
    ]
    config = CrossRefConfig(enabled=True, mailto="test@example.com")

    item_low = _crossref_item(
        doi="10.1234/wrong",
        title="Unrelated Topic",
        family="Other",
        year=2000,
    )
    item_high = _crossref_item(
        doi="10.1234/correct",
        title="Attention Is All You Need",
        family="Vaswani",
        year=2017,
    )

    with patch(
        "researchmind.structuring.reference_resolver._crossref_request",
        new_callable=AsyncMock,
    ) as mock_req:
        mock_req.return_value = _successful_response([item_low, item_high])
        results = resolve_references(raw_refs, config)

    assert len(results) == 1
    assert results[0].resolution_status == ResolutionStatus.RESOLVED
    assert results[0].doi == "10.1234/correct"


# ---------------------------------------------------------------------------
# Retry: transient error then success
# ---------------------------------------------------------------------------


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_crossref_retry_then_succeeds() -> None:
    """A transient network error triggers retry; subsequent success resolves."""
    raw_refs = [
        _ref(
            title="Test Title",
            authors=["Author"],
            year="2020",
            raw_text="Test text.",
        )
    ]
    config = CrossRefConfig(
        enabled=True, mailto="test@example.com",
        retry_attempts=2, retry_backoff_seconds=0.01,
    )
    item = _crossref_item(
        doi="10.1234/test",
        title="Test Title",
        family="Author",
        year=2020,
    )

    success_resp = _successful_response([item])

    with patch(
        "httpx.AsyncClient.get",
        new_callable=AsyncMock,
    ) as mock_get:
        mock_get.side_effect = [
            httpx.ConnectError("Connection refused"),
            success_resp,
        ]
        results = resolve_references(raw_refs, config)

    assert len(results) == 1
    assert results[0].resolution_status == ResolutionStatus.RESOLVED
    assert results[0].doi == "10.1234/test"


# ---------------------------------------------------------------------------
# Retry exhausted
# ---------------------------------------------------------------------------


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_crossref_retry_exhausted() -> None:
    """All retry attempts fail → UNRESOLVED."""
    raw_refs = [
        _ref(
            title="Test Title",
            authors=["Author"],
            year="2020",
            raw_text="Test text.",
        )
    ]
    config = CrossRefConfig(
        enabled=True, mailto="test@example.com",
        retry_attempts=2, retry_backoff_seconds=0.01,
    )

    with patch(
        "httpx.AsyncClient.get",
        new_callable=AsyncMock,
    ) as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection refused")
        results = resolve_references(raw_refs, config)

    assert len(results) == 1
    assert results[0].resolution_status == ResolutionStatus.UNRESOLVED
    assert mock_get.call_count == 3  # initial + 2 retries


# ---------------------------------------------------------------------------
# Threshold configuration
# ---------------------------------------------------------------------------


def test_crossref_low_resolve_threshold_resolves_more() -> None:
    """A low resolve_threshold allows marginal candidates to be RESOLVED."""
    raw_refs = [
        _ref(
            title="Deep Learning for Image Recognition",
            authors=["Author"],
            year="2020",
            raw_text="Some reference.",
        )
    ]
    item = _crossref_item(
        doi="10.1234/ml",
        title="Deep Reinforcement Learning Methods",
        family="Author",
        year=2020,
    )

    config_loose = CrossRefConfig(
        enabled=True, mailto="test@example.com",
        resolve_threshold=0.55, ambiguous_threshold=0.30,
    )
    config_strict = CrossRefConfig(
        enabled=True, mailto="test@example.com",
        resolve_threshold=0.90, ambiguous_threshold=0.80,
    )

    with patch(
        "researchmind.structuring.reference_resolver._crossref_request",
        new_callable=AsyncMock,
    ) as mock_req:
        mock_req.return_value = _successful_response([item])
        results_loose = resolve_references(raw_refs, config_loose)
        mock_req.reset_mock()
        mock_req.return_value = _successful_response([item])
        results_strict = resolve_references(raw_refs, config_strict)

    assert results_loose[0].resolution_status == ResolutionStatus.RESOLVED
    assert results_strict[0].resolution_status == ResolutionStatus.UNRESOLVED


# ---------------------------------------------------------------------------
# CrossRef disabled
# ---------------------------------------------------------------------------


def test_crossref_disabled() -> None:
    """When crossref is disabled, all refs needing lookup become UNRESOLVED."""
    raw_refs = [
        _ref(title="Test", authors=["Author"], year="2020", raw_text="text"),
        _ref(title="Test 2", authors=["Author"], year="2021", raw_text="text"),
    ]
    config = CrossRefConfig(enabled=False)

    results = resolve_references(raw_refs, config)

    assert len(results) == 2
    for ref in results:
        assert ref.resolution_status == ResolutionStatus.UNRESOLVED
        assert ref.doi is None


# ---------------------------------------------------------------------------
# Empty query skips lookup
# ---------------------------------------------------------------------------


def test_crossref_empty_query_skips() -> None:
    """A reference with no title, author, or raw_text is skipped without API call."""
    raw_refs = [_ref()]
    config = CrossRefConfig(enabled=True, mailto="test@example.com")

    with patch(
        "researchmind.structuring.reference_resolver._crossref_request",
        new_callable=AsyncMock,
    ) as mock_req:
        results = resolve_references(raw_refs, config)

    assert len(results) == 1
    assert results[0].resolution_status == ResolutionStatus.UNRESOLVED
    mock_req.assert_not_called()


# ---------------------------------------------------------------------------
# _normalise_doi
# ---------------------------------------------------------------------------


def test_normalise_doi_handles_url_encoded() -> None:
    assert _normalise_doi("10.1007%2F978-3-030-12345-6") == "10.1007/978-3-030-12345-6"


# ---------------------------------------------------------------------------
# _score_crossref_candidate
# ---------------------------------------------------------------------------


def test_score_crossref_candidate_perfect_match() -> None:
    ref = _ref(title="Exact Title", authors=["Smith, John"], year="2020")
    item = _crossref_item(
        doi="10.1234/exact",
        title="Exact Title",
        family="Smith",
        year=2020,
    )

    composite, title_sim, author_score, year_score, doi = \
        _score_crossref_candidate(ref, item)

    assert title_sim == 1.0
    assert author_score == 1.0
    assert year_score == 1.0
    assert doi == "10.1234/exact"
    assert composite == pytest.approx(1.0, abs=0.01)


def test_score_crossref_candidate_no_match() -> None:
    ref = _ref(title="One Topic", authors=["Smith, John"], year="2020")
    item = _crossref_item(
        doi="10.1234/other",
        title="Completely Different",
        family="Jones",
        year=1999,
    )

    composite, title_sim, author_score, year_score, doi = \
        _score_crossref_candidate(ref, item)

    assert title_sim < 0.3
    assert author_score == 0.0
    assert year_score == 0.0
    assert composite < 0.3
