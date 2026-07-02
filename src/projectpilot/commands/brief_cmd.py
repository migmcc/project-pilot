"""``pp brief import`` -- ingest an externally produced Project Brief.

The brief's content and quality are owned by whatever process produced it (for
example SkillLab). ProjectPilot only copies the supplied file into the project,
records provenance metadata, and advances the lifecycle.
"""
from __future__ import annotations

from pathlib import Path

from ..errors import StateNotFoundError
from ..phases import Phase
from ..state import Clock, load_state, save_state

BRIEF_FILENAME = "PROJECT_BRIEF.md"


def run_brief_import(args, *, clock: Clock) -> int:
    base = Path(args.dir)
    try:
        state = load_state(base)
    except StateNotFoundError:
        print('No ProjectPilot state found. Run `pp init "<idea>"` first.')
        return 1

    if state.current_phase != Phase.BRIEF:
        print(
            "Brief import is only available during the 'brief' phase; current phase is "
            f"'{state.current_phase.value}'."
        )
        return 1

    source = Path(args.path)
    if not source.is_file():
        print(f"Brief source file not found: {source}")
        return 1

    target = base / BRIEF_FILENAME
    if target.exists() and not args.force:
        print(f"{BRIEF_FILENAME} already exists. Re-run with --force to replace it.")
        return 1

    target.write_bytes(source.read_bytes())

    now = clock()
    state.brief = {
        "brief_path": BRIEF_FILENAME,
        "brief_imported_at": now,
        "source_path": str(source.resolve()),
    }
    state.current_phase = Phase.SETUP_ADVICE
    state.updated_at = now
    state.history.append(
        {
            "event": "brief_imported",
            "phase": Phase.SETUP_ADVICE.value,
            "timestamp": now,
            "brief_path": BRIEF_FILENAME,
            "source_path": str(source.resolve()),
        }
    )
    save_state(base, state)

    print(f"Imported brief to {BRIEF_FILENAME}.")
    print("Advanced to phase 'setup-advice'.")
    return 0
