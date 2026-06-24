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

#: Human hint for what to do at each phase. Each hint names a command that
#: already exists, except where the lifecycle has no further command yet.
NEXT_ACTION: dict[Phase, str] = {
    Phase.IDEA: "Run `pp validate` to enter validation and generate the SkillLab prompt.",
    Phase.VALIDATION: "Record the SkillLab decision with `pp decision set`.",
    Phase.BRIEF: "Import the SkillLab-approved brief with `pp brief import <path>`.",
    Phase.SETUP_ADVICE: "Prepare setup advice with `pp advise-setup`.",
    Phase.PLANNING: "Check readiness with `pp check-ateam`, then `pp execution approve`.",
    Phase.EXECUTION: "Drive execution with the A-team, then `pp final-validation prepare`.",
    Phase.FINAL_VALIDATION: "Complete the checklist, then `pp done approve --reason \"...\"`.",
    Phase.DONE: "Project complete.",
}

#: Description of the gate guarding entry into the *next* phase.
GATE_FOR_NEXT: dict[Phase, str] = {
    Phase.IDEA: "Run `pp validate` to proceed.",
    Phase.VALIDATION: "An APPROVED decision is required to advance.",
    Phase.BRIEF: "An imported brief is required to advance.",
    Phase.SETUP_ADVICE: "Setup advice must be prepared to advance.",
    Phase.PLANNING: "A-team readiness or an explicit override is required to advance.",
    Phase.EXECUTION: "Execution must be complete and reviewed to advance.",
    Phase.FINAL_VALIDATION: "Final validation must be complete to advance.",
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
