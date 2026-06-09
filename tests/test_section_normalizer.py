from researchmind.models.enums import CanonicalLabel
from researchmind.models.intermediates import RawSection
from researchmind.extraction.tei_parser import parse_tei_xml
from researchmind.structuring.section_normalizer import normalize_sections


def _labels(headers: list[str]) -> list[CanonicalLabel]:
    sections = [
        RawSection(header=header, paragraphs=["placeholder body"], page_start=0, page_end=0)
        for header in headers
    ]
    return [section.canonical_label for section in normalize_sections(sections)]


def test_common_ml_section_headers_are_not_other() -> None:
    labels = _labels(
        [
            "Experimental Setup",
            "Implementation Details",
            "Training Details",
            "Ablation Studies",
            "Evaluation",
            "Error Analysis",
            "Case Studies",
            "Datasets",
            "Supplementary Material",
            "Additional Results",
            "Hyperparameters",
        ]
    )

    assert labels == [
        CanonicalLabel.METHODOLOGY,
        CanonicalLabel.METHODOLOGY,
        CanonicalLabel.METHODOLOGY,
        CanonicalLabel.RESULTS,
        CanonicalLabel.RESULTS,
        CanonicalLabel.RESULTS,
        CanonicalLabel.RESULTS,
        CanonicalLabel.METHODOLOGY,
        CanonicalLabel.APPENDIX,
        CanonicalLabel.RESULTS,
        CanonicalLabel.METHODOLOGY,
    ]


def test_arxiv_appendix_prefixes_are_cleaned_before_matching() -> None:
    labels = _labels(
        [
            "A.3 Fine-tuning Procedure",
            "C Additional Ablation Studies",
            "C.2 Ablation for Different Masking Procedures",
            "B.3 CIFAR-10 and CIFAR-100",
        ]
    )

    assert labels == [
        CanonicalLabel.METHODOLOGY,
        CanonicalLabel.RESULTS,
        CanonicalLabel.RESULTS,
        CanonicalLabel.RESULTS,
    ]


def test_attention_style_method_and_result_subsections_match() -> None:
    labels = _labels(
        [
            "Encoder and Decoder Stacks",
            "Scaled Dot-Product Attention",
            "Training Data and Batching",
            "Hardware and Schedule",
            "Machine Translation",
            "English Constituency Parsing",
        ]
    )

    assert labels == [
        CanonicalLabel.METHODOLOGY,
        CanonicalLabel.METHODOLOGY,
        CanonicalLabel.METHODOLOGY,
        CanonicalLabel.METHODOLOGY,
        CanonicalLabel.RESULTS,
        CanonicalLabel.RESULTS,
    ]


def test_low_confidence_child_other_inherits_parent_label() -> None:
    sections = [
        RawSection(
            header="Methodology",
            level=1,
            paragraphs=["We describe the research design."],
            page_start=0,
            page_end=0,
        ),
        RawSection(
            header="Custom Cohort Filter",
            level=2,
            parent_index=0,
            paragraphs=["This subsection describes a data filtering step."],
            page_start=0,
            page_end=0,
        ),
    ]

    normalized = normalize_sections(sections)

    assert normalized[1].parent_section_id == "sec_001"
    assert normalized[1].canonical_label == CanonicalLabel.METHODOLOGY
    assert normalized[1].label_confidence < normalized[0].label_confidence


def test_parent_inheritance_does_not_override_non_other_child() -> None:
    sections = [
        RawSection(
            header="Methodology",
            level=1,
            paragraphs=["We describe the research design."],
            page_start=0,
            page_end=0,
        ),
        RawSection(
            header="Ablation Studies",
            level=2,
            parent_index=0,
            paragraphs=["We compare several variants."],
            page_start=0,
            page_end=0,
        ),
    ]

    normalized = normalize_sections(sections)

    assert normalized[1].canonical_label == CanonicalLabel.RESULTS


def test_parent_inheritance_has_safeguards_for_references() -> None:
    sections = [
        RawSection(
            header="Methodology",
            level=1,
            paragraphs=["We describe the research design."],
            page_start=0,
            page_end=0,
        ),
        RawSection(
            header="References",
            level=2,
            parent_index=0,
            paragraphs=["Smith 2020."],
            page_start=0,
            page_end=0,
        ),
    ]

    normalized = normalize_sections(sections)

    assert normalized[1].canonical_label == CanonicalLabel.OTHER


def test_expanded_methodology_variants_are_not_other() -> None:
    """Verify newly added ML/CS methodology headers are recognized."""
    labels = _labels(
        [
            "Our Approach",
            "Problem Formulation",
            "Learning Objective",
            "Loss Function",
            "Training Objective",
            "Experimental Protocol",
            "Training Setup",
            "Training Configuration",
            "Complexity Analysis",
            "Algorithm",
            "Learning",
            "Optimization",
            "Baselines",
            "Time Complexity",
            "Training Loss",
            "Objective Function",
        ]
    )

    assert all(l == CanonicalLabel.METHODOLOGY for l in labels), (
        f"Expected all METHODOLOGY, got: {[(h, l.value) for h, l in zip(['Our Approach', 'Problem Formulation', 'Learning Objective', 'Loss Function', 'Training Objective', 'Experimental Protocol', 'Training Setup', 'Training Configuration', 'Complexity Analysis', 'Algorithm', 'Learning', 'Optimization', 'Baselines', 'Time Complexity', 'Training Loss', 'Objective Function'], labels)]}"
    )


