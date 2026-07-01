"""``pp phase check`` -- report the current phase's artifact requirements.

Consults the Phase Requirements Engine (the single source of truth) and prints
which required/optional artifacts are satisfied, the completion percentage, and
whether the phase is ready to progress. Read-only: it inspects only artifact
metadata via the engine and never reads artifact contents. ``--json`` emits a
deterministic machine-readable form; ``--verbose`` adds optional requirements.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import artifact_store, console, phase_requirements
from ..errors import StateNotFoundError
from ..phases import phase_label
from ..state import load_state


def _status_lines(statuses, tick, cross) -> list[str]:
    lines = []
    for status in statuses:
        mark = tick if status.satisfied else cross
        lines.append(f"{mark} {status.label}")
    return lines


def run_phase_check(args) -> int:
    base = Path(args.dir)
    try:
        state = load_state(base)
    except StateNotFoundError:
        print('No ProjectPilot state found. Run `pp init "<idea>"` first.')
        return 1

    artifacts = artifact_store.list_artifacts(base)
    evaluation = phase_requirements.evaluate(state.current_phase, artifacts)

    if getattr(args, "json", False):
        print(json.dumps(evaluation.to_dict(), indent=2, ensure_ascii=False))
        return 0

    verbose = getattr(args, "verbose", False)
    tick, cross = console.glyphs(("✓", "✗"), ("[x]", "[ ]"))

    lines = [f"Current phase: {phase_label(state.current_phase)}", "", "Requirements", ""]

    required = evaluation.required_statuses
    if required:
        lines += _status_lines(required, tick, cross)
    else:
        lines.append("(no required artifacts for this phase)")

    optional = evaluation.optional_statuses
    if optional and verbose:
        lines += ["", "Optional", ""]
        lines += _status_lines(optional, tick, cross)

    lines += ["", "Completion", "", f"{evaluation.completion}%"]
    lines += ["", "Ready to progress", "", "Yes" if evaluation.ready_to_progress else "No"]

    print("\n".join(lines))
    return 0
