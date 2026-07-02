"""Typed errors for ProjectPilot."""
from __future__ import annotations

from pathlib import Path

__all__ = [
    "ProjectPilotError",
    "StateCorruptedError",
    "StateExistsError",
    "StateNotFoundError",
    "UnknownPhaseError",
]

class ProjectPilotError(Exception):
    """Base class for all ProjectPilot errors."""


class StateCorruptedError(ProjectPilotError):
    """Raised when a ProjectPilot data file exists but cannot be used as-is.

    Carries the affected ``path``, a human-readable ``reason``, and a
    user-facing recovery ``hint`` so the CLI can print a friendly message
    instead of a traceback.
    """

    def __init__(self, path: Path | str, reason: str, hint: str) -> None:
        self.path = Path(path)
        self.reason = reason
        self.hint = hint
        super().__init__(f"Corrupted ProjectPilot file {self.path}: {reason}. {hint}")


class StateExistsError(ProjectPilotError):
    """Raised when project state already exists and overwrite was not requested."""


class StateNotFoundError(ProjectPilotError):
    """Raised when project state is expected but no state file is present."""


class UnknownPhaseError(ProjectPilotError):
    """Raised when a value does not map to a known lifecycle phase."""
