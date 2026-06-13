"""
Root conftest.py — ResearchMind environment isolation.

Ensures all temporary files, caches, and pytest artifacts remain
under D:\\RM and never spill onto C: (AppData, Temp, or User dirs).

This file runs automatically at the start of every pytest session.
"""
import os
import tempfile
from pathlib import Path

# ------------------------------------------------------------------
# Force Python tempfile module to use D:\RM\.tmp instead of C:\...\Temp
# This must happen before any test imports that call tempfile functions.
# ------------------------------------------------------------------
_TMP_ROOT = Path("D:/RM/.tmp")
_TMP_ROOT.mkdir(parents=True, exist_ok=True)

os.environ["TEMP"] = str(_TMP_ROOT)
os.environ["TMP"] = str(_TMP_ROOT)
tempfile.tempdir = str(_TMP_ROOT)

# ------------------------------------------------------------------
# Exclude script-style integration tests from standard pytest runs.
# These files have no def test_* functions and execute pipeline code
# at module level — collecting them triggers full pipeline runs and
# writes output files, dirtying the git working tree.
# Run them explicitly: python tests/test_extraction.py
# ------------------------------------------------------------------
collect_ignore = [
    "tests/test_extraction.py",
]
