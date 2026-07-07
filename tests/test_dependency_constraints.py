from __future__ import annotations

import tomllib
from pathlib import Path


def test_spacy_is_constrained_for_python39_compatibility() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    dependencies = pyproject_data["project"]["dependencies"]

    spacy_dependency = next(dep for dep in dependencies if dep.startswith("spacy"))
    assert spacy_dependency == "spacy>=3.7,<3.8"