def test_expanded_results_variants_are_not_other() -> None:
    """Verify newly added ML/CS results headers are recognized."""
    labels = _labels(
        [
            "Quantitative Analysis",
            "Qualitative Analysis",
            "Comparison with Baselines",
            "Baseline Comparison",
            "Parameter Sensitivity",
            "Sensitivity Analysis",
            "Statistical Analysis",
            "Runtime Analysis",
            "Efficiency",
            "Ablation Analysis",
            "Qualitative Examples",
            "Quantitative Evaluation",
            "Qualitative Evaluation",
            "Comparison with Prior Work",
            "Hyperparameter Analysis",
            "Comparison with State-of-the-Art",
            "Performance Comparison",
            "Quantitative Comparison",
            "Qualitative Comparison",
            "Ablation",
        ]
    )

    expected: list[CanonicalLabel] = [CanonicalLabel.RESULTS] * len(labels)
    # "Comparison with Prior Work" is semantically related_work, not results
    expected[13] = CanonicalLabel.RELATED_WORK

    assert labels == expected, (
        f"Mismatch: {[(h, l.value, e.value) for h, l, e in zip(['Quantitative Analysis', 'Qualitative Analysis', 'Comparison with Baselines', 'Baseline Comparison', 'Parameter Sensitivity', 'Sensitivity Analysis', 'Statistical Analysis', 'Runtime Analysis', 'Efficiency', 'Ablation Analysis', 'Qualitative Examples', 'Quantitative Evaluation', 'Qualitative Evaluation', 'Comparison with Prior Work', 'Hyperparameter Analysis', 'Comparison with State-of-the-Art', 'Performance Comparison', 'Quantitative Comparison', 'Qualitative Comparison', 'Ablation'], labels, expected)]}"
    )


def test_expanded_discussion_variants_are_not_other() -> None:
    """Verify newly added discussion variants are recognized."""
    labels = _labels(
        [
            "Experimental Analysis",
            "Discussion and Analysis",
            "Analysis and Discussion",
        ]
    )

    assert all(l == CanonicalLabel.DISCUSSION for l in labels), (
        f"Expected all DISCUSSION, got: {[(h, l.value) for h, l in zip(['Experimental Analysis', 'Discussion and Analysis', 'Analysis and Discussion'], labels)]}"
    )


def test_expanded_appendix_variants_are_not_other() -> None:
    """Verify newly added appendix variants are recognized."""
    labels = _labels(
        [
            "Online Supplement",
            "Supplement",
            "Supplemental",
        ]
    )

    assert all(l == CanonicalLabel.APPENDIX for l in labels), (
        f"Expected all APPENDIX, got: {[(h, l.value) for h, l in zip(['Online Supplement', 'Supplement', 'Supplemental'], labels)]}"
    )


def test_expanded_introduction_variants_are_not_other() -> None:
    """Verify newly added introduction variants are recognized."""
    labels = _labels(
        [
            "Preliminaries",
            "Notations",
        ]
    )

    assert all(l == CanonicalLabel.INTRODUCTION for l in labels), (
        f"Expected all INTRODUCTION, got: {[(h, l.value) for h, l in zip(['Preliminaries', 'Notations'], labels)]}"
    )


def test_single_word_header_does_not_false_match_multiword_variant() -> None:
    """Short single-word headers should not match multi-word variants via
    token_set_ratio at full confidence.  This avoids false MATCHING where
    'Evaluation' would match 'evaluation protocol' at 1.0 instead of
    matching the exact 'evaluation' variant under RESULTS."""
    sections = [
        RawSection(header="Evaluation", paragraphs=["placeholder"], page_start=0, page_end=0),
        RawSection(header="Data", paragraphs=["placeholder"], page_start=0, page_end=0),
        RawSection(header="Setup", paragraphs=["placeholder"], page_start=0, page_end=0),
    ]

    normalized = normalize_sections(sections)
    labels = [s.canonical_label for s in normalized]

    assert labels[0] == CanonicalLabel.RESULTS, f"Expected RESULTS, got {labels[0].value}"


def test_confidence_for_expanded_variants_uses_strong_threshold() -> None:
    """Expanded YAML variants should match at score >= 0.88 (strong tier),
    yielding full confidence rather than the damped tentative tier."""
    sections = [
        RawSection(header="Our Approach", paragraphs=["placeholder"], page_start=0, page_end=0),
        RawSection(header="Quantitative Analysis", paragraphs=["placeholder"], page_start=0, page_end=0),
        RawSection(header="Online Supplement", paragraphs=["placeholder"], page_start=0, page_end=0),
        RawSection(header="Baseline Comparison", paragraphs=["placeholder"], page_start=0, page_end=0),
    ]

    normalized = normalize_sections(sections)

    for s in normalized:
        assert s.label_confidence >= 0.88, (
            f"Section '{s.original_header}' confidence {s.label_confidence:.3f} < 0.88"
        )


def test_nested_tei_divs_provide_parent_indexes_for_inheritance() -> None:
    tei_xml = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>
    <fileDesc>
      <titleStmt><title>Hierarchy Test</title></titleStmt>
      <sourceDesc><p>test</p></sourceDesc>
    </fileDesc>
  </teiHeader>
  <text>
    <body>
      <div>
        <head>Experiments</head>
        <p>We evaluate the method.</p>
        <div>
          <head>Custom Benchmark Slice</head>
          <p>This subsection reports a benchmark slice.</p>
        </div>
      </div>
    </body>
  </text>
</TEI>
"""

    raw_fields, _quality = parse_tei_xml(tei_xml)
    raw_sections = raw_fields["raw_sections"]
    normalized = normalize_sections(raw_sections)

    assert raw_sections[1].parent_index == 0
    assert normalized[1].parent_section_id == "sec_001"
    assert normalized[1].canonical_label == CanonicalLabel.RESULTS
    assert normalized[1].label_confidence < normalized[0].label_confidence
