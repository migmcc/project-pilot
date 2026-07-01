"""Skill recommendations: suggest which skills fit the current lifecycle phase.

This is a separate layer from the scanner (:mod:`projectpilot.skills`). The
scanner only *discovers* skills; the recommender *decides which to suggest*. The
two never depend on each other's internals -- the recommender consumes the
plain :class:`~projectpilot.skills.Skill` records the scanner produces.

The algorithm is deliberately simple, deterministic, and **uses no AI, no
embeddings, and no network**. Each lifecycle phase has a list of keyword/category
terms; a skill is scored by how well its id, name, category, and description
match those terms. The pure ranking core (:func:`rank`) takes skills + keywords
and returns an ordered list, so it is trivially testable and easy to replace with
a smarter ranker later.

Rules are configurable and generic -- nothing is hardcoded to any one library.
Built-in defaults use ordinary product-management / engineering vocabulary; a
project may override any phase's terms in ``.project-pilot/config.yaml`` with a
``recommend_<phase>`` list (e.g. ``recommend_planning``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from .config import load_mapping
from .phases import Phase
from .skills import Skill

__all__ = [
    "RULE_KEY_PREFIX",
    "MAX_STARS",
    "DEFAULT_RULES",
    "Recommendation",
    "category_of",
    "stars_string",
    "rank",
    "load_rules",
    "keywords_for_phase",
]

#: Config keys of the form ``recommend_<phase-value>`` override a phase's terms.
RULE_KEY_PREFIX = "recommend_"

#: Maximum stars shown for a recommendation.
MAX_STARS = 5

#: Built-in, generic phase -> keyword rules. These are ordinary domain terms, not
#: identifiers from any specific skill library, so any library benefits from them.
DEFAULT_RULES: dict[Phase, list[str]] = {
    Phase.IDEA: [
        "market", "research", "discovery", "problem", "opportunity",
        "customer", "interview", "idea", "validation",
    ],
    Phase.VALIDATION: [
        "validation", "validate", "problem", "assumption", "experiment",
        "research", "interview", "feedback", "evidence", "survey",
    ],
    Phase.BRIEF: [
        "prd", "brief", "requirement", "spec", "scope", "objective",
        "stakeholder", "vision", "strategy", "positioning",
    ],
    Phase.SETUP_ADVICE: [
        "setup", "plan", "planning", "roadmap", "estimate", "prioritization",
        "prioritize", "okr", "milestone", "story", "stories",
    ],
    Phase.PLANNING: [
        "prd", "requirement", "roadmap", "risk", "planning", "plan",
        "prioritization", "prioritize", "estimate", "stakeholder", "scope",
        "okr", "story", "stories", "premortem", "pre-mortem",
    ],
    Phase.EXECUTION: [
        "architecture", "technical", "implementation", "build", "review",
        "engineering", "design", "test", "sprint", "development", "code",
        "dataset", "scenario",
    ],
    Phase.FINAL_VALIDATION: [
        "test", "qa", "validation", "review", "acceptance", "release",
        "launch", "checklist", "scenario", "metrics",
    ],
    Phase.DONE: [
        "launch", "release", "documentation", "docs", "retrospective", "retro",
        "postmortem", "post-mortem", "announcement", "notes", "go-to-market",
    ],
}

# Field match weights. A term that appears in the id/name is a stronger signal
# than one that only appears in the category, which is stronger than one that
# appears only in the free-text description.
_WEIGHT_ID_NAME = 3
_WEIGHT_CATEGORY = 2
_WEIGHT_DESCRIPTION = 1


@dataclass
class Recommendation:
    """One scored skill suggestion. ``stars`` is a 1..:data:`MAX_STARS` rating."""

    skill: Skill
    score: int
    stars: int
    matched: list[str] = field(default_factory=list)


def category_of(skill: Skill) -> str:
    """Return a coarse category for a skill: its top-level folder under the source.

    For a layout like ``pm-skills/pm-execution/skills/create-prd/SKILL.md`` the
    category is ``pm-execution``. Falls back to the source directory name.
    """
    try:
        parts = Path(skill.path).resolve().relative_to(Path(skill.source).resolve()).parts
    except ValueError:
        return Path(skill.source).name
    return parts[0] if len(parts) > 1 else Path(skill.source).name


def _score_skill(skill: Skill, keywords: Sequence[str]) -> tuple[int, list[str]]:
    """Score one skill against ``keywords``. Returns ``(score, matched_terms)``.

    Each keyword contributes once, scored by the strongest field it appears in.
    Matching is lowercase substring matching -- simple and deterministic.
    """
    id_name = f"{skill.skill_id} {skill.name}".lower()
    category = category_of(skill).lower()
    description = (skill.description or "").lower()

    score = 0
    matched: list[str] = []
    for keyword in keywords:
        term = keyword.strip().lower()
        if not term:
            continue
        if term in id_name:
            score += _WEIGHT_ID_NAME
        elif term in category:
            score += _WEIGHT_CATEGORY
        elif term in description:
            score += _WEIGHT_DESCRIPTION
        else:
            continue
        matched.append(term)
    return score, matched


def _stars(score: int) -> int:
    """Map a raw score to a 1..:data:`MAX_STARS` rating (only called for score>0)."""
    if score >= 6:
        return 5
    if score >= 4:
        return 4
    if score >= 3:
        return 3
    if score >= 2:
        return 2
    return 1


def stars_string(stars: int, *, filled: str = "★", empty: str = "☆") -> str:
    """Render a star rating as filled/empty marks, e.g. ``★★★★☆``.

    ``filled``/``empty`` are overridable so callers on terminals that cannot
    encode the Unicode stars can pass ASCII fallbacks (e.g. ``*`` and ``.``).
    """
    stars = max(0, min(MAX_STARS, stars))
    return filled * stars + empty * (MAX_STARS - stars)


def rank(skills: Sequence[Skill], keywords: Sequence[str]) -> list[Recommendation]:
    """Rank ``skills`` for a phase described by ``keywords``. Pure and deterministic.

    Only skills with a positive score are returned. Results are ordered by score
    (descending), then by ``skill_id`` (ascending) so ties are broken stably and
    the same inputs always yield byte-identical output. This function knows
    nothing about config, state, or the filesystem -- it is the swappable core.
    """
    recommendations: list[Recommendation] = []
    for skill in skills:
        score, matched = _score_skill(skill, keywords)
        if score > 0:
            recommendations.append(
                Recommendation(skill=skill, score=score, stars=_stars(score), matched=matched)
            )
    recommendations.sort(key=lambda r: (-r.score, r.skill.skill_id))
    return recommendations


def load_rules(base: Path) -> dict[Phase, list[str]]:
    """Return phase rules: built-in defaults overridden by config when present.

    A ``recommend_<phase-value>`` config list (e.g. ``recommend_planning``)
    replaces that phase's default terms. Unknown keys are ignored.
    """
    rules: dict[Phase, list[str]] = {phase: list(terms) for phase, terms in DEFAULT_RULES.items()}
    mapping = load_mapping(base)
    for phase in Phase:
        key = f"{RULE_KEY_PREFIX}{phase.value}"
        if key not in mapping:
            continue
        value = mapping[key]
        if isinstance(value, list):
            terms = [str(item).strip().lower() for item in value if str(item).strip()]
        elif isinstance(value, str) and value.strip():
            terms = [value.strip().lower()]
        else:
            terms = []
        if terms:
            rules[phase] = terms
    return rules


def keywords_for_phase(base: Path, phase: Phase) -> list[str]:
    """Return the keyword rules that apply to ``phase`` for the project at ``base``."""
    return load_rules(base).get(phase, [])
