"""``pp execution approve`` -- manual gate from planning to execution."""
from __future__ import annotations

from pathlib import Path

from ..errors import StateNotFoundError
from ..phases import Phase
from ..state import Clock, load_state, save_state


def run_execution_approve(args, *, clock: Clock) -> int:
    base = Path(args.dir)
    try:
        state = load_state(base)
    except StateNotFoundError:
        print('No ProjectPilot state found. Run `pp init "<idea>"` first.')
        return 1

    if state.current_phase != Phase.PLANNING:
        print(
            "Execution approval is only available during the 'planning' phase; "
            f"current phase is '{state.current_phase.value}'."
        )
        return 1

    if not state.ateam_check:
        print("No A-team readiness check found. Run `pp check-ateam` first.")
        return 1

    # A hand-edited check without a 'ready' flag counts as not ready (strict gate).
    ateam_ready = bool(state.ateam_check.get("ready", False))
    if not ateam_ready and not args.override:
        print(
            "A-team check is not ready. Re-run with --override to approve manually."
        )
        return 1

    now = clock()
    state.execution_approval = {
        "approved_at": now,
        "reason": args.reason,
        "source": "manual",
        "override": bool(args.override),
        "ateam_ready_at_approval": ateam_ready,
    }
    state.current_phase = Phase.EXECUTION
    state.updated_at = now
    state.history.append(
        {
            "event": "execution_approved",
            "phase": Phase.EXECUTION.value,
            "timestamp": now,
            "override": bool(args.override),
            "ateam_ready_at_approval": ateam_ready,
        }
    )
    save_state(base, state)

    print("Execution approved manually.")
    if args.override:
        print("Override recorded.")
    print("Advanced to phase 'execution'.")
    return 0
