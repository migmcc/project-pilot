"""Artifact inventory for externally produced workflow evidence.

ProjectPilot records metadata about artifacts produced by humans or external
agents, but never executes, validates, copies, or modifies those artifacts.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Callable

from .errors import StateCorruptedError
from .state import atomic_write_text, state_dir, utc_now_iso


__all__ = [
    "ARTIFACTS_FILENAME",
    "ORIGIN_MANUAL",
    "STATUS_REGISTERED",
    "Clock",
    "ARTIFACT_RECORD_KEYS",
    "artifacts_path",
    "sha256_file",
    "load_inventory",
    "dumps_inventory",
    "save_inventory",
    "list_artifacts",
    "find_artifact",
    "add_artifact",
    "remove_artifact",
]

ARTIFACTS_FILENAME = "artifacts.json"
ORIGIN_MANUAL = "manual"
STATUS_REGISTERED = "registered"

#: Recovery hint shown when ``artifacts.json`` cannot be used.
_INVENTORY_HINT = (
    "Repair the file by hand or delete it and re-register the evidence with "
    "`pp artifact add <path>`."
)

Clock = Callable[[], str]

_ID_TOKEN_RE = re.compile(r"[^a-z0-9]+")
ARTIFACT_RECORD_KEYS = (
    "id",
    "path",
    "name",
    "type",
    "phase",
    "registered_at",
    "size",
    "sha256",
    "origin",
    "status",
)


def artifacts_path(base: Path) -> Path:
    """Return ``<base>/.project-pilot/artifacts.json``."""
    return state_dir(base) / ARTIFACTS_FILENAME


def sha256_file(path: Path) -> str:
    """Calculate the SHA-256 digest for ``path`` without changing it."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_relative_path(base: Path, file_path: Path) -> str:
    base_resolved = Path(base).resolve()
    path = Path(file_path)
    if not path.is_absolute():
        path = base_resolved / path
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Artifact file does not exist: {file_path}")
    try:
        relative = resolved.relative_to(base_resolved)
    except ValueError:
        raise ValueError(f"Artifact must be inside the project directory: {file_path}") from None
    return relative.as_posix()


def _stable_id(relative_path: str) -> str:
    slug = _ID_TOKEN_RE.sub("-", relative_path.lower()).strip("-")
    return slug or "artifact"


def _collision_id(relative_path: str) -> str:
    suffix = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:8]
    return f"{_stable_id(relative_path)}-{suffix}"


def _ordered_record(record: dict) -> dict:
    return {key: record[key] for key in ARTIFACT_RECORD_KEYS}


def _sort_records(records: list[dict]) -> list[dict]:
    return sorted((_ordered_record(record) for record in records), key=lambda r: (r["path"], r["id"]))


def load_inventory(base: Path) -> dict:
    """Load the deterministic inventory payload.

    Missing inventories are treated as empty. Records are returned sorted by
    relative path so callers get stable ordering even if a file was edited by
    hand. Raises :class:`StateCorruptedError` when the file exists but is
    malformed JSON or its records are missing required fields.
    """
    path = artifacts_path(base)
    if not path.exists():
        return {"artifacts": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StateCorruptedError(
            path,
            f"the file is not valid JSON ({exc.msg} at line {exc.lineno}, column {exc.colno})",
            _INVENTORY_HINT,
        ) from exc
    try:
        records = data.get("artifacts", [])
        return {"artifacts": _sort_records(list(records))}
    except KeyError as exc:
        raise StateCorruptedError(
            path,
            f"an artifact record is missing the required field {exc.args[0]!r}",
            _INVENTORY_HINT,
        ) from exc
    except (TypeError, AttributeError) as exc:
        raise StateCorruptedError(
            path, f"the file does not have the expected structure ({exc})", _INVENTORY_HINT
        ) from exc


def dumps_inventory(base: Path) -> str:
    """Serialise the inventory as deterministic JSON with a trailing newline."""
    return json.dumps(load_inventory(base), indent=2, ensure_ascii=False) + "\n"


def save_inventory(base: Path, inventory: dict) -> Path:
    """Save ``inventory`` to ``.project-pilot/artifacts.json`` atomically."""
    directory = state_dir(base)
    directory.mkdir(parents=True, exist_ok=True)
    path = artifacts_path(base)
    records = _sort_records(list(inventory.get("artifacts", [])))
    payload = {"artifacts": records}
    atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return path


def list_artifacts(base: Path) -> list[dict]:
    """Return registered artifacts in stable order."""
    return list(load_inventory(base)["artifacts"])


def find_artifact(base: Path, artifact_id: str) -> dict | None:
    """Find one artifact by id, or ``None`` when absent."""
    return next((record for record in list_artifacts(base) if record["id"] == artifact_id), None)


def _id_for_path(records: list[dict], relative_path: str) -> str:
    preferred = _stable_id(relative_path)
    for record in records:
        if record["path"] == relative_path:
            return record["id"]
    if not any(record["id"] == preferred for record in records):
        return preferred
    return _collision_id(relative_path)


def add_artifact(
    base: Path,
    file_path: Path,
    current_phase: str,
    *,
    clock: Clock = utc_now_iso,
) -> dict:
    """Register or update metadata for ``file_path``.

    Duplicate adds for the same relative path replace the inventory entry with
    freshly calculated deterministic metadata; the artifact file itself is never
    copied or modified.
    """
    relative_path = _normalise_relative_path(base, file_path)
    inventory = load_inventory(base)
    records = list(inventory["artifacts"])
    resolved = Path(base).resolve() / relative_path
    artifact_id = _id_for_path(records, relative_path)
    extension = resolved.suffix.lower().lstrip(".") or "unknown"
    record = {
        "id": artifact_id,
        "path": relative_path,
        "name": resolved.name,
        "type": extension,
        "phase": current_phase,
        "registered_at": clock(),
        "size": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
        "origin": ORIGIN_MANUAL,
        "status": STATUS_REGISTERED,
    }
    records = [existing for existing in records if existing["path"] != relative_path]
    records.append(record)
    save_inventory(base, {"artifacts": records})
    return _ordered_record(record)


def remove_artifact(base: Path, artifact_id: str) -> dict | None:
    """Remove one inventory entry by id without deleting the artifact file."""
    inventory = load_inventory(base)
    records = list(inventory["artifacts"])
    removed = next((record for record in records if record["id"] == artifact_id), None)
    if removed is None:
        return None
    save_inventory(
        base,
        {"artifacts": [record for record in records if record["id"] != artifact_id]},
    )
    return removed
