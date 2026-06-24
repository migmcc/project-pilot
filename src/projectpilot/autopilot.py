"""Agent-driven autopilot engine (v0.2).

Advances the lifecycle through deterministic, safe steps by reusing the existing
v0.1 command functions, stopping at the first human gate. Writes local
coordination files (``NEXT_ACTION.md``, ``ACTION_REQUIRED.md``).

It spawns no processes and performs no network, GitHub, or LLM calls, and never
executes the project, SkillLab, the A-team, or AgentDesk. Instructions written to
the coordination files only ever name safe ``pp`` commands or human SkillLab/A-team
steps -- never push, tag, release, or install.
"""
from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from .commands.advance_cmd import run_advance
from .commands.setup_advice_cmd import run_advise_setup
from .commands.validate_cmd import run_validate
from .phases import Phase
from .state import Clock, ProjectState, load_state, state_dir

NEXT_ACTION_FILENAME = "NEXT_ACTION.md"
ACTION_REQUIRED_FILENAME = "ACTION_REQUIRED.md"

# Safety bound: the lifecycle has 8 phases, so the autopilot can never need more
# than that many forward steps. Guards against any unexpected non-advancing loop.
_MAX_STEPS = 16


@dataclass
class AutopilotResult:
    steps: list[str] = field(default_factory=list)
    blocked: bool = False
    phase: Phase = Phase.IDEA
    gate: str | None = None
    action: str | None = None


def _args(base: Path, **extra) -> SimpleNamespace:
    return SimpleNamespace(dir=str(base), **extra)


def _silent(fn, args, *, clock: Clock) -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        fn(args, clock=clock)


def _run_step(base: Path, fn, *, clock: Clock, target: str | None = None) -> bool:
    """Run a v0.1 step and report whether it advanced the phase."""
    before = load_state(base).current_phase
    args = _args(base, target=target) if target is not None else _args(base)
    _silent(fn, args, clock=clock)
    after = load_state(base).current_phase
    return after != before


def _gate_for(phase: Phase, state: ProjectState) -> tuple[str, str]:
    """Return (gate label, required human action) for a blocking phase."""
    if phase is Phase.VALIDATION:
        decision = state.decision
        if decision and decision.get("decision") != "APPROVED":
            value = decision["decision"]
            return (
                f"Decision is {value}; APPROVED required",
                f"The recorded decision is {value}. Return to SkillLab validation/rework, "
                'then record a new decision: pp decision set <APPROVED|NEEDS_REWORK|REJECTED> '
                '--reason "...".',
            )
        return (
            "SkillLab decision required",
            "Run `/skilllab-start-project` with the idea, then record the decision:\n"
            '  pp decision set <APPROVED|NEEDS_REWORK|REJECTED> --reason "..."',
        )
    if phase is Phase.BRIEF:
        return (
            "SkillLab brief import required",
            "Provide the SkillLab PROJECT_BRIEF.md, then run:\n"
            "  pp brief import <path-to-PROJECT_BRIEF.md>",
        )
    if phase is Phase.PLANNING:
        return (
            "Execution approval required",
            "Ensure the A-team is ready (or use --override), then run:\n"
            '  pp execution approve --reason "..." [--override]',
        )
    if phase is Phase.EXECUTION:
        return (
            "Technical execution by the A-team",
            "Do the technical work with the A-team. When complete, run:\n"
            "  pp final-validation prepare",
        )
    if phase is Phase.FINAL_VALIDATION:
        return (
            "Final-validation sign-off required",
            'Complete the checklist, then run:\n  pp done approve --reason "..."',
        )
    return ("Manual review required", "Inspect `.project-pilot/status.json` and resolve manually.")


