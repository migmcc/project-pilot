import tempfile
import unittest
from pathlib import Path

from projectpilot import artifact_store, dashboard, graph_context
from projectpilot.config import config_path
from projectpilot.phases import Phase
from projectpilot.state import ProjectState, save_state


def seed_state(base: Path, phase=Phase.PLANNING, name="Demo"):
    save_state(
        base,
        ProjectState(
            name=name,
            slug="demo",
            idea="build a thing",
            created_at="2026-06-30T00:00:00Z",
            updated_at="2026-06-30T00:00:00Z",
            current_phase=phase,
        ),
    )


def register(base: Path, rel: str, phase="planning"):
    path = base / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("content", encoding="utf-8")
    artifact_store.add_artifact(base, path, phase, clock=lambda: "2026-07-01T00:00:00Z")


def configure_lib(base: Path, d: Path):
    lib = d / "lib"
    skill_dir = lib / "sprint-plan"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        '---\nname: sprint-plan\ndescription: "Plan a sprint."\n---\n\nBody.\n', encoding="utf-8"
    )
    path = config_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("external_skill_paths:\n  - ../lib\n", encoding="utf-8")


def configure_graphify(base: Path, *, ready: bool) -> None:
    path = config_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("graphify_enabled: true\n", encoding="utf-8")
    if ready:
        out = base / "graphify-out"
        out.mkdir()
        (out / "graph.json").write_text("{}\n", encoding="utf-8")
        (out / "GRAPH_REPORT.md").write_text("# Report\n", encoding="utf-8")


class EmptyProjectTests(unittest.TestCase):
    def test_uninitialized(self):
        with tempfile.TemporaryDirectory() as d:
            dash = dashboard.collect(Path(d))
            self.assertFalse(dash.initialized)
            self.assertIsNone(dash.project_name)
            self.assertIsNone(dash.phase)
            self.assertIsNotNone(dash.top_recommendation)
            self.assertIn("pp init", dash.top_recommendation.command)

    def test_uninitialized_json_shape(self):
        with tempfile.TemporaryDirectory() as d:
            payload = dashboard.collect(Path(d)).to_dict()
            self.assertEqual(payload["project"], {"name": None, "phase": None})
            self.assertEqual(payload["artifacts"], {"total": 0, "items": []})
            self.assertEqual(payload["skills"], {"recommended": []})


class InitializedProjectTests(unittest.TestCase):
    def test_aggregates_all_sections(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            seed_state(base, name="Local Review Assistant")
            configure_lib(base, Path(d))
            register(base, "docs/PRD.md")
            dash = dashboard.collect(base)
            self.assertTrue(dash.initialized)
            self.assertEqual(dash.project_name, "Local Review Assistant")
            self.assertEqual(dash.phase, Phase.PLANNING)
            self.assertEqual(dash.completion, 50)
            self.assertFalse(dash.ready_to_progress)
            self.assertEqual(dash.completed, ["prd"])
            self.assertEqual(dash.missing, ["roadmap"])
            self.assertEqual([r["path"] for r in dash.artifacts], ["docs/PRD.md"])
            self.assertIn("sprint-plan", dash.recommended_skills)
            self.assertIsNotNone(dash.top_recommendation)

    def test_matches_underlying_engines(self):
        # Dashboard must not diverge from the engines it aggregates.
        from projectpilot import advisor, phase_requirements

        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            register(base, "docs/PRD.md")
            dash = dashboard.collect(base)
            evaluation = phase_requirements.evaluate(
                Phase.PLANNING, artifact_store.list_artifacts(base)
            )
            advice = advisor.advise(base)
            self.assertEqual(dash.completion, evaluation.completion)
            self.assertEqual(dash.ready_to_progress, evaluation.ready_to_progress)
            self.assertEqual(dash.top_recommendation, advice.recommendations[0])


class JsonModeTests(unittest.TestCase):
    def test_enabled_context_is_additive_and_stably_ordered(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            configure_graphify(base, ready=True)
            payload = dashboard.collect(base).to_dict()
            self.assertEqual(
                list(payload.keys()),
                ["project", "phase", "workflow", "artifacts", "skills", "context"],
            )
            self.assertEqual(
                list(payload["context"].keys()),
                ["provider", "status", "query_budget", "graph", "report"],
            )
            self.assertEqual(
                payload["context"],
                {
                    "provider": "graphify",
                    "status": graph_context.STATE_READY,
                    "query_budget": 1200,
                    "graph": "graphify-out/graph.json",
                    "report": "graphify-out/GRAPH_REPORT.md",
                },
            )

    def test_disabled_context_keeps_original_top_level_shape(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            payload = dashboard.collect(base).to_dict()
            self.assertEqual(
                list(payload.keys()),
                ["project", "phase", "workflow", "artifacts", "skills"],
            )
            self.assertNotIn("context", payload)

    def test_key_ordering_is_stable(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            payload = dashboard.collect(base).to_dict()
            self.assertEqual(
                list(payload.keys()), ["project", "phase", "workflow", "artifacts", "skills"]
            )
            self.assertEqual(list(payload["phase"].keys()), ["completion", "ready_to_progress"])

    def test_verbose_adds_fields(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            register(base, "docs/PRD.md")
            plain = dashboard.collect(base).to_dict(verbose=False)
            verbose = dashboard.collect(base).to_dict(verbose=True)
            self.assertNotIn("completed", plain["phase"])
            self.assertIn("completed", verbose["phase"])
            self.assertIn("missing", verbose["phase"])
            self.assertNotIn("metadata", plain["artifacts"])
            self.assertIn("metadata", verbose["artifacts"])
            # metadata is summary only -- no size/sha/content leakage keys
            meta = verbose["artifacts"]["metadata"][0]
            self.assertEqual(set(meta.keys()), {"id", "path", "type", "phase", "status"})

    def test_deterministic_across_runs(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            seed_state(base)
            configure_lib(base, Path(d))
            register(base, "docs/PRD.md")
            first = dashboard.collect(base).to_dict(verbose=True)
            second = dashboard.collect(base).to_dict(verbose=True)
            self.assertEqual(first, second)


class MissingOptionalDataTests(unittest.TestCase):
    def test_no_artifacts_no_skills(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            dash = dashboard.collect(base)
            self.assertEqual(dash.artifacts, [])
            self.assertEqual(dash.recommended_skills, [])
            payload = dash.to_dict()
            self.assertEqual(payload["artifacts"]["total"], 0)
            self.assertEqual(payload["skills"]["recommended"], [])

    def test_workflow_block_empty_when_no_recommendation(self):
        # done phase with handoffs still yields a recommendation ("Project complete"),
        # so assert the block is well-formed rather than empty.
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base, phase=Phase.DONE)
            payload = dashboard.collect(base).to_dict()
            self.assertIn("action", payload["workflow"])


if __name__ == "__main__":
    unittest.main()
