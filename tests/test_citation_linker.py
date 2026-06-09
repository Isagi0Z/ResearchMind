from researchmind.extraction.tei_parser import parse_tei_xml
from researchmind.models.enums import (
    CanonicalLabel,
    ExtractionMethod,
    ResolutionSource,
    ResolutionStatus,
)
from researchmind.models.intermediates import RawCitation, RawReference
from researchmind.models.sro import SROChunk, SROReference, SROSection
from researchmind.structuring.citation_linker import link_citations


def _section(section_id: str, position: int, label: CanonicalLabel) -> SROSection:
    return SROSection(
        section_id=section_id,
        level=1,
        position=position,
        original_header=label.value,
        canonical_label=label,
        label_confidence=1.0,
        page_start=0,
        page_end=0,
        content="section text",
    )


def _chunk(
    chunk_id: str,
    section_id: str,
    paragraph_index: int,
    text: str,
) -> SROChunk:
    return SROChunk(
        chunk_id=chunk_id,
        text=text,
        word_count=len(text.split()),
        section_id=section_id,
        canonical_label=CanonicalLabel.METHODOLOGY,
        page_start=0,
        page_end=0,
        paragraph_index=paragraph_index,
        reading_order=int(chunk_id.rsplit("_", 1)[-1]),
        extraction_method=ExtractionMethod.GROBID,
        extraction_confidence=1.0,
    )


def _reference(ref_id: str, title: str, year: str = "2020") -> SROReference:
    return SROReference(
        ref_id=ref_id,
        raw_text=title,
        resolution_status=ResolutionStatus.RESOLVED,
        ref_confidence=0.9,
        title=title,
        authors=["Smith, Jane"],
        year=year,
        resolution_source=ResolutionSource.GROBID_CONSOLIDATION,
    )


def test_multi_target_grobid_citation_emits_one_edge_per_reference() -> None:
    sections = [_section("sec_001", 0, CanonicalLabel.METHODOLOGY)]
    chunks = [_chunk("chk_000", "sec_001", 0, "Prior work [1,2] supports this method.")]
    raw_refs = [
        RawReference(grobid_id="b0", raw_text="Reference 1"),
        RawReference(grobid_id="b1", raw_text="Reference 2"),
    ]
    refs = [_reference("ref_001", "Reference 1"), _reference("ref_002", "Reference 2")]
    raw_citations = [
        RawCitation(
            grobid_ref_target="#b0 #b1",
            raw_marker="[1,2]",
            section_index=0,
            paragraph_index=0,
            sentence="Prior work [1,2] supports this method.",
        )
    ]

    linked = link_citations(raw_citations, refs, chunks, sections, raw_refs)

    assert [citation.ref_id for citation in linked] == ["ref_001", "ref_002"]
    assert {citation.chunk_id for citation in linked} == {"chk_000"}


def test_numeric_range_fallback_links_multiple_references() -> None:
    sections = [_section("sec_001", 0, CanonicalLabel.RELATED_WORK)]
    chunks = [_chunk("chk_000", "sec_001", 0, "Several papers [1-3] established this.")]
    raw_refs = [RawReference(raw_text=f"Reference {idx}") for idx in range(1, 4)]
    refs = [_reference(f"ref_{idx:03d}", f"Reference {idx}") for idx in range(1, 4)]
    raw_citations = [
        RawCitation(
            raw_marker="[1-3]",
            section_index=0,
            paragraph_index=0,
            sentence="Several papers [1-3] established this.",
        )
    ]

    linked = link_citations(raw_citations, refs, chunks, sections, raw_refs)

    assert [citation.ref_id for citation in linked] == ["ref_001", "ref_002", "ref_003"]


