"""Prompt builder: assemble a consolidated, agent-ready prompt for one skill.

This is a separate layer with a single job: gather the project's recorded
context, join it with a skill, and produce a Markdown document. It contains **no
skill discovery and no ranking** -- those belong to :mod:`projectpilot.skills`
and :mod:`projectpilot.recommend`. The skill is handed in as plain strings, so
this module never depends on how skills are found or scored.

It **calls no model and executes nothing**. The output is a prompt the user can
paste into Claude Code, Codex, ChatGPT, or any other agent. Everything written is
drawn from recorded state or the skill itself -- nothing is invented, and any
section without data is omitted. Given the same state and skill, the output is
byte-for-byte deterministic (no timestamps are generated here).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import artifact_store, graph_context, phase_requirements
from .phases import NEXT_ACTION, Phase, phase_label
from .state import ProjectState, state_dir

__all__ = [
    "OUTPUT_SUBDIR",
    "PromptContext",
    "collect_context",
    "build_prompt",
]

#: Where ``pp skill use`` writes prompts by default.
OUTPUT_SUBDIR = Path("projectpilot_outputs") / "prompts"

#: How many of the most recent history events to surface as "handoffs".
_MAX_HANDOFFS = 5

_GRAPH_CONTEXT_PHASES = frozenset(
    {
        Phase.PLANNING.value,
        Phase.EXECUTION.value,
        Phase.FINAL_VALIDATION.value,
    }
)

#: Known ProjectPilot-produced artifacts (relative to the project dir). Only the
#: ones that actually exist on disk are listed -- this never invents files.
_KNOWN_ARTIFACTS = (
    "PROJECT_BRIEF.md",
    ".project-pilot/status.json",
    ".project-pilot/NEXT_ACTION.md",
    ".project-pilot/ACTION_REQUIRED.md",
    ".project-pilot/RUN_LOG.md",
)

#: Deterministic guidance appended to every prompt. Generic; invents no project
#: facts and reiterates that ProjectPilot neither runs a model nor executes.
_INSTRUCTIONS = (
    "Apply the skill above using the project context provided.",
    "Produce the skill's output as a single, self-contained document.",
    "Use only the information stated above. If something needed is missing, ask"
    " before proceeding rather than inventing it.",
    "This prompt was prepared by ProjectPilot, which does not call any model or"
    " execute the skill. Run it in the agent of your choice (Claude Code, Codex,"
    " ChatGPT, ...).",
)


@dataclass
class PromptContext:
    """The grounded project context for a prompt. Empty fields are omitted later."""

    project_name: str | None = None
    phase_value: str | None = None
    phase_label: str | None = None
    objective: str | None = None
    current_state: str | None = None
    handoffs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    produced_files: list[str] = field(default_factory=list)
    registered_artifacts: list[str] = field(default_factory=list)
    #: Phase completion percentage (0-100), or ``None`` when not computed.
    completion: int | None = None
    #: Labels of the required artifacts still missing for the current phase.
    missing_requirements: list[str] = field(default_factory=list)
    graph_context_status: graph_context.GraphContextStatus | None = None


def _collect_handoffs(state: ProjectState) -> list[str]:
    handoffs: list[str] = []
    for entry in state.history[-_MAX_HANDOFFS:]:
        timestamp = entry.get("timestamp", "")
        event = entry.get("event", "?")
        phase = entry.get("phase", "")
        suffix = f" (phase: {phase})" if phase else ""
        handoffs.append(f"{timestamp} {event}{suffix}".strip())
    return handoffs


def _collect_notes(state: ProjectState) -> list[str]:
    """Gather grounded, recorded notes -- decision/approval reasons only."""
    notes: list[str] = []
    decision = state.decision
    if decision and decision.get("reason"):
        verdict = decision.get("decision", "decision")
        notes.append(f"Decision {verdict}: {decision['reason']}")
    approval = state.execution_approval
    if approval and approval.get("reason"):
        notes.append(f"Execution approval: {approval['reason']}")
    done = state.done_approval
    if done and done.get("reason"):
        notes.append(f"Closure: {done['reason']}")
    return notes


def _collect_files(base: Path) -> list[str]:
    """List ProjectPilot-produced artifacts that actually exist, as posix paths."""
    base = Path(base)
    files: list[str] = []
    for relative in _KNOWN_ARTIFACTS:
        if (base / relative).is_file():
            files.append(relative)
    outputs = base / "projectpilot_outputs"
    if outputs.is_dir():
        for path in sorted(outputs.rglob("*")):
            if path.is_file():
                files.append(path.relative_to(base).as_posix())
    # Deterministic order, no duplicates.
    seen: set[str] = set()
    ordered: list[str] = []
    for item in files:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _collect_artifacts(base: Path) -> list[str]:
    """List registered artifact metadata only; never read artifact content."""
    artifacts: list[str] = []
    for record in artifact_store.list_artifacts(base):
        artifacts.append(
            " | ".join(
                [
                    record["id"],
                    record["path"],
                    record["type"],
                    record["phase"],
                    record["status"],
                ]
            )
        )
    return artifacts


def collect_context(state: ProjectState, base: Path) -> PromptContext:
    """Collect grounded prompt context from recorded state and produced files.

    Pure with respect to the project: it reads ``state`` and the filesystem under
    ``base`` but never invents data. Sections with nothing to say stay empty and
    are dropped by :func:`build_prompt`.
    """
    phase = state.current_phase
    evaluation = phase_requirements.evaluate(phase, artifact_store.list_artifacts(base))
    return PromptContext(
        project_name=state.name or None,
        phase_value=phase.value,
        phase_label=phase_label(phase),
        objective=(state.idea or None),
        current_state=NEXT_ACTION.get(phase),
        handoffs=_collect_handoffs(state),
        notes=_collect_notes(state),
        produced_files=_collect_files(base),
        registered_artifacts=_collect_artifacts(base),
        completion=evaluation.completion,
        missing_requirements=[status.label for status in evaluation.missing],
        graph_context_status=graph_context.inspect_graph_context(base),
    )


def _section(title: str, body_lines: list[str]) -> list[str]:
    return [title, "-" * len(title), "", *body_lines, ""]


def _labelled(label: str, value: str) -> list[str]:
    return [f"{label}:", value, ""]


def _context_block(context: PromptContext) -> list[str]:
    """Build the inner lines of the Project context section, omitting empties."""
    lines: list[str] = []
    if context.objective:
        lines += _labelled("Objective", context.objective)
    if context.current_state:
        lines += _labelled("Current state", context.current_state)
    if context.handoffs:
        lines.append("Recent handoffs:")
        lines += [f"- {item}" for item in context.handoffs]
        lines.append("")
    if context.notes:
        lines.append("Notes:")
        lines += [f"- {item}" for item in context.notes]
        lines.append("")
    if context.produced_files:
        lines.append("Files produced by ProjectPilot:")
        lines += [f"- {item}" for item in context.produced_files]
        lines.append("")
    if context.registered_artifacts:
        lines.append("Registered artifacts:")
        lines += [f"- {item}" for item in context.registered_artifacts]
        lines.append("")
    if context.completion is not None:
        lines += _labelled("Phase completion", f"{context.completion}%")
        if context.missing_requirements:
            lines.append("Missing requirements:")
            lines += [f"- {item}" for item in context.missing_requirements]
            lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def build_prompt(
    context: PromptContext,
    *,
    skill_id: str,
    skill_name: str,
    skill_description: str,
    skill_body: str,
) -> str:
    """Assemble the consolidated prompt Markdown. Deterministic; omits empty sections."""
    out: list[str] = []
    if context.project_name:
        out += [f"Project: {context.project_name}", ""]
    out += ["Current phase:", context.phase_label or "(unknown)", ""]
    out += ["Selected skill:", skill_id, ""]

    context_lines = _context_block(context)
    if context_lines:
        out += _section("Project context", context_lines)

    status = context.graph_context_status
    if status is not None and context.phase_value in _GRAPH_CONTEXT_PHASES:
        directive = graph_context.render_query_directive(status, skill_name)
        if directive:
            out += _section("Context retrieval", directive.splitlines())

    skill_lines: list[str] = []
    if skill_description:
        skill_lines += [skill_description, ""]
    skill_lines.append(skill_body.strip() if skill_body.strip() else "(skill body unavailable)")
    out += _section("Skill", skill_lines)

    out += _section("Instructions", list(_INSTRUCTIONS))

    return "\n".join(out).rstrip() + "\n"
