"""Canonical lifecycle phases (decision D5) and ordered transitions.

Phase catalogue, in order:

    idea -> validation -> brief -> setup-advice -> planning -> execution
         -> final-validation -> done
"""
from __future__ import annotations

from enum import Enum

from .errors import UnknownPhaseError


class Phase(str, Enum):
    IDEA = "idea"
    VALIDATION = "validation"
    BRIEF = "brief"
    SETUP_ADVICE = "setup-advice"
    PLANNING = "planning"
    EXECUTION = "execution"
    FINAL_VALIDATION = "final-validation"
    DONE = "done"


#: The canonical ordered catalogue (D5).
PHASE_ORDER: list[Phase] = [
    Phase.IDEA,
    Phase.VALIDATION,
    Phase.BRIEF,
    Phase.SETUP_ADVICE,
    Phase.PLANNING,
    Phase.EXECUTION,
    Phase.FINAL_VALIDATION,
    Phase.DONE,
]

#: Human hint for what comes next at each phase. Items marked "(future:" name
#: commands that land in later runs — Run A only ships ``init`` and ``status``.
NEXT_ACTION: dict[Phase, str] = {
    Phase.IDEA: "Generate the SkillLab validation prompt (future: pp validate).",
    Phase.VALIDATION: "Record the SkillLab decision (future: pp decision set).",
    Phase.BRIEF: "Generate PROJECT_BRIEF.md (future: pp brief).",
    Phase.SETUP_ADVICE: "Get A-Team / minimal-builders advice (future: pp advise-setup).",
    Phase.PLANNING: "Generate the run-organised plan (future: pp plan).",
    Phase.EXECUTION: "Drive execution with the A-Team (future: pp next).",
    Phase.FINAL_VALIDATION: "Run the final-validation checklist (future: pp finalize).",
    Phase.DONE: "Project complete.",
}

#: Description of the gate guarding entry into the *next* phase.
GATE_FOR_NEXT: dict[Phase, str] = {
    Phase.IDEA: "SkillLab validation must produce a recorded decision (future).",
    Phase.VALIDATION: "Recorded decision must be APPROVED to advance (future).",
    Phase.BRIEF: "none",
    Phase.SETUP_ADVICE: "none",
    Phase.PLANNING: "A-Team must be operational, or an explicit override (future).",
    Phase.EXECUTION: "Execution complete and reviewed (future).",
    Phase.FINAL_VALIDATION: "Final-validation checklist complete (future).",
    Phase.DONE: "none",
}


def next_phase(phase: Phase) -> Phase | None:
    """Return the phase that follows ``phase``, or ``None`` for the terminal phase."""
    index = PHASE_ORDER.index(phase)
    if index + 1 < len(PHASE_ORDER):
        return PHASE_ORDER[index + 1]
    return None


def gate_for_next(phase: Phase) -> str:
    """Return the gate description guarding entry into the next phase."""
    return GATE_FOR_NEXT[phase]


def phase_from_str(value: str) -> Phase:
    """Parse a phase name, raising :class:`UnknownPhaseError` if it is not valid."""
    try:
        return Phase(value)
    except ValueError:
        raise UnknownPhaseError(f"Unknown phase: {value!r}") from None
