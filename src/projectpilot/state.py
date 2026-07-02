"""Project lifecycle state: the ``.project-pilot/status.json`` foundation.

State is a small dataclass serialised deterministically to JSON. Timestamps are
supplied by an injectable clock (see :func:`utc_now_iso`) so that callers and
tests can freeze time for reproducible output.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .errors import StateCorruptedError, StateNotFoundError, UnknownPhaseError
from .phases import Phase, phase_from_str

__all__ = [
    "SCHEMA_VERSION",
    "STATE_DIRNAME",
    "STATE_FILENAME",
    "Clock",
    "utc_now_iso",
    "state_dir",
    "state_path",
    "state_exists",
    "ProjectState",
    "atomic_write_text",
    "save_state",
    "load_state",
]

#: Recovery hint shown when ``status.json`` cannot be used.
_STATE_HINT = (
    "Repair the file by hand (compare it with a freshly initialized project) "
    'or start over with `pp init "<idea>" --force`.'
)

#: Increased only on backward-incompatible changes or mandatory migrations.
#: Additive optional fields (which load via ``.get(...)``) keep version 1.
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
    idea_source: str | None = None
    current_phase: Phase = Phase.IDEA
    decision: dict[str, Any] | None = None
    brief: dict[str, Any] | None = None
    setup_advice: dict[str, Any] | None = None
    ateam_check: dict[str, Any] | None = None
    execution_approval: dict[str, Any] | None = None
    final_validation: dict[str, Any] | None = None
    done_approval: dict[str, Any] | None = None
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
                "idea_source": self.idea_source,
            },
            "current_phase": self.current_phase.value,
            "decision": self.decision,
            "brief": self.brief,
            "setup_advice": self.setup_advice,
            "ateam_check": self.ateam_check,
            "execution_approval": self.execution_approval,
            "final_validation": self.final_validation,
            "done_approval": self.done_approval,
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
            idea_source=project.get("idea_source"),
            updated_at=data["updated_at"],
            current_phase=phase_from_str(data["current_phase"]),
            decision=data.get("decision"),
            brief=data.get("brief"),
            setup_advice=data.get("setup_advice"),
            ateam_check=data.get("ateam_check"),
            execution_approval=data.get("execution_approval"),
            final_validation=data.get("final_validation"),
            done_approval=data.get("done_approval"),
            history=list(data.get("history", [])),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )


def atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically.

    The content lands in a temporary sibling file first and is then moved over
    the target with :func:`os.replace`, so an interruption mid-write can never
    leave a half-written file behind. The sibling lives in the same directory,
    which keeps the replace on one volume (atomic on POSIX and Windows alike).
    On failure the temporary file is removed and the target is left untouched.
    """
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def save_state(base: Path, state: ProjectState) -> Path:
    """Write state to ``<base>/.project-pilot/status.json`` and return its path.

    The write is atomic (see :func:`atomic_write_text`).
    """
    directory = state_dir(base)
    directory.mkdir(parents=True, exist_ok=True)
    path = state_path(base)
    payload = json.dumps(state.to_dict(), indent=2, ensure_ascii=False)
    atomic_write_text(path, payload + "\n")
    return path


#: Optional recorded sections that, when present, must be JSON objects.
_OPTIONAL_SECTIONS = (
    "decision",
    "brief",
    "setup_advice",
    "ateam_check",
    "execution_approval",
    "final_validation",
    "done_approval",
)


def _validate_sections(path: Path, state: ProjectState) -> None:
    """Reject hand-edited section values whose type no consumer could handle."""
    for name in _OPTIONAL_SECTIONS:
        value = getattr(state, name)
        if value is not None and not isinstance(value, dict):
            raise StateCorruptedError(
                path, f"the {name!r} section must be a JSON object or null", _STATE_HINT
            )
    if not all(isinstance(entry, dict) for entry in state.history):
        raise StateCorruptedError(
            path, "the 'history' section must be a list of JSON objects", _STATE_HINT
        )


def load_state(base: Path) -> ProjectState:
    """Load state from ``<base>/.project-pilot/status.json``.

    Raises :class:`StateNotFoundError` if the file does not exist and
    :class:`StateCorruptedError` if it exists but cannot be used (malformed
    JSON, missing required fields, an unknown phase, or hand-edited sections
    of the wrong type).
    """
    path = state_path(base)
    if not path.exists():
        raise StateNotFoundError(f"No ProjectPilot state at {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StateCorruptedError(
            path,
            f"the file is not valid JSON ({exc.msg} at line {exc.lineno}, column {exc.colno})",
            _STATE_HINT,
        ) from exc
    try:
        state = ProjectState.from_dict(data)
    except KeyError as exc:
        raise StateCorruptedError(
            path, f"the required field {exc.args[0]!r} is missing", _STATE_HINT
        ) from exc
    except UnknownPhaseError as exc:
        raise StateCorruptedError(path, str(exc), _STATE_HINT) from exc
    except (TypeError, AttributeError, ValueError) as exc:
        raise StateCorruptedError(
            path, f"the file does not have the expected structure ({exc})", _STATE_HINT
        ) from exc
    _validate_sections(path, state)
    return state
