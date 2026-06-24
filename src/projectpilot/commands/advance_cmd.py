"""``pp advance brief`` -- gated transition into the ``brief`` phase.

Only succeeds when a decision is recorded and equals ``APPROVED`` and the current
phase is ``validation``. It changes the phase only; it does NOT generate
PROJECT_BRIEF.md (that lands in a later run).
"""
from __future__ import annotations

from pathlib import Path

from ..errors import StateNotFoundError
from ..phases import Phase
from ..state import Clock, load_state, save_state


def run_advance(args, *, clock: Clock) -> int:
    base = Path(args.dir)
    try:
        state = load_state(base)
    except StateNotFoundError:
        print('No ProjectPilot state found. Run `pp init "<idea>"` first.')
        return 1

    # argparse constrains target to "brief" for Run B.
    if state.current_phase != Phase.VALIDATION:
        print(f"Cannot advance to 'brief' from phase '{state.current_phase.value}'.")
        return 1

    decision = state.decision
    if not decision:
        print('No recorded decision. Run `pp decision set APPROVED --reason "..."` first.')
        return 1
    if decision["decision"] != "APPROVED":
        print(
            f"Decision is {decision['decision']}; APPROVED is required to advance to 'brief'."
        )
        return 1

    now = clock()
    state.current_phase = Phase.BRIEF
    state.updated_at = now
    state.history.append(
        {"event": "advance", "phase": Phase.BRIEF.value, "timestamp": now}
    )
    save_state(base, state)

    print("Advanced to phase 'brief'. PROJECT_BRIEF.md is not generated in this version.")
    return 0
