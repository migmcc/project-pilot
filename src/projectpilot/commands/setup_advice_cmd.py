"""``pp advise-setup`` -- deterministic manual setup advice."""
from __future__ import annotations

from pathlib import Path

from ..errors import StateNotFoundError
from ..phases import Phase
from ..state import Clock, load_state, save_state

RECOMMENDED_BUILDERS = [
    "A-team (example execution toolkit) for serious or active project work",
    "minimal builders only",
]

READINESS_CHECKS = [
    "Install your execution toolkit (e.g. the A-team) in the project repo if this is a serious or active project",
    "Install only minimal builders",
    "Fill INIT.md",
    "Run /orchestrate init",
    "Review .agent-sync/TEAM.md",
    "Review .agent-sync/ROUTING.md",
    "Only then advance to technical execution",
    "AgentDesk is optional support, not a replacement for A-team",
]


def _render_advice() -> str:
    lines = [
        "Setup advice prepared.",
        "",
        "Recommended builders:",
        *[f"- {item}" for item in RECOMMENDED_BUILDERS],
        "",
        "Manual readiness checks:",
        *[f"- {item}" for item in READINESS_CHECKS],
        "",
        "These checks reflect one example workflow (the A-team convention);",
        "adapt them to your own toolkit.",
        "",
        "No tools were installed or executed by ProjectPilot.",
    ]
    return "\n".join(lines)


def run_advise_setup(args, *, clock: Clock) -> int:
    base = Path(args.dir)
    try:
        state = load_state(base)
    except StateNotFoundError:
        print('No ProjectPilot state found. Run `pp init "<idea>"` first.')
        return 1

    if state.current_phase != Phase.SETUP_ADVICE:
        print(
            "Setup advice is only available during the 'setup-advice' phase; "
            f"current phase is '{state.current_phase.value}'."
        )
        return 1

    if not state.brief:
        print("No imported brief found. Run `pp brief import <path>` first.")
        return 1

    now = clock()
    state.setup_advice = {
        "prepared_at": now,
        "recommended_builders": list(RECOMMENDED_BUILDERS),
        "readiness_checks": list(READINESS_CHECKS),
        "source": "deterministic",
    }
    state.current_phase = Phase.PLANNING
    state.updated_at = now
    state.history.append(
        {
            "event": "setup_advice_prepared",
            "phase": Phase.PLANNING.value,
            "timestamp": now,
        }
    )
    save_state(base, state)

    print(_render_advice())
    print("")
    print("Advanced to phase 'planning'.")
    return 0
