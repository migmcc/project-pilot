"""Phase Requirements Engine: which artifacts each phase expects, and how complete.

This is a small, deterministic engine that answers one question: *for the current
phase, which expected artifacts are present and which are missing?* It is the
single source of truth for phase completeness, so the workflow advisor and the
prompt builder can reason about "readiness" without each re-deriving the rules.

Design constraints (all satisfied here):

* **stdlib only, no LLM, no network, no process spawning, no dependencies.**
* **No CLI logic, no workflow logic, no artifact persistence.** The engine takes
  a phase plus already-loaded artifact records (the public shape produced by
  :mod:`projectpilot.artifact_store`) and returns a plain evaluation object.
* **Deterministic.** The same inputs always yield the same output and ordering.

The requirement catalogue is intentionally generic and easily extensible: add a
:class:`Requirement` to a phase's ``required``/``optional`` tuple in
:data:`REQUIREMENTS`. Nothing here is tied to a particular skill library.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .phases import Phase

__all__ = [
    "Requirement",
    "PhaseRequirements",
    "REQUIREMENTS",
    "RequirementStatus",
    "PhaseEvaluation",
    "requirements_for",
    "evaluate",
]

# Completion is measured over *required* artifacts. ``threshold`` is the fraction
# of required artifacts that must be present for the phase to be "ready to
# progress" (1.0 = all required). Optional artifacts are advisory only: they are
# reported but never affect completion or readiness.
_DEFAULT_THRESHOLD = 1.0


@dataclass(frozen=True)
class Requirement:
    """One expected artifact type, matched against registered artifact metadata.

    ``key`` is a stable machine identifier, ``label`` is the human name, and
    ``keywords`` are the lowercase terms that, when found in an artifact's
    id/path/name, mark the requirement satisfied.
    """

    key: str
    label: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class PhaseRequirements:
    required: tuple[Requirement, ...] = ()
    optional: tuple[Requirement, ...] = ()
    threshold: float = _DEFAULT_THRESHOLD


# --------------------------------------------------------------------------- #
# Requirement catalogue. Generic and extensible -- edit these tuples to change
# what a phase expects; every other layer follows automatically.
# --------------------------------------------------------------------------- #

_BRIEF = Requirement("brief", "Project Brief", ("brief", "project brief"))
_MARKET_RESEARCH = Requirement("market-research", "Market Research", ("market research", "market", "research"))
_VALIDATION = Requirement("validation", "Validation Evidence", ("validation", "validate"))
_PRD = Requirement("prd", "PRD", ("prd", "product requirements", "product requirement"))
_ROADMAP = Requirement("roadmap", "Roadmap", ("roadmap",))
_RISK = Requirement("risk-analysis", "Risk Analysis", ("risk analysis", "risk", "pre mortem", "premortem"))
_ARCHITECTURE = Requirement("architecture", "Architecture", ("architecture", "arch"))
_IMPL_PLAN = Requirement("implementation-plan", "Implementation Plan", ("implementation plan", "impl plan"))
_DESIGN_REVIEW = Requirement("design-review", "Design Review", ("design review",))
_SECURITY_REVIEW = Requirement("security-review", "Security Review", ("security review", "security"))
_TEST_REPORT = Requirement("test-report", "Test Report", ("test report", "test results", "qa report", "qa"))
_RELEASE_NOTES = Requirement("release-notes", "Release Notes", ("release notes", "changelog"))
_RETROSPECTIVE = Requirement("retrospective", "Retrospective", ("retrospective", "retro"))

#: Per-phase expectations. Add or edit entries to extend the engine.
REQUIREMENTS: dict[Phase, PhaseRequirements] = {
    Phase.IDEA: PhaseRequirements(optional=(_MARKET_RESEARCH,)),
    Phase.VALIDATION: PhaseRequirements(optional=(_VALIDATION, _MARKET_RESEARCH)),
    Phase.BRIEF: PhaseRequirements(required=(_BRIEF,)),
    Phase.SETUP_ADVICE: PhaseRequirements(),
    Phase.PLANNING: PhaseRequirements(
        required=(_PRD, _ROADMAP), optional=(_RISK, _ARCHITECTURE)
    ),
    Phase.EXECUTION: PhaseRequirements(
        required=(_IMPL_PLAN,), optional=(_DESIGN_REVIEW, _SECURITY_REVIEW)
    ),
    Phase.FINAL_VALIDATION: PhaseRequirements(
        required=(_TEST_REPORT,), optional=(_SECURITY_REVIEW,)
    ),
    Phase.DONE: PhaseRequirements(optional=(_RELEASE_NOTES, _RETROSPECTIVE)),
}


@dataclass(frozen=True)
class RequirementStatus:
    """The evaluation of one requirement against the registered artifacts."""

    key: str
    label: str
    required: bool
    satisfied: bool
    artifact_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "required": self.required,
            "satisfied": self.satisfied,
            "artifact_id": self.artifact_id,
        }


@dataclass
class PhaseEvaluation:
    """The completeness of a phase given the registered artifacts."""

    phase: Phase
    statuses: list[RequirementStatus] = field(default_factory=list)
    completion: int = 100
    ready_to_progress: bool = True

    @property
    def required_statuses(self) -> list[RequirementStatus]:
        return [s for s in self.statuses if s.required]

    @property
    def optional_statuses(self) -> list[RequirementStatus]:
        return [s for s in self.statuses if not s.required]

    @property
    def completed(self) -> list[RequirementStatus]:
        return [s for s in self.required_statuses if s.satisfied]

    @property
    def missing(self) -> list[RequirementStatus]:
        return [s for s in self.required_statuses if not s.satisfied]

    def to_dict(self) -> dict:
        """Deterministic JSON shape with stable key ordering."""
        return {
            "phase": self.phase.value,
            "completion": self.completion,
            "ready_to_progress": self.ready_to_progress,
            "completed": [s.key for s in self.completed],
            "missing": [s.key for s in self.missing],
        }


_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _normalise(text: str) -> str:
    """Lowercase and collapse non-alphanumeric runs to single spaces."""
    return _NON_ALNUM.sub(" ", text.lower()).strip()


def _artifact_text(record: dict) -> str:
    fields = " ".join(
        str(record.get(key, "")) for key in ("id", "path", "name", "type")
    )
    return f" {_normalise(fields)} "


def _matches(artifact_text: str, requirement: Requirement) -> bool:
    """True if any of the requirement's keywords appears as a whole token run."""
    for keyword in requirement.keywords:
        needle = f" {_normalise(keyword)} "
        if needle in artifact_text:
            return True
    return False


