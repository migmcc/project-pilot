"""Workflow advisor: analyse project state and suggest the next logical step.

The advisor is ProjectPilot's orchestration brain in advice-only form. It reads
the current project state, spots gaps (missing artifacts, pending gates,
un-prepared recommended skills), and produces justified, prioritised
recommendations. It **executes nothing and calls no LLM** -- it only advises.

Design:

* It is a **separate layer**. It never reaches into the skill scanner or the
  prompt builder internals -- it consumes their *public* functions
  (:func:`skills.scan_skills`, :func:`recommend.rank`) and reads recorded state.
* The rules engine is a list of small, independent functions. Each takes an
  :class:`AdvisorContext` and returns zero or more :class:`Recommendation`
  objects. Adding a rule is: write a function, append it to :data:`RULES`.
* Everything is **deterministic**: the same state always yields the same
  recommendations in the same order, so the JSON output is stable for tooling.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import recommend, skills
from .errors import StateNotFoundError
from .phases import Phase, next_phase
from .state import ProjectState, load_state

PRIORITY_HIGH = "High"
PRIORITY_MEDIUM = "Medium"
PRIORITY_LOW = "Low"

#: Lower rank sorts first. Used to order recommendations deterministically.
_PRIORITY_RANK = {PRIORITY_HIGH: 0, PRIORITY_MEDIUM: 1, PRIORITY_LOW: 2}

#: Phases that come after the brief has been imported.
_PAST_BRIEF = frozenset(
    {Phase.SETUP_ADVICE, Phase.PLANNING, Phase.EXECUTION, Phase.FINAL_VALIDATION, Phase.DONE}
)

BRIEF_FILENAME = "PROJECT_BRIEF.md"
_PROMPTS_SUBDIR = Path("projectpilot_outputs") / "prompts"


@dataclass
class Recommendation:
    """A single justified suggestion. ``command``/``depends_on`` are optional."""

    priority: str
    action: str
    reason: str
    command: str | None = None
    depends_on: str | None = None

    def to_dict(self) -> dict:
        return {
            "priority": self.priority,
            "action": self.action,
            "reason": self.reason,
            "command": self.command,
            "depends_on": self.depends_on,
        }


@dataclass
class Advice:
    """The advisor's output: the phase, ordered recommendations, and a follow-up."""

    phase: Phase | None
    recommendations: list[Recommendation]
    followup: str | None

    def to_dict(self) -> dict:
        return {
            "phase": self.phase.value if self.phase else None,
            "followup": self.followup,
            "recommendations": [r.to_dict() for r in self.recommendations],
        }


@dataclass
class AdvisorContext:
    """Everything the rules need, gathered once via public interfaces."""

    base: Path
    state: ProjectState
    phase: Phase
    has_brief: bool
    has_handoffs: bool
    top_skill_id: str | None
    top_skill_prepared: bool

    @property
    def skill_ready_to_prepare(self) -> bool:
        """True when a recommended skill exists that has not been prepared yet."""
        return bool(self.top_skill_id) and not self.top_skill_prepared


def _phase_label(phase: Phase) -> str:
    return phase.value.replace("-", " ").title()


# --------------------------------------------------------------------------- #
# Rules. Each is small and independent; append to RULES to add a new one.
# --------------------------------------------------------------------------- #

def rule_use_recommended_skill(ctx: AdvisorContext) -> list[Recommendation]:
    """Suggest preparing the phase's top recommended skill (if not done yet)."""
    if not ctx.skill_ready_to_prepare:
        return []
    label = _phase_label(ctx.phase)
    return [
        Recommendation(
            priority=PRIORITY_HIGH,
            action=f"Prepare the recommended skill '{ctx.top_skill_id}'",
            reason=(
                f"'{ctx.top_skill_id}' is the top recommended skill for the {label} phase, "
                "and no prompt has been prepared for it yet."
            ),
            command=f"pp skill use {ctx.top_skill_id}",
            depends_on=f"Current {label} phase",
        )
    ]


def _phase_gate(ctx: AdvisorContext) -> tuple[str, str, str | None] | None:
    """Return ``(action, reason, command)`` for the current phase's gate, or None."""
    phase = ctx.phase
    if phase is Phase.IDEA:
        return ("Enter validation", "The idea has not been validated yet.", "pp validate")
    if phase is Phase.VALIDATION:
        decision = ctx.state.decision
        verdict = decision.get("decision") if decision else None
        if verdict == "APPROVED":
            return (
                "Advance to the brief phase",
                "The SkillLab decision is APPROVED; the project can move on.",
                "pp advance brief",
            )
        if verdict:
            return (
                "Record a new SkillLab decision",
                f"The recorded decision is {verdict}; an APPROVED decision is required to advance.",
                'pp approve decision APPROVED --reason "..."',
            )
        return (
            "Record the SkillLab decision",
            "Validation is pending a SkillLab decision.",
            'pp approve decision APPROVED --reason "..."',
        )
    if phase is Phase.BRIEF:
        return (
            "Import the Project Brief",
            "No brief has been imported for this project yet.",
            "pp brief import <path>",
        )
    if phase is Phase.SETUP_ADVICE:
        return ("Prepare setup advice", "Setup advice has not been prepared yet.", "pp advise-setup")
    if phase is Phase.PLANNING:
        return (
            "Approve the move to execution",
            "Planning must be signed off before execution begins.",
            'pp approve execution --reason "..."',
        )
    if phase is Phase.EXECUTION:
        return (
            "Prepare final validation",
            "Execution is underway; prepare final validation when the work is complete.",
            "pp final-validation prepare",
        )
    if phase is Phase.FINAL_VALIDATION:
        return (
            "Close the project",
            "Final validation must be signed off to finish the lifecycle.",
            'pp approve done --reason "..."',
        )
    return None  # DONE has no forward gate.


