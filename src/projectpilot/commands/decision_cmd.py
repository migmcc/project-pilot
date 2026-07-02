"""``pp decision set`` — record a manual decision (does NOT advance the phase).

The decision value itself is owned by your validation process (for example
SkillLab); this command only persists what the human reports back. Advancing to
the next phase is a separate, explicit step (``pp advance brief``).
"""
from __future__ import annotations

from pathlib import Path

from ..errors import StateNotFoundError
from ..phases import Phase
from ..state import Clock, load_state, save_state


def run_decision_set(args, *, clock: Clock) -> int:
    base = Path(args.dir)
    try:
        state = load_state(base)
    except StateNotFoundError:
        print('No ProjectPilot state found. Run `pp init "<idea>"` first.')
        return 1

    if state.current_phase != Phase.VALIDATION:
        print(
            "Decisions are recorded during the 'validation' phase; current phase is "
            f"'{state.current_phase.value}'. Run `pp validate` first."
        )
        return 1

    now = clock()
    state.decision = {
        "decision": args.decision,
        "reason": args.reason,
        "timestamp": now,
        "source": "manual",
        "current_stage": state.current_phase.value,
    }
    state.updated_at = now
    state.history.append(
        {
            "event": "decision",
            "decision": args.decision,
            "phase": state.current_phase.value,
            "timestamp": now,
        }
    )
    save_state(base, state)

    print(f"Recorded decision: {args.decision} (source: manual).")
    print("This does not advance the phase. When APPROVED, run `pp advance brief`.")
    return 0
