"""Parse GROBID TEI XML into raw intermediate data structures.

This module takes the TEI XML string returned by GROBID and extracts all
structured data — title, authors, abstract, body sections, bibliography,
inline citations, tables, figures — into the intermediate models defined in
:mod:`researchmind.models.intermediates`.

The main entry point is :func:`parse_tei_xml` which returns a dict of raw
fields and a quality score.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from lxml import etree

from researchmind.models.enums import ExtractionMethod
from researchmind.models.intermediates import (
    RawAuthor,
    RawCitation,
    RawFigure,
    RawReference,
    RawSection,
    RawTable,
)

logger = logging.getLogger(__name__)

# TEI namespace
_NS = "http://www.tei-c.org/ns/1.0"
_XML_NS = "http://www.w3.org/XML/1998/namespace"
_NSMAP = {"tei": _NS}


def _xpath(el: etree._Element, expr: str) -> list[etree._Element]:
    """Convenience wrapper for XPath with the TEI namespace."""
    return el.xpath(expr, namespaces=_NSMAP)


def _text_content(el: etree._Element | None) -> str:
    """Recursively extract all text content from an element."""
    if el is None:
        return ""
    return (etree.tostring(el, method="text", encoding="unicode") or "").strip()


def _text_or_empty(el: etree._Element | None) -> str:
    """Return the direct text of an element, or empty string."""
    if el is None:
        return ""
    return (el.text or "").strip()


def _xml_id(el: etree._Element) -> str:
    """Return an element's XML id, handling namespace-aware TEI attributes."""
    return (
        el.get(f"{{{_XML_NS}}}id")
        or el.get("xml:id")
        or el.get("id")
        or ""
    )


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------


def _extract_title(root: etree._Element) -> str | None:
    """Extract the paper title from the TEI header."""
    # Primary: //tei:titleStmt/tei:title[@level='a' and @type='main']
    titles = _xpath(root, ".//tei:teiHeader//tei:titleStmt/tei:title[@type='main']")
    if not titles:
        titles = _xpath(root, ".//tei:teiHeader//tei:titleStmt/tei:title")
    if titles:
        title_text = _text_content(titles[0])
        if title_text:
            return title_text
    return None


# ---------------------------------------------------------------------------
# Authors
# ---------------------------------------------------------------------------


def _extract_authors(root: etree._Element) -> list[RawAuthor]:
    """Extract authors from the TEI header, including affiliations and ORCID."""
    authors: list[RawAuthor] = []

    # Build an affiliation lookup  {xml:id → affiliation string}
    aff_map: dict[str, str] = {}
    for aff_el in _xpath(root, ".//tei:teiHeader//tei:affiliation"):
        aff_key = _xml_id(aff_el) or aff_el.get("key") or ""
        org_names = _xpath(aff_el, ".//tei:orgName")
        parts = [_text_content(o) for o in org_names if _text_content(o)]
        if parts:
            aff_map[aff_key] = ", ".join(parts)
        elif _text_content(aff_el):
            aff_map[aff_key] = _text_content(aff_el)

    for author_el in _xpath(
        root, ".//tei:teiHeader//tei:fileDesc//tei:author"
    ):
        persname = _xpath(author_el, ".//tei:persName")
        if not persname:
            continue
        pn = persname[0]

        given_parts = _xpath(pn, "tei:forename")
        given = " ".join(_text_content(g) for g in given_parts).strip() or None

        surname_els = _xpath(pn, "tei:surname")
        surname = _text_content(surname_els[0]) if surname_els else None

        full_name_parts = [p for p in (given, surname) if p]
        full_name = " ".join(full_name_parts) if full_name_parts else _text_content(pn)
        if not full_name:
            continue

        # Email
        email_els = _xpath(author_el, ".//tei:email")
        email = _text_content(email_els[0]) if email_els else None

        # ORCID — stored in <idno type="ORCID"> or similar
        orcid: str | None = None
        for idno in _xpath(author_el, ".//tei:idno[@type='ORCID']"):
            orcid_val = _text_content(idno)
            if orcid_val:
                orcid = orcid_val
                break

        # Affiliations
        affiliations: list[str] = []
        for aff_child in _xpath(author_el, ".//tei:affiliation"):
            aff_key = aff_child.get("key") or ""
            if aff_key and aff_key in aff_map:
                affiliations.append(aff_map[aff_key])
            else:
                aff_text = _text_content(aff_child)
                if aff_text:
                    affiliations.append(aff_text)

        # Corresponding author heuristic
        role = author_el.get("role", "")
        is_corresponding = "corresp" in role.lower() or email is not None

        authors.append(
            RawAuthor(
                full_name=full_name,
                given_name=given,
                surname=surname,
                affiliations=affiliations,
                email=email,
                orcid=orcid,
                is_corresponding=is_corresponding,
            )
        )

    return authors