def rule_phase_gate(ctx: AdvisorContext) -> list[Recommendation]:
    """Recommend the current phase's formal next step / gate."""
    gate = _phase_gate(ctx)
    if gate is None:
        return []
    action, reason, command = gate
    # The gate is the top action unless there is a skill to prepare first.
    priority = PRIORITY_MEDIUM if ctx.skill_ready_to_prepare else PRIORITY_HIGH
    return [
        Recommendation(
            priority=priority,
            action=action,
            reason=reason,
            command=command,
            depends_on=f"Current {_phase_label(ctx.phase)} phase",
        )
    ]


def rule_missing_brief(ctx: AdvisorContext) -> list[Recommendation]:
    """Justify a missing Project Brief once the project is past the brief phase."""
    if ctx.phase in _PAST_BRIEF and not ctx.has_brief:
        return [
            Recommendation(
                priority=PRIORITY_MEDIUM,
                action="Provide the Project Brief",
                reason=(
                    f"The project is in the {_phase_label(ctx.phase)} phase but no "
                    f"{BRIEF_FILENAME} is present."
                ),
                command="pp brief import <path>",
                depends_on=f"Current {_phase_label(ctx.phase)} phase",
            )
        ]
    return []


def rule_no_handoffs(ctx: AdvisorContext) -> list[Recommendation]:
    """Nudge recording progress when no lifecycle handoffs exist yet."""
    if ctx.has_handoffs or ctx.phase is Phase.DONE:
        return []
    return [
        Recommendation(
            priority=PRIORITY_LOW,
            action="Record initial progress",
            reason="No lifecycle handoffs have been recorded yet.",
            command="pp continue",
        )
    ]


def rule_project_done(ctx: AdvisorContext) -> list[Recommendation]:
    """State that the lifecycle is complete."""
    if ctx.phase is not Phase.DONE:
        return []
    return [
        Recommendation(
            priority=PRIORITY_LOW,
            action="Project complete",
            reason="The lifecycle has reached 'done'; no further action is required.",
        )
    ]


#: The active rule set, evaluated in order. Append a function here to add a rule.
RULES: list[Callable[[AdvisorContext], list[Recommendation]]] = [
    rule_use_recommended_skill,
    rule_phase_gate,
    rule_missing_brief,
    rule_no_handoffs,
    rule_project_done,
]


def _top_recommended_skill(base: Path, phase: Phase) -> str | None:
    """Return the id of the phase's top recommended skill, via public APIs only."""
    found = skills.scan_skills(base)
    if not found:
        return None
    ranked = recommend.rank(found, recommend.keywords_for_phase(base, phase))
    return ranked[0].skill.skill_id if ranked else None


def _build_context(base: Path, state: ProjectState) -> AdvisorContext:
    phase = state.current_phase
    has_brief = bool(state.brief) or (base / BRIEF_FILENAME).is_file()
    top_skill_id = _top_recommended_skill(base, phase)
    top_skill_prepared = bool(top_skill_id) and (
        base / _PROMPTS_SUBDIR / f"{top_skill_id}.md"
    ).is_file()
    return AdvisorContext(
        base=base,
        state=state,
        phase=phase,
        has_brief=has_brief,
        has_handoffs=bool(state.history),
        top_skill_id=top_skill_id,
        top_skill_prepared=top_skill_prepared,
    )


def _followup(phase: Phase) -> str | None:
    nxt = next_phase(phase)
    if nxt is None:
        return None
    return (
        f"After clearing the {_phase_label(phase)} gate, ProjectPilot advances to the "
        f"{_phase_label(nxt)} phase. Review the work before advancing."
    )


def advise(base: Path) -> Advice:
    """Analyse the project at ``base`` and return justified, ordered recommendations.

    Deterministic: identical state yields identical output. When no project state
    exists, the single recommendation is to initialise ProjectPilot.
    """
    base = Path(base)
    try:
        state = load_state(base)
    except StateNotFoundError:
        return Advice(
            phase=None,
            recommendations=[
                Recommendation(
                    priority=PRIORITY_HIGH,
                    action="Initialize ProjectPilot",
                    reason="No project state was found in this directory.",
                    command='pp init "<idea>"',
                )
            ],
            followup=None,
        )

    ctx = _build_context(base, state)
    recommendations: list[Recommendation] = []
    for rule in RULES:
        recommendations.extend(rule(ctx))
    # Stable sort by priority preserves rule order within each priority band.
    recommendations.sort(key=lambda r: _PRIORITY_RANK[r.priority])
    return Advice(
        phase=state.current_phase,
        recommendations=recommendations,
        followup=_followup(state.current_phase),
    )
