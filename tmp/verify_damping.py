"""Verify the damping fix didn't break legitimate matches."""
import yaml
from pathlib import Path
from researchmind.structuring.section_normalizer import _clean_header, _variant_score
from researchmind.models.enums import CanonicalLabel

with open("config/section_variants.yaml") as f:
    raw = yaml.safe_load(f)

variant_dict = {}
for key, variants in raw.items():
    try:
        label = CanonicalLabel(key)
    except ValueError:
        continue
    variant_dict[label] = [v.lower().strip() for v in variants]

test_cases = [
    ("Evaluation", "results"),
    ("Experimental Setup", "methodology"),
    ("Implementation Details", "methodology"),
    ("Training Details", "methodology"),
    ("Ablation Studies", "results"),
    ("Error Analysis", "results"),
    ("Additional Results", "results"),
    ("Supplementary Material", "appendix"),
    ("Online Supplement", "appendix"),
    ("Problem Formulation", "methodology"),
    ("Our Approach", "methodology"),
    ("Preliminaries", "introduction"),
    ("Comparison with Baselines", "results"),
    ("Baseline Comparison", "results"),
    ("Runtime Analysis", "results"),
    ("Complexity Analysis", "methodology"),
    ("Training Setup", "methodology"),
    ("Quantitative Analysis", "results"),
    ("Loss Function", "methodology"),
    ("Sensitivity Analysis", "results"),
]

all_pass = True
for header, expected in test_cases:
    cleaned = _clean_header(header)
    best_label = None
    best_score = 0.0
    for label, variants in variant_dict.items():
        for variant in variants:
            score = _variant_score(cleaned, variant)
            if score > best_score:
                best_score = score
                best_label = label
    actual = best_label.value if best_label else "OTHER"
    ok = actual == expected
    if not ok:
        all_pass = False
    print(f"{'PASS' if ok else 'FAIL'}: \"{header}\" -> {actual} (expected {expected}) score={best_score:.3f}")

print()
print("ALL PASS" if all_pass else "SOME FAILURES")
