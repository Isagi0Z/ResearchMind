"""Extraction layer — PDF content extraction via GROBID, PyMuPDF, and OCR."""

from researchmind.extraction.grobid_client import GrobidClient
from researchmind.extraction.tei_parser import parse_tei_xml
from researchmind.extraction.pymupdf_extractor import extract_with_pymupdf
from researchmind.extraction.ocr_extractor import extract_with_ocr

__all__ = [
    "GrobidClient",
    "parse_tei_xml",
    "extract_with_pymupdf",
    "extract_with_ocr",
]