# ---------------------------------------------------------------------------
# Abstract
# ---------------------------------------------------------------------------


def _extract_abstract(root: etree._Element) -> str | None:
    """Extract the abstract text, concatenating multiple abstract divs."""
    abstracts = _xpath(root, ".//tei:teiHeader//tei:profileDesc//tei:abstract")
    if not abstracts:
        return None

    parts: list[str] = []
    for ab in abstracts:
        # Abstract may contain <div>/<p> structure or direct text
        paras = _xpath(ab, ".//tei:p")
        if paras:
            for p in paras:
                text = _text_content(p)
                if text:
                    parts.append(text)
        else:
            text = _text_content(ab)
            if text:
                parts.append(text)

    return "\n\n".join(parts) if parts else None


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------


def _extract_keywords(root: etree._Element) -> list[str]:
    """Extract keywords from the TEI header."""
    keywords: list[str] = []
    for kw_list in _xpath(root, ".//tei:teiHeader//tei:keywords"):
        for term in _xpath(kw_list, ".//tei:term"):
            text = _text_content(term)
            if text:
                keywords.append(text)
        # Also handle direct text in keywords element
        if not keywords:
            text = _text_content(kw_list)
            if text:
                # Split comma-separated keywords
                keywords.extend(
                    k.strip() for k in text.split(",") if k.strip()
                )
    return keywords


# ---------------------------------------------------------------------------
# DOI and dates
# ---------------------------------------------------------------------------


def _extract_doi(root: etree._Element) -> str | None:
    """Extract DOI from the TEI header."""
    for idno in _xpath(root, ".//tei:teiHeader//tei:idno[@type='DOI']"):
        doi = _text_content(idno)
        if doi:
            return doi
    return None


def _extract_dates(root: etree._Element) -> str | None:
    """Extract the publication date string from the TEI header."""
    # Try <date type="published">
    for date_el in _xpath(root, ".//tei:teiHeader//tei:date[@type='published']"):
        when = date_el.get("when", "")
        if when:
            return when
        text = _text_content(date_el)
        if text:
            return text

    # Fallback: any <date> in the header
    for date_el in _xpath(root, ".//tei:teiHeader//tei:date"):
        when = date_el.get("when", "")
        if when:
            return when

    return None


# ---------------------------------------------------------------------------
# Body sections
# ---------------------------------------------------------------------------


def _extract_body_sections(root: etree._Element) -> list[RawSection]:
    """Extract body sections with hierarchy from <body><div>...</div></body>.

    Handles nested divs and produces a flat list with ``parent_index`` links
    to represent the hierarchy.
    """
    body = _xpath(root, ".//tei:text/tei:body")
    if not body:
        logger.warning("TEI XML has no <body> element")
        return []

    sections: list[RawSection] = []

    def _process_div(
        div: etree._Element, level: int, parent_idx: int | None
    ) -> None:
        """Recursively process a <div> into sections."""
        # Section header
        heads = _xpath(div, "tei:head")
        header = _text_content(heads[0]) if heads else ""

        # Extract page coordinates if available
        page_start = 0
        page_end = 0
        if heads:
            coords = heads[0].get("coords", "")
            if coords:
                try:
                    page_start = int(coords.split(",")[0]) - 1  # 0-indexed
                    page_end = page_start
                except (ValueError, IndexError):
                    pass

        # Direct paragraphs (not inside nested divs)
        paragraphs: list[str] = []
        for p_el in _xpath(div, "tei:p"):
            text = _text_content(p_el)
            if text:
                paragraphs.append(text)

        current_idx = len(sections)
        sections.append(
            RawSection(
                header=header,
                level=level,
                parent_index=parent_idx,
                paragraphs=paragraphs,
                page_start=page_start,
                page_end=page_end,
                extraction_method=ExtractionMethod.GROBID,
            )
        )

        # Recurse into child divs
        for child_div in _xpath(div, "tei:div"):
            _process_div(child_div, level + 1, current_idx)

    # Process top-level divs inside <body>
    for div in _xpath(body[0], "tei:div"):
        _process_div(div, 1, None)

    # If no divs found, try to extract paragraphs directly from body
    if not sections:
        paras = _xpath(body[0], "tei:p")
        if paras:
            paragraphs = [_text_content(p) for p in paras if _text_content(p)]
            if paragraphs:
                sections.append(
                    RawSection(
                        header="",
                        level=1,
                        parent_index=None,
                        paragraphs=paragraphs,
                        page_start=0,
                        page_end=0,
                        extraction_method=ExtractionMethod.GROBID,
                    )
                )

    return sections