def test_section_and_paragraph_aware_chunk_matching_prefers_local_chunk() -> None:
    sections = [
        _section("sec_001", 0, CanonicalLabel.INTRODUCTION),
        _section("sec_002", 1, CanonicalLabel.METHODOLOGY),
    ]
    chunks = [
        _chunk("chk_000", "sec_001", 0, "The same sentence [1] appears here."),
        _chunk("chk_001", "sec_002", 0, "The same sentence [1] appears here."),
    ]
    raw_refs = [RawReference(grobid_id="b0", raw_text="Reference 1")]
    refs = [_reference("ref_001", "Reference 1")]
    raw_citations = [
        RawCitation(
            grobid_ref_target="#b0",
            raw_marker="[1]",
            section_index=1,
            paragraph_index=0,
            sentence="The same sentence [1] appears here.",
        )
    ]

    linked = link_citations(raw_citations, refs, chunks, sections, raw_refs)

    assert linked[0].chunk_id == "chk_001"
    assert linked[0].section_id == "sec_002"


def test_author_year_ampersand_syntax() -> None:
    sections = [_section("sec_001", 0, CanonicalLabel.RELATED_WORK)]
    chunks = [_chunk("chk_000", "sec_001", 0, "Prior work (Smith & Jones, 2020) is relevant.")]
    raw_refs = [RawReference(raw_text=""), RawReference(raw_text="")]
    refs = [
        SROReference(
            ref_id="ref_001", raw_text="", title="A", authors=["Smith, Jane"],
            year="2020", resolution_status=ResolutionStatus.RESOLVED,
            ref_confidence=0.9, resolution_source=ResolutionSource.GROBID_CONSOLIDATION,
        ),
        SROReference(
            ref_id="ref_002", raw_text="", title="B", authors=["Jones, Bob"],
            year="2020", resolution_status=ResolutionStatus.RESOLVED,
            ref_confidence=0.9, resolution_source=ResolutionSource.GROBID_CONSOLIDATION,
        ),
    ]
    raw_citations = [
        RawCitation(
            raw_marker="(Smith & Jones, 2020)",
            section_index=0, paragraph_index=0,
            sentence="Prior work (Smith & Jones, 2020) is relevant.",
        )
    ]

    linked = link_citations(raw_citations, refs, chunks, sections, raw_refs)

    assert {citation.ref_id for citation in linked} == {"ref_001", "ref_002"}


def test_author_year_et_al_syntax() -> None:
    sections = [_section("sec_001", 0, CanonicalLabel.RELATED_WORK)]
    chunks = [_chunk("chk_000", "sec_001", 0, "As shown by (Smith et al., 2020) the method works.")]
    raw_refs = [RawReference(raw_text="")]
    refs = [
        SROReference(
            ref_id="ref_001", raw_text="", title="A", authors=["Smith, Jane"],
            year="2020", resolution_status=ResolutionStatus.RESOLVED,
            ref_confidence=0.9, resolution_source=ResolutionSource.GROBID_CONSOLIDATION,
        ),
    ]
    raw_citations = [
        RawCitation(
            raw_marker="(Smith et al., 2020)",
            section_index=0, paragraph_index=0,
            sentence="As shown by (Smith et al., 2020) the method works.",
        )
    ]

    linked = link_citations(raw_citations, refs, chunks, sections, raw_refs)

    assert linked[0].ref_id == "ref_001"


def test_author_year_semicolon_separated() -> None:
    sections = [_section("sec_001", 0, CanonicalLabel.RELATED_WORK)]
    chunks = [_chunk("chk_000", "sec_001", 0, "Several works (Smith, 2020; Jones, 2021) exist.")]
    raw_refs = [RawReference(raw_text=""), RawReference(raw_text="")]
    refs = [
        SROReference(
            ref_id="ref_001", raw_text="", title="A", authors=["Smith, Jane"],
            year="2020", resolution_status=ResolutionStatus.RESOLVED,
            ref_confidence=0.9, resolution_source=ResolutionSource.GROBID_CONSOLIDATION,
        ),
        SROReference(
            ref_id="ref_002", raw_text="", title="B", authors=["Jones, Bob"],
            year="2021", resolution_status=ResolutionStatus.RESOLVED,
            ref_confidence=0.9, resolution_source=ResolutionSource.GROBID_CONSOLIDATION,
        ),
    ]
    raw_citations = [
        RawCitation(
            raw_marker="(Smith, 2020; Jones, 2021)",
            section_index=0, paragraph_index=0,
            sentence="Several works (Smith, 2020; Jones, 2021) exist.",
        )
    ]

    linked = link_citations(raw_citations, refs, chunks, sections, raw_refs)

    assert {citation.ref_id for citation in linked} == {"ref_001", "ref_002"}


