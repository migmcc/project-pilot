"""``pp execution approve`` -- manual gate from planning to execution."""
from __future__ import annotations

from pathlib import Path

from .. import artifact_store, phase_requirements
from ..errors import StateCorruptedError, StateNotFoundError
from ..phases import Phase
from ..state import Clock, load_state, save_state


def _requirements_warning(base: Path) -> str | None:
    """Advisory only: warn when planning evidence is incomplete at approval.

    Never blocks the approval. A corrupted inventory is skipped here on
    purpose -- it is advisory context, and the corruption is reported loudly
    by every command that actually reads the inventory.
    """
    try:
        artifacts = artifact_store.list_artifacts(base)
    except StateCorruptedError:
        return None
    evaluation = phase_requirements.evaluate(Phase.PLANNING, artifacts)
    if evaluation.ready_to_progress:
        return None
    missing = ", ".join(status.label for status in evaluation.missing)
    return (
        f"Warning: planning requirements are incomplete (missing: {missing}). "
        "The approval was recorded anyway."
    )


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
    warning = _requirements_warning(base)
    if warning:
        print(warning)
    print("Advanced to phase 'execution'.")
    return 0