# ---------------------------------------------------------------------------
# Bibliography
# ---------------------------------------------------------------------------


def _extract_references(root: etree._Element) -> list[RawReference]:
    """Extract bibliography entries from <listBibl>/<biblStruct>."""
    refs: list[RawReference] = []

    for bib in _xpath(root, ".//tei:text//tei:listBibl/tei:biblStruct"):
        grobid_id = _xml_id(bib)

        # Title — from <title level="a" type="main"> or <title level="m">
        title: str | None = None
        for t in _xpath(bib, ".//tei:title[@type='main']"):
            title = _text_content(t)
            if title:
                break
        if not title:
            for t in _xpath(bib, ".//tei:title"):
                title = _text_content(t)
                if title:
                    break

        # Authors
        author_names: list[str] = []
        for author_el in _xpath(bib, ".//tei:author"):
            pn = _xpath(author_el, ".//tei:persName")
            if pn:
                name = _text_content(pn[0])
                if name:
                    author_names.append(name)

        # Year
        year: str | None = None
        for date_el in _xpath(bib, ".//tei:date"):
            when = date_el.get("when", "")
            if when:
                # Extract just the year part
                year_match = re.match(r"(\d{4})", when)
                if year_match:
                    year = year_match.group(1)
                    break

        # Venue — <title level="j"> (journal) or <title level="m"> (monograph)
        venue: str | None = None
        for t in _xpath(bib, ".//tei:title[@level='j']"):
            venue = _text_content(t)
            if venue:
                break
        if not venue:
            for t in _xpath(bib, ".//tei:title[@level='m']"):
                venue = _text_content(t)
                if venue:
                    break

        # Volume and pages
        volume: str | None = None
        for v in _xpath(bib, ".//tei:biblScope[@unit='volume']"):
            volume = _text_content(v)
            if volume:
                break

        pages: str | None = None
        for pg in _xpath(bib, ".//tei:biblScope[@unit='page']"):
            from_pg = pg.get("from", "")
            to_pg = pg.get("to", "")
            if from_pg and to_pg:
                pages = f"{from_pg}-{to_pg}"
            elif from_pg:
                pages = from_pg
            else:
                pages = _text_content(pg) or None
            if pages:
                break

        # DOI
        doi: str | None = None
        for idno in _xpath(bib, ".//tei:idno[@type='DOI']"):
            doi = _text_content(idno)
            if doi:
                break

        # URL
        url: str | None = None
        for ptr in _xpath(bib, ".//tei:ptr[@target]"):
            url = ptr.get("target", "") or None
            if url:
                break

        # Raw text fallback
        raw_text = _text_content(bib)

        refs.append(
            RawReference(
                grobid_id=grobid_id or None,
                raw_text=raw_text,
                title=title,
                authors=author_names,
                year=year,
                venue=venue,
                volume=volume,
                pages=pages,
                doi=doi,
                url=url,
            )
        )

    return refs


# ---------------------------------------------------------------------------
# Inline citations
# ---------------------------------------------------------------------------


