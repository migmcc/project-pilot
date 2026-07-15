"""Project Dashboard: one aggregated, read-only overview of a project.

The dashboard is a thin **aggregator**. It introduces no workflow logic and
duplicates nothing -- it only gathers what other layers already expose through
their public interfaces and assembles a single, deterministic snapshot:

* :func:`projectpilot.state.load_state` -- project name and current phase;
* :func:`projectpilot.phase_requirements.evaluate` -- completion / readiness;
* :func:`projectpilot.advisor.advise` -- the top workflow recommendation;
* :func:`projectpilot.artifact_store.list_artifacts` -- registered evidence
  (metadata only; contents are never read);
* :func:`projectpilot.skills.scan_skills` + :func:`projectpilot.recommend.rank`
  -- the phase's recommended skills.

It calls no LLM, spawns no process, touches no network, and adds no
dependency. Given the same project state it produces byte-identical output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import advisor, artifact_store, graph_context, phase_requirements, recommend, skills
from .errors import StateNotFoundError
from .phases import Phase
from .state import load_state

__all__ = [
    "Dashboard",
    "collect",
]

#: How many recommended skills to surface.
_MAX_SKILLS = 5

#: Artifact metadata fields exposed in verbose output (never file contents).
_ARTIFACT_META_KEYS = ("id", "path", "type", "phase", "status")


@dataclass
class Dashboard:
    """A deterministic, aggregated snapshot of a project. Data only, no rendering."""

    initialized: bool
    project_name: str | None = None
    phase: Phase | None = None
    completion: int | None = None
    ready_to_progress: bool | None = None
    completed: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    top_recommendation: advisor.Recommendation | None = None
    artifacts: list[dict] = field(default_factory=list)
    recommended_skills: list[str] = field(default_factory=list)
    graph_context_status: graph_context.GraphContextStatus | None = None

    def to_dict(self, *, verbose: bool = False) -> dict:
        """Assemble the deterministic JSON payload with stable key ordering."""
        phase_block: dict = {
            "completion": self.completion,
            "ready_to_progress": self.ready_to_progress,
        }
        if verbose:
            phase_block["completed"] = list(self.completed)
            phase_block["missing"] = list(self.missing)

        workflow_block: dict = {}
        if self.top_recommendation is not None:
            rec = self.top_recommendation
            workflow_block = {
                "priority": rec.priority,
                "action": rec.action,
                "reason": rec.reason,
                "command": rec.command,
            }

        artifacts_block: dict = {
            "total": len(self.artifacts),
            "items": [record["path"] for record in self.artifacts],
        }
        if verbose:
            artifacts_block["metadata"] = [
                {key: record[key] for key in _ARTIFACT_META_KEYS} for record in self.artifacts
            ]

        payload = {
            "project": {
                "name": self.project_name,
                "phase": self.phase.value if self.phase else None,
            },
            "phase": phase_block,
            "workflow": workflow_block,
            "artifacts": artifacts_block,
            "skills": {"recommended": list(self.recommended_skills)},
        }
        status = self.graph_context_status
        if status is not None and status.enabled:
            payload["context"] = {
                "provider": "graphify",
                "status": status.state,
                "query_budget": status.query_budget,
                "graph": status.graph_path,
                "report": status.report_path,
            }
        return payload


def _recommended_skills(base: Path, phase: Phase) -> list[str]:
    found = skills.scan_skills(base)
    if not found:
        return []
    ranked = recommend.rank(found, recommend.keywords_for_phase(base, phase))
    return [item.skill.skill_id for item in ranked[:_MAX_SKILLS]]


def collect(base: Path) -> Dashboard:
    """Gather a :class:`Dashboard` for the project at ``base`` (read-only).

    Works whether or not the project is initialized: an uninitialized directory
    yields the advisor's "initialize" nudge and optional Graphify context status.
    """
    base = Path(base)
    context_status = graph_context.inspect_graph_context(base)
    advice = advisor.advise(base)
    records = artifact_store.list_artifacts(base)
    top = advice.recommendations[0] if advice.recommendations else None

    try:
        state = load_state(base)
    except StateNotFoundError:
        return Dashboard(
            initialized=False,
            top_recommendation=top,
            artifacts=records,
            graph_context_status=context_status,
        )

    phase = state.current_phase
    evaluation = phase_requirements.evaluate(phase, records)
    return Dashboard(
        initialized=True,
        project_name=state.name or None,
        phase=phase,
        completion=evaluation.completion,
        ready_to_progress=evaluation.ready_to_progress,
        completed=[status.key for status in evaluation.completed],
        missing=[status.key for status in evaluation.missing],
        top_recommendation=top,
        artifacts=records,
        recommended_skills=_recommended_skills(base, phase),
        graph_context_status=context_status,
    )