def run_autopilot(base: Path, *, clock: Clock) -> AutopilotResult:
    steps: list[str] = []
    for _ in range(_MAX_STEPS):
        state = load_state(base)
        phase = state.current_phase

        if phase is Phase.DONE:
            return AutopilotResult(steps=steps, blocked=False, phase=phase)

        if phase is Phase.IDEA:
            if _run_step(base, run_validate, clock=clock):
                steps.append("validate (idea -> validation)")
                continue
            return _blocked(steps, load_state(base))

        if phase is Phase.VALIDATION:
            decision = state.decision
            if decision and decision.get("decision") == "APPROVED":
                if _run_step(base, run_advance, clock=clock, target="brief"):
                    steps.append("advance brief (validation -> brief)")
                    continue
            return _blocked(steps, state)

        if phase is Phase.SETUP_ADVICE:
            if _run_step(base, run_advise_setup, clock=clock):
                steps.append("advise-setup (setup-advice -> planning)")
                continue
            return _blocked(steps, load_state(base))

        # BRIEF, PLANNING, EXECUTION, FINAL_VALIDATION and any other phase block.
        return _blocked(steps, state)

    # Safety: should be unreachable; stop rather than loop.
    return _blocked(steps, load_state(base))


def _blocked(steps: list[str], state: ProjectState) -> AutopilotResult:
    gate, action = _gate_for(state.current_phase, state)
    return AutopilotResult(
        steps=steps, blocked=True, phase=state.current_phase, gate=gate, action=action
    )


def _coord_path(base: Path, name: str) -> Path:
    return state_dir(base) / name


def write_next_action(base: Path, state: ProjectState, result: AutopilotResult, *, clock: Clock) -> Path:
    lines = [
        "# ProjectPilot - Next Action",
        "",
        f"Project: {state.name} ({state.slug})",
        f"Current phase: {state.current_phase.value}",
        f"Updated: {clock()}",
        "",
        "## What ProjectPilot just did",
    ]
    lines += [f"- {s}" for s in result.steps] if result.steps else ["- No automatic step was available."]
    lines += ["", "## Next action"]
    if result.blocked:
        lines.append(f"Human gate: {result.gate}. See ACTION_REQUIRED.md.")
        lines += ["", "## For the VSCode agent", result.action or ""]
    elif state.current_phase is Phase.DONE:
        lines.append("Project complete. No further action.")
    else:
        lines.append("Run `pp continue`.")
    path = _coord_path(base, NEXT_ACTION_FILENAME)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_or_clear_action_required(
    base: Path, state: ProjectState, result: AutopilotResult, *, clock: Clock
) -> Path | None:
    path = _coord_path(base, ACTION_REQUIRED_FILENAME)
    if not result.blocked:
        if path.exists():
            path.unlink()
        return None
    lines = [
        "# ProjectPilot - Action Required (human gate)",
        "",
        f"Project: {state.name} ({state.slug})",
        f"Phase: {state.current_phase.value}",
        f"Gate: {result.gate}",
        f"Updated: {clock()}",
        "",
        "## Why ProjectPilot stopped",
        "This step needs a human decision, approval, or artifact; ProjectPilot does not perform it.",
        "",
        "## Required human action",
        result.action or "",
        "",
        "## Boundary reminder",
        "ProjectPilot does not validate the idea, execute the project, or install/run external tools.",
        "SkillLab owns validation; the A-team is the execution engine; AgentDesk is optional.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def summary_lines(result: AutopilotResult) -> list[str]:
    out = []
    if result.steps:
        out.append("Autopilot steps:")
        out += [f"  - {s}" for s in result.steps]
    else:
        out.append("Autopilot: no automatic step was available.")
    if result.blocked:
        out.append(f"Stopped at human gate: {result.gate} (see .project-pilot/ACTION_REQUIRED.md).")
    elif result.phase is Phase.DONE:
        out.append("Lifecycle complete (phase 'done').")
    return out


def drive(base: Path, *, clock: Clock) -> AutopilotResult:
    """Run the autopilot and refresh the coordination files from state."""
    result = run_autopilot(base, clock=clock)
    state = load_state(base)
    write_next_action(base, state, result, clock=clock)
    write_or_clear_action_required(base, state, result, clock=clock)
    return result