def _extract_citations(
    root: etree._Element, sections: list[RawSection]
) -> list[RawCitation]:
    """Extract inline citation markers from <ref type="bibr"> elements."""
    citations: list[RawCitation] = []

    body = _xpath(root, ".//tei:text/tei:body")
    if not body:
        return citations

    for div_idx, div in enumerate(_xpath(body[0], ".//tei:div")):
        for para_idx, p_el in enumerate(_xpath(div, "tei:p")):
            # Get the full paragraph text for sentence context
            para_text = _text_content(p_el)

            for ref_el in _xpath(p_el, ".//tei:ref[@type='bibr']"):
                target = ref_el.get("target", "")
                marker = _text_content(ref_el)

                # Build a context sentence: grab surrounding text
                # Use the paragraph as sentence context (a simplification)
                sentence = para_text[:500] if para_text else ""

                # Map div_idx to section_index
                section_index = min(div_idx, len(sections) - 1) if sections else 0

                citations.append(
                    RawCitation(
                        grobid_ref_target=target if target else None,
                        raw_marker=marker,
                        section_index=section_index,
                        paragraph_index=para_idx,
                        sentence=sentence,
                    )
                )

    return citations


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


def _extract_tables(root: etree._Element) -> list[RawTable]:
    """Extract tables from <figure type='table'>."""
    tables: list[RawTable] = []

    for fig in _xpath(root, ".//tei:figure[@type='table']"):
        grobid_id = _xml_id(fig)

        # Caption
        caption_els = _xpath(fig, "tei:head")
        caption = _text_content(caption_els[0]) if caption_els else ""
        # Also try <figDesc>
        if not caption:
            desc_els = _xpath(fig, "tei:figDesc")
            caption = _text_content(desc_els[0]) if desc_els else ""

        # Page from coords
        page = 0
        coords = fig.get("coords", "")
        if coords:
            try:
                page = int(coords.split(",")[0]) - 1
            except (ValueError, IndexError):
                pass

        # Raw table content — try to extract from <table> child
        raw_content: str | None = None
        table_els = _xpath(fig, ".//tei:table")
        if table_els:
            rows: list[str] = []
            for row_el in _xpath(table_els[0], ".//tei:row"):
                cells: list[str] = []
                for cell_el in _xpath(row_el, "tei:cell"):
                    cells.append(_text_content(cell_el))
                rows.append(" | ".join(cells))
            raw_content = "\n".join(rows) if rows else _text_content(table_els[0])
        if not raw_content:
            raw_content = _text_content(fig) or None

        tables.append(
            RawTable(
                grobid_id=grobid_id or None,
                caption=caption,
                page=max(page, 0),
                raw_content=raw_content,
                extraction_method=ExtractionMethod.GROBID,
            )
        )

    return tables


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------


def _extract_figures(root: etree._Element) -> list[RawFigure]:
    """Extract figures from <figure> (non-table type)."""
    figures: list[RawFigure] = []

    for fig in _xpath(root, ".//tei:figure"):
        fig_type = fig.get("type", "")
        if fig_type == "table":
            continue  # handled by _extract_tables

        grobid_id = _xml_id(fig)

        # Caption
        caption_els = _xpath(fig, "tei:head")
        caption = _text_content(caption_els[0]) if caption_els else ""
        if not caption:
            desc_els = _xpath(fig, "tei:figDesc")
            caption = _text_content(desc_els[0]) if desc_els else ""

        # Page
        page = 0
        coords = fig.get("coords", "")
        if coords:
            try:
                page = int(coords.split(",")[0]) - 1
            except (ValueError, IndexError):
                pass

        figures.append(
            RawFigure(
                grobid_id=grobid_id or None,
                caption=caption,
                page=max(page, 0),
                image_path=None,  # GROBID doesn't export images
            )
        )

    return figures


# ---------------------------------------------------------------------------
# Quality score
# ---------------------------------------------------------------------------


