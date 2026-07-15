"""``pp dashboard`` -- a single, aggregated project overview (read-only).

Renders the :class:`~projectpilot.dashboard.Dashboard` snapshot as text or, with
``--json``, as deterministic JSON. ``--verbose`` adds completed/missing
requirements, the recommendation's reasoning, and an artifact metadata summary
(metadata only -- artifact contents are never read). No LLM, no execution.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import console
from .. import dashboard as dashboard_mod
from ..phases import phase_label

_BAR_WIDTH = 10


def _progress_bar(completion: int) -> str:
    filled_char, empty_char = console.glyphs(("█", "░"), ("#", "-"))
    filled = max(0, min(_BAR_WIDTH, round(completion / 100 * _BAR_WIDTH)))
    return f"{filled_char * filled}{empty_char * (_BAR_WIDTH - filled)} {completion}%"


def _context_lines(dash: dashboard_mod.Dashboard) -> list[str]:
    status = dash.graph_context_status
    if status is None or not status.enabled:
        return []
    return [
        "",
        "Knowledge context",
        "",
        "Provider: Graphify",
        f"Status: {status.state.title()}",
        f"Query budget: {status.query_budget} tokens",
    ]


def _render_text(dash: dashboard_mod.Dashboard, *, verbose: bool) -> list[str]:
    header = "Project Health"
    if dash.project_name:
        header += f": {dash.project_name}"
    lines = [header, ""]

    if not dash.initialized:
        lines.append("ProjectPilot is not initialized in this directory.")
        lines += _context_lines(dash)
        lines += _recommendation_lines(dash, verbose=verbose)
        return lines

    lines.append(f"Phase: {phase_label(dash.phase)}")
    lines.append(_progress_bar(dash.completion or 0))
    lines += ["", "Ready to progress:", "Yes" if dash.ready_to_progress else "No"]
    lines += _context_lines(dash)

    if verbose:
        lines += ["", "Completed requirements:"]
        lines += [f"- {key}" for key in dash.completed] or ["(none)"]
        lines += ["", "Missing requirements:"]
        lines += [f"- {key}" for key in dash.missing] or ["(none)"]

    lines += _recommendation_lines(dash, verbose=verbose)

    lines += ["", f"Artifacts ({len(dash.artifacts)})", ""]
    if dash.artifacts:
        for record in dash.artifacts:
            if verbose:
                lines.append(
                    f"{record['path']}  [{record['type']} | {record['phase']} | {record['status']}]"
                )
            else:
                lines.append(record["path"])
    else:
        lines.append("(none)")

    lines += ["", "Recommended skills", ""]
    if dash.recommended_skills:
        lines += list(dash.recommended_skills)
    else:
        lines.append("(none)")

    return lines


def _recommendation_lines(dash: dashboard_mod.Dashboard, *, verbose: bool) -> list[str]:
    lines = ["", "Top recommendation", ""]
    rec = dash.top_recommendation
    if rec is None:
        lines.append("(no recommendation)")
        return lines
    lines.append(rec.action)
    if verbose:
        lines.append(f"Reason: {rec.reason}")
    if rec.command:
        lines += ["", "Suggested command", "", rec.command]
    return lines


def run_dashboard(args) -> int:
    base = Path(args.dir)
    dash = dashboard_mod.collect(base)
    verbose = getattr(args, "verbose", False)

    if getattr(args, "json", False):
        print(json.dumps(dash.to_dict(verbose=verbose), indent=2, ensure_ascii=False))
        return 0

    print("\n".join(_render_text(dash, verbose=verbose)))
    return 0
