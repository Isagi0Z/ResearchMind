"""Intake layer — PDF fingerprinting and extraction route selection."""

from researchmind.intake.fingerprint import fingerprint
from researchmind.intake.router import route

__all__ = ["fingerprint", "route"]
