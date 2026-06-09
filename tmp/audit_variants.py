"""Audit which common ML/CS headers are currently missed by section variants."""
import yaml
from pathlib import Path
from rapidfuzz import fuzz
import re

from researchmind.models.enums import CanonicalLabel

config_path = Path("config/section_variants.yaml")
with open(config_path) as f:
    raw = yaml.safe_load(f)

variant_dict = {}
for key, variants in raw.items():
    try:
        label = CanonicalLabel(key)
    except ValueError:
        continue
    variant_dict[label] = [v.lower().strip() for v in variants]

def _clean_header(header):
    cleaned = re.sub(r"^\s*[A-Z]\.\d+(?:\.\d+)*\s*", "", header)
    cleaned = re.sub(r"^\s*[A-Z]\s+(?=(?:Additional|Appendix|Supplementary|Ablation|Results)\b)", "", cleaned)
    cleaned = re.sub(r"^\s*[\dIVXivx]+[\.\)]\s*", "", cleaned)
    cleaned = re.sub(r"^\s*[A-Z][\.\)]\s*", "", cleaned)
    cleaned = re.sub(r"^\s*[\d]+\s*[-]\s*", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip().lower()

test_headers = [
    "Our Approach",
    "The Proposed Method",
    "Method Overview",
    "Problem Formulation",
    "Preliminaries",
    "Notations",
    "Learning",
    "Training Objective",
    "Optimization",
    "Algorithm",
    "Experimental Protocol",
    "Baselines",
    "Benchmark Datasets",
    "Quantitative Analysis",
    "Qualitative Analysis",
    "Comparison with Baselines",
    "Comparison to Prior Work",
    "Baseline Comparison",
    "Ablation",
    "Ablation Analysis",
    "Parameter Sensitivity",
    "Sensitivity Analysis",
    "Statistical Analysis",
    "Runtime Analysis",
    "Efficiency",
    "Qualitative Examples",
    "Online Supplement",
    "Experimental Analysis",
    "Discussion and Analysis",
    "Complexity Analysis",
    "Implementation",
    "Evaluation Metrics",
    "Evaluation Protocol",
    "Training Setup",
    "Training Configuration",
    "Model Architecture",
    "Experimental Methodology",
    "Time Complexity",
    "Learning Objective",
    "Optimization Objective",
    "Loss Function",
    "Training Loss",
    "Objective Function",
]

print(f"{'Status':7s} {'Header':35s} {'Best Label':20s} {'Score':6s} {'Conf':6s}")
print("-" * 75)
for h in test_headers:
    cleaned = _clean_header(h)
    best_score = 0.0
    best_label = ""
    for label, variants in variant_dict.items():
        for variant in variants:
            s = max(
                fuzz.ratio(cleaned, variant) / 100.0,
                fuzz.token_sort_ratio(cleaned, variant) / 100.0,
            )
            if len(variant.split()) >= 2 or len(variant) >= 12:
                s = max(s, fuzz.token_set_ratio(cleaned, variant) / 100.0)
            if s > best_score:
                best_score = s
                best_label = label.value

    if best_score >= 0.88:
        conf = best_score
        marker = "OK"
    elif best_score >= 0.70:
        conf = best_score * 0.85
        marker = "LOW"
    else:
        conf = best_score
        marker = "MISS"

    print(f"{marker:7s} {h:35s} {best_label:20s} {best_score:.3f} {conf:.3f}")