def _first_match(artifacts: list[dict], texts: list[str], requirement: Requirement) -> str | None:
    for record, text in zip(artifacts, texts):
        if _matches(text, requirement):
            return record.get("id")
    return None


def requirements_for(phase: Phase) -> PhaseRequirements:
    """Return the (possibly empty) requirements defined for ``phase``."""
    return REQUIREMENTS.get(phase, PhaseRequirements())


def evaluate(phase: Phase, artifacts: list[dict]) -> PhaseEvaluation:
    """Evaluate ``phase`` completeness against ``artifacts`` (pure, deterministic).

    ``artifacts`` are records in :mod:`projectpilot.artifact_store` shape. The
    engine only reads their metadata (id/path/name/type); it never touches file
    contents. Completion is the percentage of *required* artifacts registered.
    """
    reqs = requirements_for(phase)
    texts = [_artifact_text(record) for record in artifacts]

    statuses: list[RequirementStatus] = []
    for requirement in reqs.required:
        artifact_id = _first_match(artifacts, texts, requirement)
        statuses.append(
            RequirementStatus(
                key=requirement.key,
                label=requirement.label,
                required=True,
                satisfied=artifact_id is not None,
                artifact_id=artifact_id,
            )
        )
    for requirement in reqs.optional:
        artifact_id = _first_match(artifacts, texts, requirement)
        statuses.append(
            RequirementStatus(
                key=requirement.key,
                label=requirement.label,
                required=False,
                satisfied=artifact_id is not None,
                artifact_id=artifact_id,
            )
        )

    total_required = len(reqs.required)
    satisfied_required = sum(1 for s in statuses if s.required and s.satisfied)
    if total_required == 0:
        completion = 100
        ready = True
    else:
        fraction = satisfied_required / total_required
        completion = round(fraction * 100)
        ready = fraction >= reqs.threshold

    return PhaseEvaluation(
        phase=phase,
        statuses=statuses,
        completion=completion,
        ready_to_progress=ready,
    )
