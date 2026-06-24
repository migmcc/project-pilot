"""``pp done approve`` -- manual closure of the lifecycle.

Records a manual done approval and advances to the ``done`` phase. It validates
nothing automatically, makes no release, no push, and no GitHub call. The human
asserts the project is complete.
"""
from __future__ import annotations

from pathlib import Path

from ..errors import StateNotFoundError
from ..phases import Phase
from ..state import Clock, load_state, save_state


def run_done_approve(args, *, clock: Clock) -> int:
    base = Path(args.dir)
    try:
        state = load_state(base)
    except StateNotFoundError:
        print('No ProjectPilot state found. Run `pp init "<idea>"` first.')
        return 1

    if state.current_phase != Phase.FINAL_VALIDATION:
        print(
            "Done approval is only available during the 'final-validation' phase; "
            f"current phase is '{state.current_phase.value}'."
        )
        return 1

    now = clock()
    state.done_approval = {
        "approved_at": now,
        "reason": args.reason,
        "source": "manual",
    }
    state.current_phase = Phase.DONE
    state.updated_at = now
    state.history.append(
        {"event": "done_approved", "phase": Phase.DONE.value, "timestamp": now}
    )
    save_state(base, state)

    print("Done approved manually. Project marked 'done'.")
    print("No release, tag, or push was made by ProjectPilot.")
    return 0
