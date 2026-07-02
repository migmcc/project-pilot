"""``pp validate`` — internal pre-check + validation prompt generation.

This command does NOT validate the quality of the idea. Idea validation belongs
to an external process of your choice (for example the SkillLab library).
ProjectPilot only verifies its own internal preconditions, moves the project
into the ``validation`` phase, and emits a prompt describing the human step.
The decision is recorded later, by hand, via ``pp decision set``.
"""
from __future__ import annotations

from pathlib import Path

from ..errors import StateNotFoundError
from ..phases import Phase
from ..state import Clock, ProjectState, load_state, save_state


def _render_prompt(state: ProjectState) -> str:
    return (
        "# Idea validation prompt\n\n"
        f"Project: {state.name} ({state.slug})\n"
        f"Idea: {state.idea}\n\n"
        "ProjectPilot does not validate the idea itself. Validate it with the process\n"
        "of your choice -- a validation skill, a team review, or your own judgement --\n"
        "and produce a decision plus a PROJECT_BRIEF.md. For example, with SkillLab:\n\n"
        f"    /skilllab-start-project {state.idea}\n\n"
        "Then record the decision your process produced (the decision is never made\n"
        "by ProjectPilot):\n\n"
        '    pp decision set <APPROVED|NEEDS_REWORK|REJECTED> --reason "..."\n'
    )


def run_validate(args, *, clock: Clock) -> int:
    base = Path(args.dir)
    try:
        state = load_state(base)
    except StateNotFoundError:
        print('No ProjectPilot state found. Run `pp init "<idea>"` first.')
        return 1

    if state.current_phase not in (Phase.IDEA, Phase.VALIDATION):
        print(f"Cannot run validate from phase '{state.current_phase.value}'.")
        return 1

    now = clock()
    if state.current_phase == Phase.IDEA:
        state.current_phase = Phase.VALIDATION
    state.updated_at = now
    state.history.append(
        {"event": "validate", "phase": Phase.VALIDATION.value, "timestamp": now}
    )
    save_state(base, state)

    print(_render_prompt(state))
    return 0
