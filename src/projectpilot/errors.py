"""Typed errors for ProjectPilot."""
from __future__ import annotations


class ProjectPilotError(Exception):
    """Base class for all ProjectPilot errors."""


class StateExistsError(ProjectPilotError):
    """Raised when project state already exists and overwrite was not requested."""


class StateNotFoundError(ProjectPilotError):
    """Raised when project state is expected but no state file is present."""


class UnknownPhaseError(ProjectPilotError):
    """Raised when a value does not map to a known lifecycle phase."""
