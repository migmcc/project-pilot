"""``pp analyze`` -- inspect the current project and suggest the next action.

Read-only: it reports what is on disk and never invents results.
"""
from __future__ import annotations

from pathlib import Path

from .. import detectors
from ..state import state_exists


def run_analyze(args) -> int:
    base = Path(args.dir)
    report = detectors.detect_stack(base)
    initialized = state_exists(base)

    lines = [f"ProjectPilot analyze: {base.resolve()}", ""]

    lines.append("Detected stack:")
    if report.markers:
        lines.extend(f"- {marker}" for marker in report.markers)
    else:
        lines.append("- (no recognizable stack markers)")

    languages = ", ".join(report.languages) if report.languages else "unknown"
    lines.append("")
    lines.append(f"Languages: {languages}")
    lines.append(f"Tests detected: {'yes' if report.has_tests else 'no'}")
    lines.append(f"CI detected: {'yes' if report.has_ci else 'no'}")
    lines.append(f"README detected: {'yes' if report.has_readme else 'no'}")

    kind = "new (little to build on yet)" if report.looks_new else "existing"
    lines.append("")
    lines.append(f"Project appears: {kind}")
    lines.append(f"ProjectPilot initialized: {'yes' if initialized else 'no'}")

    lines.append("")
    lines.append("Suggested next action:")
    if not initialized:
        lines.append('- Run `pp init "<idea>"` to start ProjectPilot tracking here.')
    else:
        lines.append("- Run `pp status` to see the current phase and gate.")
    if report.looks_new:
        lines.append(
            "- AgentDesk could help scaffold a brand-new project later "
            "(optional support, not required)."
        )
    else:
        lines.append(
            "- AgentDesk is optional here; the A-team remains the primary "
            "execution engine."
        )

    print("\n".join(lines))
    return 0
