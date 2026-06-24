"""``pp status`` — show the current lifecycle phase and next action (read-only)."""
from __future__ import annotations

from pathlib import Path

from ..errors import StateNotFoundError
from ..phases import NEXT_ACTION, gate_for_next, next_phase
from ..state import load_state


def run_status(args) -> int:
    base = Path(args.dir)
    try:
        state = load_state(base)
    except StateNotFoundError:
        print(
            "No ProjectPilot state found here. "
            "Run `pp init \"<idea>\"` to start a project."
        )
        return 1

    upcoming = next_phase(state.current_phase)
    print(f"Project: {state.name} ({state.slug})")
    print(f"Current phase: {state.current_phase.value}")
    print(f"Next phase: {upcoming.value if upcoming else '(none — final phase)'}")
    print(f"Active gate: {gate_for_next(state.current_phase)}")
    print(f"Next action: {NEXT_ACTION[state.current_phase]}")
    return 0