def _compute_quality_score(
    title: str | None,
    authors: list[RawAuthor],
    abstract: str | None,
    sections: list[RawSection],
    references: list[RawReference],
    total_text_chars: int,
) -> float:
    """Compute a GROBID extraction quality score in [0, 1].

    Weighted formula
    ~~~~~~~~~~~~~~~~
    - 0.25 × title present
    - 0.20 × authors present
    - 0.15 × abstract present
    - 0.20 × min(sections_count / 4, 1.0)
    - 0.10 × min(refs_count / 5, 1.0)
    - 0.10 × min(text_density / 10_000, 1.0)
    """
    score = 0.0

    # Title
    if title:
        score += 0.25

    # Authors
    if authors:
        score += 0.20

    # Abstract
    if abstract:
        score += 0.15

    # Sections (scale: 4+ sections = full marks)
    n_sections = len(sections)
    score += 0.20 * min(n_sections / 4.0, 1.0)

    # References (scale: 5+ refs = full marks)
    n_refs = len(references)
    score += 0.10 * min(n_refs / 5.0, 1.0)

    # Text density (scale: 10k+ chars = full marks)
    score += 0.10 * min(total_text_chars / 10_000.0, 1.0)

    return round(min(max(score, 0.0), 1.0), 4)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def parse_tei_xml(
    tei_xml: str,
) -> tuple[dict[str, Any], float]:
    """Parse GROBID TEI XML and return raw field data plus a quality score.

    Parameters
    ----------
    tei_xml:
        The complete TEI XML string returned by GROBID.

    Returns
    -------
    tuple[dict[str, Any], float]
        A 2-tuple of:
        - A dict whose keys map directly to :class:`ExtractionResult` fields
          (``raw_title``, ``raw_authors``, etc.).  The caller is responsible
          for setting ``intake`` and assembling the ``ExtractionResult``.
        - A ``float`` quality score in [0, 1].

    The function never raises — on parse errors it returns as much data as
    it could extract along with a reduced quality score.
    """
    result: dict[str, Any] = {
        "raw_title": None,
        "raw_authors": [],
        "raw_abstract": None,
        "raw_keywords": [],
        "raw_doi": None,
        "raw_pub_date": None,
        "raw_sections": [],
        "raw_references": [],
        "raw_citations": [],
        "raw_tables": [],
        "raw_figures": [],
    }

    if not tei_xml or not tei_xml.strip():
        logger.error("Empty TEI XML string")
        return result, 0.0

    # Parse XML
    try:
        root = etree.fromstring(tei_xml.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        logger.error("Failed to parse TEI XML: %s", exc)
        return result, 0.0

    # --- Title ---
    try:
        result["raw_title"] = _extract_title(root)
    except Exception as exc:
        logger.warning("Error extracting title: %s", exc)

    # --- Authors ---
    try:
        result["raw_authors"] = _extract_authors(root)
    except Exception as exc:
        logger.warning("Error extracting authors: %s", exc)

    # --- Abstract ---
    try:
        result["raw_abstract"] = _extract_abstract(root)
    except Exception as exc:
        logger.warning("Error extracting abstract: %s", exc)

    # --- Keywords ---
    try:
        result["raw_keywords"] = _extract_keywords(root)
    except Exception as exc:
        logger.warning("Error extracting keywords: %s", exc)

    # --- DOI ---
    try:
        result["raw_doi"] = _extract_doi(root)
    except Exception as exc:
        logger.warning("Error extracting DOI: %s", exc)

    # --- Dates ---
    try:
        result["raw_pub_date"] = _extract_dates(root)
    except Exception as exc:
        logger.warning("Error extracting dates: %s", exc)

    # --- Body sections ---
    try:
        result["raw_sections"] = _extract_body_sections(root)
    except Exception as exc:
        logger.warning("Error extracting body sections: %s", exc)

    # --- References ---
    try:
        result["raw_references"] = _extract_references(root)
    except Exception as exc:
        logger.warning("Error extracting references: %s", exc)

    # --- Inline citations ---
    try:
        result["raw_citations"] = _extract_citations(root, result["raw_sections"])
    except Exception as exc:
        logger.warning("Error extracting citations: %s", exc)

    # --- Tables ---
    try:
        result["raw_tables"] = _extract_tables(root)
    except Exception as exc:
        logger.warning("Error extracting tables: %s", exc)

    # --- Figures ---
    try:
        result["raw_figures"] = _extract_figures(root)
    except Exception as exc:
        logger.warning("Error extracting figures: %s", exc)

    # --- Quality score ---
    total_chars = sum(
        len(p)
        for sec in result["raw_sections"]
        for p in sec.paragraphs
    )
    quality = _compute_quality_score(
        result["raw_title"],
        result["raw_authors"],
        result["raw_abstract"],
        result["raw_sections"],
        result["raw_references"],
        total_chars,
    )

    logger.info(
        "TEI parse complete: title=%s, authors=%d, sections=%d, "
        "refs=%d, citations=%d, tables=%d, figures=%d, quality=%.3f",
        bool(result["raw_title"]),
        len(result["raw_authors"]),
        len(result["raw_sections"]),
        len(result["raw_references"]),
        len(result["raw_citations"]),
        len(result["raw_tables"]),
        len(result["raw_figures"]),
        quality,
    )

    return result, quality
