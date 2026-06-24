"""``pp final-validation prepare`` -- deterministic manual final-validation gate.

Generates a manual final-validation checklist and advances to the
``final-validation`` phase. It executes nothing: no tests, no public-repo audit,
no skill quality gate, no network. The human performs the checks.
"""
from __future__ import annotations

from pathlib import Path

from ..errors import StateNotFoundError
from ..phases import Phase
from ..state import Clock, load_state, save_state

REQUIRED_CHECKS = [
    "All unit tests green (python -m unittest discover -s tests -t .)",
    "no-automation guard green (python -m unittest tests.test_no_automation)",
    "README up to date",
    "CHANGELOG updated if applicable",
    "public-repo-audit run manually if the repo is public",
    "skill quality gate run manually if skills are shipped",
    "git status clean",
    "release and tag only manually, outside ProjectPilot",
]


def _render_checklist() -> str:
    lines = [
        "Final validation checklist prepared (manual; ProjectPilot runs nothing).",
        "",
        "Required checks:",
        *[f"- {item}" for item in REQUIRED_CHECKS],
    ]
    return "\n".join(lines)


def run_final_validation_prepare(args, *, clock: Clock) -> int:
    base = Path(args.dir)
    try:
        state = load_state(base)
    except StateNotFoundError:
        print('No ProjectPilot state found. Run `pp init "<idea>"` first.')
        return 1

    if state.current_phase != Phase.EXECUTION:
        print(
            "Final validation is only available during the 'execution' phase; "
            f"current phase is '{state.current_phase.value}'."
        )
        return 1

    now = clock()
    state.final_validation = {
        "prepared_at": now,
        "required_checks": list(REQUIRED_CHECKS),
        "source": "deterministic",
    }
    state.current_phase = Phase.FINAL_VALIDATION
    state.updated_at = now
    state.history.append(
        {
            "event": "final_validation_prepared",
            "phase": Phase.FINAL_VALIDATION.value,
            "timestamp": now,
        }
    )
    save_state(base, state)

    print(_render_checklist())
    print("")
    print("Advanced to phase 'final-validation'.")
    return 0
