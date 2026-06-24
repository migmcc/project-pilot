"""Project lifecycle state: the ``.project-pilot/status.json`` foundation.

State is a small dataclass serialised deterministically to JSON. Timestamps are
supplied by an injectable clock (see :func:`utc_now_iso`) so that callers and
tests can freeze time for reproducible output.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .errors import StateNotFoundError
from .phases import Phase

#: Bumped only when the on-disk schema changes (paired with a migration shim).
SCHEMA_VERSION = 1

STATE_DIRNAME = ".project-pilot"
STATE_FILENAME = "status.json"

#: A clock returns an ISO-8601 UTC timestamp string.
Clock = Callable[[], str]


def utc_now_iso() -> str:
    """Default clock: current UTC time, second precision, ISO-8601 with ``Z``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def state_dir(base: Path) -> Path:
    return Path(base) / STATE_DIRNAME


def state_path(base: Path) -> Path:
    return state_dir(base) / STATE_FILENAME


def state_exists(base: Path) -> bool:
    return state_path(base).exists()


@dataclass
class ProjectState:
    name: str
    slug: str
    idea: str
    created_at: str
    updated_at: str
    current_phase: Phase = Phase.IDEA
    decision: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a deterministically ordered dictionary."""
        return {
            "schema_version": self.schema_version,
            "project": {
                "name": self.name,
                "slug": self.slug,
                "idea": self.idea,
                "created_at": self.created_at,
            },
            "current_phase": self.current_phase.value,
            "decision": self.decision,
            "history": self.history,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectState":
        project = data["project"]
        return cls(
            name=project["name"],
            slug=project["slug"],
            idea=project["idea"],
            created_at=project["created_at"],
            updated_at=data["updated_at"],
            current_phase=Phase(data["current_phase"]),
            decision=data.get("decision"),
            history=list(data.get("history", [])),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )


def save_state(base: Path, state: ProjectState) -> Path:
    """Write state to ``<base>/.project-pilot/status.json`` and return its path."""
    directory = state_dir(base)
    directory.mkdir(parents=True, exist_ok=True)
    path = state_path(base)
    payload = json.dumps(state.to_dict(), indent=2, ensure_ascii=False)
    path.write_text(payload + "\n", encoding="utf-8")
    return path


def load_state(base: Path) -> ProjectState:
    """Load state from ``<base>/.project-pilot/status.json``.

    Raises :class:`StateNotFoundError` if the file does not exist.
    """
    path = state_path(base)
    if not path.exists():
        raise StateNotFoundError(f"No ProjectPilot state at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return ProjectState.from_dict(data)
