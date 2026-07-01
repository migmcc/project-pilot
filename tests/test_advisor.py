import tempfile
import unittest
from pathlib import Path

from projectpilot import advisor
from projectpilot import artifact_store
from projectpilot.config import config_path
from projectpilot.phases import Phase
from projectpilot.state import ProjectState, save_state


def make_state(base: Path, **overrides) -> ProjectState:
    data = dict(
        name="Demo",
        slug="demo",
        idea="build a thing",
        created_at="2026-06-30T00:00:00Z",
        updated_at="2026-06-30T00:00:00Z",
        current_phase=Phase.PLANNING,
    )
    data.update(overrides)
    state = ProjectState(**data)
    save_state(base, state)
    return state


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


def priorities(advice):
    return [r.priority for r in advice.recommendations]


def actions(advice):
    return [r.action for r in advice.recommendations]


class EmptyProjectTests(unittest.TestCase):
    def test_no_state_recommends_init(self):
        with tempfile.TemporaryDirectory() as d:
            advice = advisor.advise(Path(d))
            self.assertIsNone(advice.phase)
            self.assertEqual(len(advice.recommendations), 1)
            rec = advice.recommendations[0]
            self.assertEqual(rec.priority, advisor.PRIORITY_HIGH)
            self.assertIn("pp init", rec.command)


class PhaseGateTests(unittest.TestCase):
    def _gate_command(self, phase, **state_over):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            make_state(base, current_phase=phase, **state_over)
            advice = advisor.advise(base)
            gate = next(
                (r for r in advice.recommendations if r.depends_on and "phase" in r.depends_on
                 and r.action not in ("Provide the Project Brief",)),
                None,
            )
            return advice, gate

    def test_every_phase_produces_recommendations(self):
        for phase in Phase:
            with tempfile.TemporaryDirectory() as d:
                base = Path(d)
                make_state(base, current_phase=phase, history=[{"event": "x", "phase": "idea", "timestamp": "t"}])
                advice = advisor.advise(base)
                self.assertEqual(advice.phase, phase)
                self.assertTrue(advice.recommendations, f"no recs for {phase}")

    def test_idea_gate(self):
        advice, gate = self._gate_command(Phase.IDEA)
        self.assertEqual(gate.command, "pp validate")

    def test_validation_pending_decision(self):
        advice, gate = self._gate_command(Phase.VALIDATION)
        self.assertIn("approve decision", gate.command)

    def test_validation_approved_advances(self):
        advice, gate = self._gate_command(
            Phase.VALIDATION, decision={"decision": "APPROVED", "reason": "ok"}
        )
        self.assertEqual(gate.command, "pp advance brief")

    def test_validation_rework_requires_new_decision(self):
        advice, gate = self._gate_command(
            Phase.VALIDATION, decision={"decision": "NEEDS_REWORK", "reason": "redo"}
        )
        self.assertIn("NEEDS_REWORK", gate.reason)

    def test_final_validation_gate(self):
        advice, gate = self._gate_command(Phase.FINAL_VALIDATION)
        self.assertIn("approve done", gate.command)

    def test_done_reports_complete(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            make_state(base, current_phase=Phase.DONE, history=[{"event": "x", "phase": "done", "timestamp": "t"}])
            advice = advisor.advise(base)
            self.assertIsNone(advice.followup)
            self.assertIn("Project complete", actions(advice))


class ArtifactRuleTests(unittest.TestCase):
    def test_missing_brief_flagged_past_brief_phase(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            make_state(base, current_phase=Phase.PLANNING)
            advice = advisor.advise(base)
            self.assertIn("Provide the Project Brief", actions(advice))

    def test_present_brief_not_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            make_state(base, current_phase=Phase.PLANNING)
            (base / "PROJECT_BRIEF.md").write_text("brief", encoding="utf-8")
            advice = advisor.advise(base)
            self.assertNotIn("Provide the Project Brief", actions(advice))

    def test_registered_prd_artifact_suppresses_create_prd_skill_recommendation(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            make_state(base, current_phase=Phase.PLANNING)
            lib = Path(d) / "lib"
            skill_dir = lib / "create-prd"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                '---\nname: create-prd\ndescription: "Create a PRD."\n---\n\nBody.\n',
                encoding="utf-8",
            )
            path = config_path(base)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("external_skill_paths:\n  - ../lib\n", encoding="utf-8")
            evidence = base / "docs" / "PRD.md"
            evidence.parent.mkdir()
            evidence.write_text("external prd", encoding="utf-8")
            artifact_store.add_artifact(
                base,
                evidence,
                "planning",
                clock=lambda: "2026-07-01T12:00:00Z",
            )

            advice = advisor.advise(base)

            self.assertNotIn("Prepare the recommended skill 'create-prd'", actions(advice))

    def test_no_handoffs_nudges_progress(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            make_state(base, current_phase=Phase.IDEA, history=[])
            advice = advisor.advise(base)
            self.assertIn("Record initial progress", actions(advice))

    def test_handoffs_present_no_nudge(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            make_state(base, current_phase=Phase.IDEA, history=[{"event": "x", "phase": "idea", "timestamp": "t"}])
            advice = advisor.advise(base)
            self.assertNotIn("Record initial progress", actions(advice))


class SkillRuleTests(unittest.TestCase):
    def test_recommended_skill_is_high_and_first(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            make_state(base, current_phase=Phase.PLANNING)
            configure_lib(base, Path(d))
            advice = advisor.advise(base)
            self.assertEqual(advice.recommendations[0].priority, advisor.PRIORITY_HIGH)
            self.assertIn("pp skill use sprint-plan", advice.recommendations[0].command)
            # the gate is demoted to Medium while a skill is pending
            gate = next(r for r in advice.recommendations if "execution" in (r.command or ""))
            self.assertEqual(gate.priority, advisor.PRIORITY_MEDIUM)

    def test_prepared_skill_promotes_gate_to_high(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            make_state(base, current_phase=Phase.PLANNING)
            configure_lib(base, Path(d))
            prompts = base / "projectpilot_outputs" / "prompts"
            prompts.mkdir(parents=True)
            (prompts / "sprint-plan.md").write_text("prepared", encoding="utf-8")
            advice = advisor.advise(base)
            self.assertNotIn(
                "Prepare the recommended skill 'sprint-plan'", actions(advice)
            )
            gate = next(r for r in advice.recommendations if "execution" in (r.command or ""))
            self.assertEqual(gate.priority, advisor.PRIORITY_HIGH)


class OrderingAndStabilityTests(unittest.TestCase):
    def test_recommendations_sorted_by_priority(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            make_state(base, current_phase=Phase.PLANNING, history=[])
            configure_lib(base, Path(d))
            advice = advisor.advise(base)
            ranks = [advisor._PRIORITY_RANK[p] for p in priorities(advice)]
            self.assertEqual(ranks, sorted(ranks))
            self.assertGreater(len(advice.recommendations), 1)

    def test_stable_across_runs(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            make_state(base, current_phase=Phase.PLANNING)
            configure_lib(base, Path(d))
            first = advisor.advise(base).to_dict()
            second = advisor.advise(base).to_dict()
            self.assertEqual(first, second)

    def test_to_dict_shape_is_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            make_state(base, current_phase=Phase.PLANNING)
            payload = advisor.advise(base).to_dict()
            self.assertEqual(list(payload.keys()), ["phase", "followup", "recommendations"])
            rec = payload["recommendations"][0]
            self.assertEqual(
                list(rec.keys()), ["priority", "action", "reason", "command", "depends_on"]
            )


if __name__ == "__main__":
    unittest.main()
