"""``pp next`` -- the Workflow Advisor: suggest the next logical step (advice only).

Reads the project state and prints justified, prioritised recommendations. It
executes nothing and calls no LLM. ``--json`` emits a deterministic machine
-readable form; ``--verbose`` adds each recommendation's dependencies.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import advisor
from ..phases import phase_label


def _render_text(advice: advisor.Advice, *, verbose: bool) -> list[str]:
    lines: list[str] = []
    if advice.phase is not None:
        lines.append(f"Current phase: {phase_label(advice.phase)}")
    else:
        lines.append("ProjectPilot is not initialized in this directory.")
    lines.append("")
    lines.append("Recommended next action")
    lines.append("")

    if not advice.recommendations:
        lines.append("Nothing to recommend right now.")
        return lines

    for index, rec in enumerate(advice.recommendations, start=1):
        lines.append(f"{index}. {rec.action}")
        lines.append(f"   Priority: {rec.priority}")
        lines.append(f"   Reason: {rec.reason}")
        if rec.command:
            lines.append(f"   Suggested command: {rec.command}")
        if verbose and rec.depends_on:
            lines.append(f"   Depends on: {rec.depends_on}")
        lines.append("")

    if advice.followup:
        lines.append(advice.followup)
    return lines


def run_next(args) -> int:
    base = Path(args.dir)
    advice = advisor.advise(base)

    if getattr(args, "json", False):
        print(json.dumps(advice.to_dict(), indent=2, ensure_ascii=False))
        return 0

    verbose = getattr(args, "verbose", False)
    print("\n".join(_render_text(advice, verbose=verbose)).rstrip())
    return 0
