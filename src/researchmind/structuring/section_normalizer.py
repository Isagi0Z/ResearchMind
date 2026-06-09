"""Section normalizer: maps raw section headers to canonical labels.

Uses a tiered strategy:
1. Fuzzy string matching against the configured variant dictionary
2. Header heuristics for common research-paper section names
3. Content heuristics for limitation/future-work signals
4. Position heuristics for otherwise ambiguous sections
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml
from rapidfuzz import fuzz

from researchmind.models.enums import CanonicalLabel
from researchmind.models.intermediates import RawSection
from researchmind.models.sro import SROSection

logger = logging.getLogger(__name__)

# Default path relative to project root
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "section_variants.yaml"

_RESULTS_HEADER_RE = re.compile(
    r"\b("
    r"experiments?|experimental results?|evaluation|empirical evaluation|"
    r"ablation|additional ablation|case stud(?:y|ies)|error analysis|"
    r"results?\s+on|quantitative|qualitative|comparison with|effect of|"
    r"benchmarks?|performance|object detection|classification|translation|parsing|"
    r"glue|squad|swag|mnist|cifar|imagenet|pascal|ms coco|svhn|timit|reuters|"
    r"baseline comparison|comparison results|performance comparison|"
    r"parameter sensitivity|sensitivity analysis|statistical analysis|"
    r"runtime analysis|complexity analysis|efficiency|scalability|"
    r"ablation analysis|qualitative examples|quantitative analysis|qualitative analysis|"
    r"comparative analysis|hyperparameter analysis"
    r")\b",
)

_METHODOLOGY_HEADER_RE = re.compile(
    r"\b("
    r"method|methods|methodology|approach|architecture|model description|"
    r"network architecture|implementation|implementation details|experimental setup|"
    r"training|fine[- ]?tuning|pre[- ]?training|hyperparameters?|optimizer|"
    r"regularization|label smoothing|data augmentation|datasets?|data sets?|"
    r"training data|corpus|batching|hardware|schedule|system|procedure|"
    r"algorithm|update rule|initialization|"
    r"our approach|problem formulation|learning objective|loss function|"
    r"objective function|training objective|training loss|"
    r"experimental protocol|experimental methodology|baselines|"
    r"training setup|training configuration|training protocol|"
    r"model configuration|configurations|complexity analysis|time complexity|"
    r"optimization|learning|notations|preliminaries"
    r")\b",
)

_RELATED_HEADER_RE = re.compile(
    r"\b(related work|prior work|previous work|feature[- ]based approaches|transfer learning)\b"
)

_DISCUSSION_HEADER_RE = re.compile(
    r"\b(discussion|analysis|advantages and disadvantages|implications|extensions?)\b"
)

_APPENDIX_HEADER_RE = re.compile(
    r"\b(appendix|appendices|supplementary|additional material)\b"
)

_NON_INHERITABLE_HEADER_RE = re.compile(
    r"\b(abstract|references?|bibliography|acknowledg(?:e)?ments?)\b"
)

_INHERITANCE_CONFIDENCE_FACTOR = 0.85
_INHERITANCE_CONFIDENCE_CAP = 0.65
_INHERITANCE_LOW_CONFIDENCE_MAX = 0.45


def _load_variant_dict(config_path: Path) -> dict[CanonicalLabel, list[str]]:
    """Load the canonical-label to variant-strings mapping from YAML."""
    if not config_path.exists():
        logger.warning(
            "Section variants config not found at %s; using empty dictionary",
            config_path,
        )
        return {}

    with open(config_path, encoding="utf-8") as fh:
        raw: dict[str, list[str]] = yaml.safe_load(fh) or {}

    result: dict[CanonicalLabel, list[str]] = {}
    for key, variants in raw.items():
        try:
            label = CanonicalLabel(key)
        except ValueError:
            logger.warning("Unknown canonical label '%s' in config; skipping", key)
            continue
        result[label] = [v.lower().strip() for v in variants]

    logger.debug(
        "Loaded %d canonical labels with %d total variants",
        len(result),
        sum(len(v) for v in result.values()),
    )
    return result


def _clean_header(header: str) -> str:
    """Strip numbering prefixes and normalize whitespace in a section header."""
    # Remove leading numbering like "1.", "2.1", "III.", "A.", "A.3", "1 -".
    cleaned = re.sub(r"^\s*[A-Z]\.\d+(?:\.\d+)*\s*", "", header)
    cleaned = re.sub(
        r"^\s*[A-Z]\s+(?=(?:Additional|Appendix|Supplementary|Ablation|Results)\b)",
        "",
        cleaned,
    )
    cleaned = re.sub(r"^\s*[\dIVXivx]+[\.\)]\s*", "", cleaned)
    cleaned = re.sub(r"^\s*[A-Z][\.\)]\s*", "", cleaned)
    cleaned = re.sub(r"^\s*[\d]+\s*[-]\s*", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _variant_score(header: str, variant: str) -> float:
    """Score one cleaned header against one canonical variant."""
    if not header or not variant:
        return 0.0

    if header == variant:
        return 1.0

    scores = [
        fuzz.ratio(header, variant) / 100.0,
        fuzz.token_sort_ratio(header, variant) / 100.0,
    ]

    variant_words = variant.split()
    is_specific_variant = len(variant_words) >= 2 or len(variant) >= 12
    if is_specific_variant:
        tsr = fuzz.token_set_ratio(header, variant) / 100.0
        # Damp token_set_ratio when the header is a short substring of a
        # multi-word variant — avoids false 1.0 scores from single-word headers
        # matching a multi-word variant that happens to contain that word.
        if tsr >= 0.90 and len(header) < len(variant) * 0.6:
            tsr = round(max(tsr * 0.88, 0.70), 4)
        scores.append(tsr)
        if re.search(rf"\b{re.escape(variant)}\b", header):
            scores.append(0.94)

    if header.startswith(f"{variant}:") or header.startswith(f"{variant} -"):
        scores.append(0.93)

    return max(scores)


def _fuzzy_match(
    header: str,
    variant_dict: dict[CanonicalLabel, list[str]],
) -> tuple[CanonicalLabel | None, float]:
    """Find the best fuzzy match for a cleaned header against all variants."""
    best_label: CanonicalLabel | None = None
    best_score = 0.0

    for label, variants in variant_dict.items():
        for variant in variants:
            score = _variant_score(header, variant)
            if score > best_score:
                best_score = score
                best_label = label

    return best_label, best_score


def _apply_header_heuristic(
    header: str,
) -> tuple[CanonicalLabel | None, float]:
    """Map common ML/NLP/CV section headers that are not literal variants."""
    if not header:
        return None, 0.0

    if _APPENDIX_HEADER_RE.search(header):
        return CanonicalLabel.APPENDIX, 0.78

    if _RELATED_HEADER_RE.search(header):
        return CanonicalLabel.RELATED_WORK, 0.74

    # Setup/training/details should stay methodology even when they contain
    # words such as "experimental".
    if _METHODOLOGY_HEADER_RE.search(header):
        return CanonicalLabel.METHODOLOGY, 0.74

    if _RESULTS_HEADER_RE.search(header):
        return CanonicalLabel.RESULTS, 0.74

    if _DISCUSSION_HEADER_RE.search(header):
        return CanonicalLabel.DISCUSSION, 0.68

    return None, 0.0


def _apply_position_heuristic(
    index: int,
    total: int,
    already_seen: set[CanonicalLabel],
) -> tuple[CanonicalLabel, float]:
    """Assign a label based on position within the paper."""
    if index == 0 and CanonicalLabel.INTRODUCTION not in already_seen:
        return CanonicalLabel.INTRODUCTION, 0.7

    if index == total - 1 and CanonicalLabel.CONCLUSION not in already_seen:
        return CanonicalLabel.CONCLUSION, 0.6

    if CanonicalLabel.RESULTS in already_seen and CanonicalLabel.DISCUSSION not in already_seen:
        return CanonicalLabel.DISCUSSION, 0.5

    return CanonicalLabel.OTHER, 0.3


def _apply_content_heuristic(
    body_text: str,
) -> tuple[CanonicalLabel | None, float]:
    """Check body content for keyword signals."""
    lower = body_text.lower()

    if "limitation" in lower:
        return CanonicalLabel.LIMITATIONS, 0.55

    if "future" in lower and ("work" in lower or "direction" in lower):
        return CanonicalLabel.FUTURE_WORK, 0.50

    return None, 0.0


def normalize_sections(
    raw_sections: list[RawSection],
    config_path: Path | None = None,
) -> list[SROSection]:
    """Normalize raw extracted sections into SROSection objects."""
    if config_path is None:
        config_path = _DEFAULT_CONFIG_PATH

    variant_dict = _load_variant_dict(config_path)
    total = len(raw_sections)

    if total == 0:
        logger.warning("No raw sections provided for normalization")
        return []

    section_ids = [f"sec_{i + 1:03d}" for i in range(total)]
    already_seen: set[CanonicalLabel] = set()
    labels_by_index: dict[int, CanonicalLabel] = {}
    confidences_by_index: dict[int, float] = {}
    results: list[SROSection] = []

    for idx, raw in enumerate(raw_sections):
        section_id = section_ids[idx]
        parent_section_id: str | None = None
        if raw.parent_index is not None and 0 <= raw.parent_index < total:
            parent_section_id = section_ids[raw.parent_index]

        cleaned_header = _clean_header(raw.header)
        body_text = "\n\n".join(raw.paragraphs)

        label: CanonicalLabel
        confidence: float

        if cleaned_header:
            matched_label, score = _fuzzy_match(cleaned_header, variant_dict)

            if matched_label is not None and score >= 0.88:
                label = matched_label
                confidence = round(score, 4)
                logger.debug(
                    "Section '%s' -> %s (fuzzy strong, score=%.3f)",
                    raw.header,
                    label.value,
                    score,
                )
            elif matched_label is not None and score >= 0.70:
                label = matched_label
                confidence = round(score * 0.85, 4)
                logger.debug(
                    "Section '%s' -> %s (fuzzy tentative, score=%.3f, conf=%.3f)",
                    raw.header,
                    label.value,
                    score,
                    confidence,
                )
            else:
                label, confidence = _resolve_low_confidence_section(
                    raw=raw,
                    idx=idx,
                    total=total,
                    cleaned_header=cleaned_header,
                    body_text=body_text,
                    already_seen=already_seen,
                )
        else:
            label, confidence = _resolve_low_confidence_section(
                raw=raw,
                idx=idx,
                total=total,
                cleaned_header=cleaned_header,
                body_text=body_text,
                already_seen=already_seen,
            )

        label, confidence = _apply_parent_inheritance_if_needed(
            raw=raw,
            label=label,
            confidence=confidence,
            cleaned_header=cleaned_header,
            labels_by_index=labels_by_index,
            confidences_by_index=confidences_by_index,
        )

        already_seen.add(label)
        labels_by_index[idx] = label
        confidences_by_index[idx] = confidence

        try:
            results.append(
                SROSection(
                    section_id=section_id,
                    parent_section_id=parent_section_id,
                    level=min(max(raw.level, 1), 6),
                    position=idx,
                    original_header=raw.header,
                    canonical_label=label,
                    label_confidence=confidence,
                    page_start=raw.page_start,
                    page_end=raw.page_end,
                    content=body_text,
                )
            )
        except Exception:
            logger.exception(
                "Failed to create SROSection for index %d (header='%s')",
                idx,
                raw.header,
            )

    logger.info(
        "Normalized %d/%d sections (%d distinct labels)",
        len(results),
        total,
        len(already_seen),
    )
    return results


def _resolve_low_confidence_section(
    raw: RawSection,
    idx: int,
    total: int,
    cleaned_header: str,
    body_text: str,
    already_seen: set[CanonicalLabel],
) -> tuple[CanonicalLabel, float]:
    """Apply non-fuzzy fallback tiers for one section."""
    header_label, header_conf = _apply_header_heuristic(cleaned_header)
    if header_label is not None:
        logger.debug(
            "Section '%s' -> %s (header heuristic, conf=%.3f)",
            raw.header,
            header_label.value,
            header_conf,
        )
        return header_label, header_conf

    content_label, content_conf = _apply_content_heuristic(body_text)
    if content_label is not None:
        logger.debug(
            "Section '%s' -> %s (content heuristic, conf=%.3f)",
            raw.header,
            content_label.value,
            content_conf,
        )
        return content_label, content_conf

    if raw.parent_index is not None or raw.level > 1:
        logger.debug(
            "Section '%s' -> other (nested ambiguous section, conf=0.300)",
            raw.header,
        )
        return CanonicalLabel.OTHER, 0.3

    label, confidence = _apply_position_heuristic(idx, total, already_seen)
    logger.debug(
        "Section '%s' -> %s (position heuristic, conf=%.3f)",
        raw.header,
        label.value,
        confidence,
    )
    return label, confidence


def _apply_parent_inheritance_if_needed(
    raw: RawSection,
    label: CanonicalLabel,
    confidence: float,
    cleaned_header: str,
    labels_by_index: dict[int, CanonicalLabel],
    confidences_by_index: dict[int, float],
) -> tuple[CanonicalLabel, float]:
    """Inherit a parent's label only for low-confidence child OTHER sections."""
    if label != CanonicalLabel.OTHER:
        return label, confidence

    if confidence > _INHERITANCE_LOW_CONFIDENCE_MAX:
        return label, confidence

    if raw.parent_index is None or raw.level <= 1:
        return label, confidence

    if raw.parent_index < 0:
        logger.debug(
            "Section '%s' skipped parent inheritance: invalid parent_index=%s",
            raw.header,
            raw.parent_index,
        )
        return label, confidence

    if _NON_INHERITABLE_HEADER_RE.search(cleaned_header):
        logger.debug(
            "Section '%s' skipped parent inheritance: non-inheritable header",
            raw.header,
        )
        return label, confidence

    parent_label = labels_by_index.get(raw.parent_index)
    if parent_label is None:
        logger.debug(
            "Section '%s' skipped parent inheritance: parent not normalized yet",
            raw.header,
        )
        return label, confidence

    if parent_label == CanonicalLabel.OTHER:
        logger.debug(
            "Section '%s' skipped parent inheritance: parent label is OTHER",
            raw.header,
        )
        return label, confidence

    parent_confidence = confidences_by_index.get(raw.parent_index, 0.0)
    inherited_confidence = min(
        parent_confidence * _INHERITANCE_CONFIDENCE_FACTOR,
        _INHERITANCE_CONFIDENCE_CAP,
    )
    inherited_confidence = round(max(inherited_confidence, confidence), 4)

    logger.debug(
        "Section '%s' -> %s (parent inheritance from raw index %d, "
        "parent_conf=%.3f, child_conf=%.3f, inherited_conf=%.3f)",
        raw.header,
        parent_label.value,
        raw.parent_index,
        parent_confidence,
        confidence,
        inherited_confidence,
    )
    return parent_label, inherited_confidence
