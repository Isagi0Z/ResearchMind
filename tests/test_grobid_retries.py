from pathlib import Path
from unittest.mock import Mock, patch

import httpx

from researchmind.extraction.grobid_client import GrobidClient
from researchmind.models.enums import ExtractionMethod, ExtractionRoute
from researchmind.models.intermediates import GrobidConfig, IntakeResult, PipelineConfig, RawSection
from researchmind.pipeline import IngestionPipeline


MINIMAL_TEI = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>
    <fileDesc>
      <titleStmt><title type="main">Retry Test Paper</title></titleStmt>
    </fileDesc>
    <profileDesc><abstract><p>This is a small abstract for retry testing.</p></abstract></profileDesc>
  </teiHeader>
  <text>
    <body>
      <div><head>Introduction</head><p>This paper tests GROBID retry handling.</p></div>
    </body>
  </text>
</TEI>
"""


def _pdf(tmp_path: Path) -> Path:
    path = tmp_path / "paper.pdf"
    path.write_bytes(b"%PDF-1.4\n% retry test\n")
    return path


def _client(**overrides) -> GrobidClient:
    config_kwargs = {
        "url": "http://grobid.test",
        "timeout_seconds": 1,
        "retry_attempts": 3,
        "retry_backoff_initial_seconds": 0,
        "retry_backoff_max_seconds": 0,
    }
    config_kwargs.update(overrides)
    return GrobidClient(GrobidConfig(**config_kwargs))


def test_process_fulltext_retries_read_error_then_succeeds(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path)
    client = _client()
    attempts = {"count": 0}

    def fake_post_once(_pdf_path):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.ReadError(
                "connection reset by peer",
                request=httpx.Request("POST", "http://grobid.test/api/processFulltextDocument"),
            )
        return httpx.Response(
            200,
            request=httpx.Request("POST", "http://grobid.test/api/processFulltextDocument"),
            text=MINIMAL_TEI,
        )

    monkeypatch.setattr(client, "_post_fulltext_once", fake_post_once)

    assert client.process_fulltext(pdf) == MINIMAL_TEI
    assert attempts["count"] == 2


def test_process_fulltext_retries_timeout_then_succeeds(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path)
    client = _client()
    attempts = {"count": 0}

    def fake_post_once(_pdf_path):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise httpx.TimeoutException(
                "timed out",
                request=httpx.Request("POST", "http://grobid.test/api/processFulltextDocument"),
            )
        return httpx.Response(
            200,
            request=httpx.Request("POST", "http://grobid.test/api/processFulltextDocument"),
            text=MINIMAL_TEI,
        )

    monkeypatch.setattr(client, "_post_fulltext_once", fake_post_once)

    assert client.process_fulltext(pdf) == MINIMAL_TEI
    assert attempts["count"] == 3


def test_process_fulltext_retries_retryable_http_status(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path)
    client = _client(retry_status_codes=[503])
    attempts = {"count": 0}
    request = httpx.Request("POST", "http://grobid.test/api/processFulltextDocument")

    def fake_post_once(_pdf_path):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(503, request=request, text="service unavailable")
        return httpx.Response(200, request=request, text=MINIMAL_TEI)

    monkeypatch.setattr(client, "_post_fulltext_once", fake_post_once)

    assert client.process_fulltext(pdf) == MINIMAL_TEI
    assert attempts["count"] == 2


def test_process_fulltext_does_not_retry_non_retryable_http_status(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path)
    client = _client(retry_status_codes=[503])
    attempts = {"count": 0}
    request = httpx.Request("POST", "http://grobid.test/api/processFulltextDocument")

    def fake_post_once(_pdf_path):
        attempts["count"] += 1
        return httpx.Response(400, request=request, text="bad request")

    monkeypatch.setattr(client, "_post_fulltext_once", fake_post_once)

    assert client.process_fulltext(pdf) is None
    assert attempts["count"] == 1


def test_pipeline_grobid_extraction_preserves_grobid_primary_contract(tmp_path):
    pdf = _pdf(tmp_path)
    intake = IntakeResult(
        file_path=pdf,
        sha256="a" * 64,
        page_count=1,
        file_size_bytes=pdf.stat().st_size,
        has_text_layer=True,
        is_scanned=False,
        text_density=100.0,
        extraction_route=ExtractionRoute.GROBID_PRIMARY,
    )
    config = PipelineConfig()
    config.extraction.fallback_threshold = 0.0
    pipeline = IngestionPipeline(config)
    pipeline._grobid.process_fulltext = lambda _pdf_path: MINIMAL_TEI

    extraction = pipeline._extract_grobid(pdf, intake, warnings=[])

    assert extraction.extraction_method == ExtractionRoute.GROBID_PRIMARY
    assert extraction.fallback_used is False
    assert extraction.raw_title == "Retry Test Paper"
    assert extraction.raw_sections


def test_process_fulltext_retries_connect_error_then_succeeds(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path)
    client = _client()
    attempts = {"count": 0}

    def fake_post_once(_pdf_path):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.ConnectError(
                "connection refused",
                request=httpx.Request("POST", "http://grobid.test/api/processFulltextDocument"),
            )
        return httpx.Response(
            200,
            request=httpx.Request("POST", "http://grobid.test/api/processFulltextDocument"),
            text=MINIMAL_TEI,
        )

    monkeypatch.setattr(client, "_post_fulltext_once", fake_post_once)

    assert client.process_fulltext(pdf) == MINIMAL_TEI
    assert attempts["count"] == 2


def test_process_fulltext_retries_write_error_then_succeeds(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path)
    client = _client()
    attempts = {"count": 0}

    def fake_post_once(_pdf_path):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.WriteError(
                "broken pipe",
                request=httpx.Request("POST", "http://grobid.test/api/processFulltextDocument"),
            )
        return httpx.Response(
            200,
            request=httpx.Request("POST", "http://grobid.test/api/processFulltextDocument"),
            text=MINIMAL_TEI,
        )

    monkeypatch.setattr(client, "_post_fulltext_once", fake_post_once)

    assert client.process_fulltext(pdf) == MINIMAL_TEI
    assert attempts["count"] == 2


def test_process_fulltext_retries_remote_protocol_error_then_succeeds(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path)
    client = _client()
    attempts = {"count": 0}

    def fake_post_once(_pdf_path):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.RemoteProtocolError(
                "server closed connection without sending response",
                request=httpx.Request("POST", "http://grobid.test/api/processFulltextDocument"),
            )
        return httpx.Response(
            200,
            request=httpx.Request("POST", "http://grobid.test/api/processFulltextDocument"),
            text=MINIMAL_TEI,
        )

    monkeypatch.setattr(client, "_post_fulltext_once", fake_post_once)

    assert client.process_fulltext(pdf) == MINIMAL_TEI
    assert attempts["count"] == 2


def test_process_fulltext_retries_network_error_then_succeeds(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path)
    client = _client()
    attempts = {"count": 0}

    def fake_post_once(_pdf_path):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.NetworkError(
                "network unreachable",
                request=httpx.Request("POST", "http://grobid.test/api/processFulltextDocument"),
            )
        return httpx.Response(
            200,
            request=httpx.Request("POST", "http://grobid.test/api/processFulltextDocument"),
            text=MINIMAL_TEI,
        )

    monkeypatch.setattr(client, "_post_fulltext_once", fake_post_once)

    assert client.process_fulltext(pdf) == MINIMAL_TEI
    assert attempts["count"] == 2


def test_process_fulltext_all_retries_exhausted_returns_none(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path)
    client = _client(retry_attempts=3)
    attempts = {"count": 0}

    def fake_post_once(_pdf_path):
        attempts["count"] += 1
        raise httpx.ReadError(
            "connection reset by peer",
            request=httpx.Request("POST", "http://grobid.test/api/processFulltextDocument"),
        )

    monkeypatch.setattr(client, "_post_fulltext_once", fake_post_once)

    result = client.process_fulltext(pdf)

    assert result is None
    assert attempts["count"] == 3


def test_pipeline_fallback_to_pymupdf_after_grobid_retries_exhausted(tmp_path, monkeypatch):
    """Verify pipeline falls back to PyMuPDF only after GROBID retries are exhausted."""
    pdf = _pdf(tmp_path)
    intake = IntakeResult(
        file_path=pdf,
        sha256="a" * 64,
        page_count=2,
        file_size_bytes=pdf.stat().st_size,
        has_text_layer=True,
        is_scanned=False,
        text_density=100.0,
        extraction_route=ExtractionRoute.GROBID_WITH_FALLBACK,
    )
    config = PipelineConfig()
    config.grobid.retry_attempts = 2
    config.grobid.retry_backoff_initial_seconds = 0
    config.grobid.retry_backoff_max_seconds = 0
    config.extraction.fallback_threshold = 0.0
    pipeline = IngestionPipeline(config)

    grobid_attempts = {"count": 0}

    def failing_grobid(_pdf_path):
        grobid_attempts["count"] += 1
        return None  # process_fulltext returns None after retries exhausted

    monkeypatch.setattr(pipeline._grobid, "process_fulltext", failing_grobid)

    pymupdf_sections = [
        RawSection(
            header="Introduction",
            paragraphs=["This is fallback content from PyMuPDF."],
            level=1,
            parent_index=None,
            page_start=0,
            page_end=1,
            extraction_method=ExtractionMethod.PYMUPDF_FALLBACK,
        )
    ]

    def mock_extract_pymupdf(_pdf_path):
        return pymupdf_sections

    monkeypatch.setattr("researchmind.pipeline.extract_with_pymupdf", mock_extract_pymupdf)

    extraction = pipeline._stage_extraction(intake, pdf, [])

    assert extraction.fallback_used is True
    assert extraction.extraction_method == ExtractionRoute.GROBID_WITH_FALLBACK
    assert grobid_attempts["count"] == 1  # process_fulltext called once, returns None
    assert len(extraction.raw_sections) == 1
    assert extraction.raw_sections[0].paragraphs[0] == "This is fallback content from PyMuPDF."
    assert extraction.raw_sections[0].extraction_method == ExtractionMethod.PYMUPDF_FALLBACK


def test_pipeline_no_fallback_when_grobid_succeeds_on_retry(tmp_path, monkeypatch):
    """Verify pipeline does NOT fall back when GROBID succeeds after retries."""
    pdf = _pdf(tmp_path)
    intake = IntakeResult(
        file_path=pdf,
        sha256="a" * 64,
        page_count=1,
        file_size_bytes=pdf.stat().st_size,
        has_text_layer=True,
        is_scanned=False,
        text_density=100.0,
        extraction_route=ExtractionRoute.GROBID_WITH_FALLBACK,
    )
    config = PipelineConfig()
    config.grobid.retry_attempts = 3
    config.grobid.retry_backoff_initial_seconds = 0
    config.grobid.retry_backoff_max_seconds = 0
    config.extraction.fallback_threshold = 0.0
    pipeline = IngestionPipeline(config)

    call_count = {"count": 0}

    def mock_post_fulltext_once(pdf_path):
        call_count["count"] += 1
        if call_count["count"] < 2:
            raise httpx.TimeoutException(
                "timed out",
                request=httpx.Request("POST", "http://grobid.test/api/processFulltextDocument"),
            )
        resp = httpx.Response(
            200,
            request=httpx.Request("POST", "http://grobid.test/api/processFulltextDocument"),
            text=MINIMAL_TEI,
        )
        return resp

    monkeypatch.setattr(pipeline._grobid, "_post_fulltext_once", mock_post_fulltext_once)

    extraction = pipeline._stage_extraction(intake, pdf, [])

    assert extraction.fallback_used is False
    assert extraction.extraction_method == ExtractionRoute.GROBID_PRIMARY
    assert extraction.raw_title == "Retry Test Paper"
    assert call_count["count"] == 2
