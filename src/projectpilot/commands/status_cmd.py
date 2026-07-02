"""``pp status`` -- show the current lifecycle phase and next action (read-only)."""
from __future__ import annotations

from pathlib import Path

from ..errors import StateNotFoundError
from ..phases import NEXT_ACTION, Phase, gate_for_next, next_phase
from ..state import load_state


def _decision_line(decision: dict | None) -> str:
    if not decision:
        return "Decision: none"
    reason = decision.get("reason", "")
    suffix = f" -- {reason}" if reason else ""
    return f"Decision: {decision['decision']} (source: {decision.get('source', 'unknown')}){suffix}"


def _brief_line(brief: dict | None) -> str:
    if not brief:
        return "Brief: not imported"
    source = brief.get("source_path", "unknown source")
    return f"Brief: {brief['brief_path']} imported from {source}"


def _setup_advice_line(setup_advice: dict | None) -> str:
    if not setup_advice:
        return "Setup advice: not prepared"
    return f"Setup advice: prepared at {setup_advice['prepared_at']}"


def _ateam_check_line(ateam_check: dict | None) -> str:
    if not ateam_check:
        return "A-team check: not run"
    if ateam_check["ready"]:
        return "A-team check: ready"
    missing = ", ".join(ateam_check["missing_paths"])
    return f"A-team check: not ready (missing: {missing})"


def _execution_approval_line(execution_approval: dict | None) -> str:
    if not execution_approval:
        return "Execution approval: not approved"
    override = " with override" if execution_approval["override"] else ""
    return (
        "Execution approval: approved"
        f"{override} -- {execution_approval['reason']}"
    )


def _final_validation_line(final_validation: dict | None) -> str:
    if not final_validation:
        return "Final validation: not prepared"
    return f"Final validation: prepared at {final_validation['prepared_at']}"


def _done_approval_line(done_approval: dict | None) -> str:
    if not done_approval:
        return "Done approval: not approved"
    return f"Done approval: approved at {done_approval['approved_at']} -- {done_approval['reason']}"


def _active_gate(state) -> str:
    if state.current_phase != Phase.VALIDATION:
        return gate_for_next(state.current_phase)

    decision = state.decision
    if not decision:
        return "Waiting for a recorded validation decision."
    if decision["decision"] == "APPROVED":
        return "APPROVED decision recorded; `pp advance brief` is available."
    return f"Decision is {decision['decision']}; APPROVED is required to advance."


def _next_action(state) -> str:
    if state.current_phase != Phase.VALIDATION:
        return NEXT_ACTION[state.current_phase]

    decision = state.decision
    if not decision:
        return 'Run `pp decision set <APPROVED|NEEDS_REWORK|REJECTED> --reason "..."`.'
    if decision["decision"] == "APPROVED":
        return "Run `pp advance brief`."
    return "Return to validation/rework, then record a new manual decision."


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
    print(_decision_line(state.decision))
    print(_brief_line(state.brief))
    print(_setup_advice_line(state.setup_advice))
    print(_ateam_check_line(state.ateam_check))
    print(_execution_approval_line(state.execution_approval))
    print(_final_validation_line(state.final_validation))
    print(_done_approval_line(state.done_approval))
    print(f"Active gate: {_active_gate(state)}")
    print(f"Next action: {_next_action(state)}")
    return 0