def test_text_similarity_fallback_resolves_citation() -> None:
    sections = [_section("sec_001", 0, CanonicalLabel.RELATED_WORK)]
    chunks = [_chunk("chk_000", "sec_001", 0, "The neural machine translation approach introduced by Vaswani has been widely adopted [CIT001].")]
    raw_refs = [RawReference(raw_text="")]
    refs = [
        SROReference(
            ref_id="ref_001", raw_text="", title="Neural Machine Translation",
            authors=["Vaswani, A."], year="2017",
            resolution_status=ResolutionStatus.RESOLVED, ref_confidence=0.9,
            resolution_source=ResolutionSource.GROBID_CONSOLIDATION,
        ),
        SROReference(
            ref_id="ref_002", raw_text="", title="Image Classification",
            authors=["Krizhevsky, A."], year="2012",
            resolution_status=ResolutionStatus.RESOLVED, ref_confidence=0.9,
            resolution_source=ResolutionSource.GROBID_CONSOLIDATION,
        ),
    ]
    raw_citations = [
        RawCitation(
            raw_marker="[CIT001]",
            section_index=0, paragraph_index=0,
            sentence="The neural machine translation approach introduced by Vaswani has been widely adopted [CIT001].",
        )
    ]

    linked = link_citations(raw_citations, refs, chunks, sections, raw_refs)

    assert linked[0].ref_id == "ref_001"


def test_text_similarity_fallback_low_confidence_remains_unresolved() -> None:
    sections = [_section("sec_001", 0, CanonicalLabel.RELATED_WORK)]
    chunks = [_chunk("chk_000", "sec_001", 0, "Some prior work is relevant here [CIT001].")]
    raw_refs = [RawReference(raw_text="")]
    refs = [
        SROReference(
            ref_id="ref_001", raw_text="", title="Machine Translation with Attention",
            authors=["Vaswani, A."], year="2017",
            resolution_status=ResolutionStatus.RESOLVED, ref_confidence=0.9,
            resolution_source=ResolutionSource.GROBID_CONSOLIDATION,
        ),
    ]
    raw_citations = [
        RawCitation(
            raw_marker="[CIT001]",
            section_index=0, paragraph_index=0,
            sentence="Some prior work is relevant here [CIT001].",
        )
    ]

    linked = link_citations(raw_citations, refs, chunks, sections, raw_refs)

    assert linked[0].ref_id is None


def test_tei_citation_extraction_uses_direct_paragraphs_for_nested_divs() -> None:
    tei_xml = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>
    <fileDesc>
      <titleStmt><title>Nested Citation Test</title></titleStmt>
      <sourceDesc><p>test</p></sourceDesc>
    </fileDesc>
  </teiHeader>
  <text>
    <body>
      <div>
        <head>Methods</head>
        <p>Parent cites <ref type="bibr" target="#b0">[1]</ref>.</p>
        <div>
          <head>Custom Procedure</head>
          <p>Child cites <ref type="bibr" target="#b1">[2]</ref>.</p>
        </div>
      </div>
    </body>
    <back>
      <listBibl>
        <biblStruct xml:id="b0"><analytic><title>One</title></analytic></biblStruct>
        <biblStruct xml:id="b1"><analytic><title>Two</title></analytic></biblStruct>
      </listBibl>
    </back>
  </text>
</TEI>
"""

    raw_fields, _quality = parse_tei_xml(tei_xml)
    citations = raw_fields["raw_citations"]

    assert len(citations) == 2
    assert [(citation.section_index, citation.paragraph_index) for citation in citations] == [
        (0, 0),
        (1, 0),
    ]
