"""``pp artifact`` -- register externally produced workflow evidence.

The command records metadata only. It does not validate, execute, copy, or
modify artifact files.
"""
from __future__ import annotations

from pathlib import Path

from .. import artifact_store
from ..errors import StateNotFoundError
from ..state import Clock, load_state


def _display_path(base: Path, path: str) -> Path:
    file_path = Path(path)
    return file_path if file_path.is_absolute() else Path(base) / file_path


def _metadata_lines(record: dict) -> list[str]:
    return [f"{key}: {record[key]}" for key in artifact_store.ARTIFACT_RECORD_KEYS]


def run_artifact(args, *, clock: Clock) -> int:
    base = Path(args.dir)
    try:
        state = load_state(base)
    except StateNotFoundError:
        print('No ProjectPilot state found. Run `pp init "<idea>"` first.')
        return 1

    command = args.artifact_command
    if command == "add":
        try:
            record = artifact_store.add_artifact(
                base,
                _display_path(base, args.file),
                state.current_phase.value,
                clock=clock,
            )
        except (FileNotFoundError, ValueError) as exc:
            print(str(exc))
            return 1
        print(f"Registered artifact: {record['id']}")
        return 0

    if command == "list":
        if getattr(args, "json", False):
            print(artifact_store.dumps_inventory(base), end="")
            return 0
        records = artifact_store.list_artifacts(base)
        if not records:
            print("No artifacts registered.")
            return 0
        print("Registered artifacts")
        print("")
        for record in records:
            print(
                f"- {record['id']}  {record['path']}  "
                f"[{record['type']}, {record['phase']}, {record['status']}]"
            )
        return 0

    if command == "show":
        record = artifact_store.find_artifact(base, args.id)
        if record is None:
            print(f"No artifact found with id '{args.id}'.")
            return 1
        print("\n".join(_metadata_lines(record)))
        return 0

    if command == "remove":
        removed = artifact_store.remove_artifact(base, args.id)
        if removed is None:
            print(f"No artifact found with id '{args.id}'.")
            return 1
        print(f"Removed artifact: {removed['id']}")
        return 0

    raise AssertionError(f"unknown artifact command: {command!r}")  # pragma: no cover
