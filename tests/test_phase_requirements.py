import unittest

from projectpilot import phase_requirements as pr
from projectpilot.phases import Phase


def artifact(path, phase="planning"):
    name = path.rsplit("/", 1)[-1]
    ext = name.rsplit(".", 1)[-1] if "." in name else "unknown"
    slug = path.lower().replace("/", "-").replace(".", "-")
    return {
        "id": slug,
        "path": path,
        "name": name,
        "type": ext,
        "phase": phase,
        "registered_at": "t",
        "size": 1,
        "sha256": "x",
        "origin": "manual",
        "status": "registered",
    }


class EveryPhaseTests(unittest.TestCase):
    def test_all_phases_evaluate_without_error(self):
        for phase in Phase:
            evaluation = pr.evaluate(phase, [])
            self.assertEqual(evaluation.phase, phase)
            self.assertTrue(0 <= evaluation.completion <= 100)
            self.assertIsInstance(evaluation.ready_to_progress, bool)

    def test_phases_without_required_are_complete_when_empty(self):
        for phase in (Phase.IDEA, Phase.VALIDATION, Phase.SETUP_ADVICE, Phase.DONE):
            evaluation = pr.evaluate(phase, [])
            self.assertEqual(evaluation.completion, 100)
            self.assertTrue(evaluation.ready_to_progress)


class CompletionTests(unittest.TestCase):
    def test_no_artifacts_zero_for_required_phase(self):
        evaluation = pr.evaluate(Phase.PLANNING, [])
        self.assertEqual(evaluation.completion, 0)
        self.assertFalse(evaluation.ready_to_progress)
        self.assertEqual({s.label for s in evaluation.missing}, {"PRD", "Roadmap"})

    def test_partial_completion(self):
        evaluation = pr.evaluate(Phase.PLANNING, [artifact("docs/PRD.md")])
        self.assertEqual(evaluation.completion, 50)
        self.assertFalse(evaluation.ready_to_progress)
        self.assertEqual([s.key for s in evaluation.completed], ["prd"])
        self.assertEqual([s.key for s in evaluation.missing], ["roadmap"])

    def test_full_completion(self):
        artifacts = [artifact("docs/PRD.md"), artifact("docs/roadmap.md")]
        evaluation = pr.evaluate(Phase.PLANNING, artifacts)
        self.assertEqual(evaluation.completion, 100)
        self.assertTrue(evaluation.ready_to_progress)
        self.assertEqual(evaluation.missing, [])

    def test_optional_does_not_affect_completion(self):
        # Only the optional risk-analysis present -> required still 0%.
        evaluation = pr.evaluate(Phase.PLANNING, [artifact("docs/risk-analysis.md")])
        self.assertEqual(evaluation.completion, 0)
        risk = next(s for s in evaluation.optional_statuses if s.key == "risk-analysis")
        self.assertTrue(risk.satisfied)

    def test_execution_requires_implementation_plan(self):
        empty = pr.evaluate(Phase.EXECUTION, [])
        self.assertFalse(empty.ready_to_progress)
        done = pr.evaluate(Phase.EXECUTION, [artifact("implementation-plan.md")])
        self.assertTrue(done.ready_to_progress)
        self.assertEqual(done.completion, 100)


class MatchingTests(unittest.TestCase):
    def test_matches_by_name_variants(self):
        for path in ("PRD.md", "docs/product-requirements.md", "product_requirements_document.md"):
            evaluation = pr.evaluate(Phase.PLANNING, [artifact(path)])
            self.assertIn("prd", [s.key for s in evaluation.completed], path)

    def test_records_satisfying_artifact_id(self):
        art = artifact("docs/PRD.md")
        evaluation = pr.evaluate(Phase.PLANNING, [art])
        prd = next(s for s in evaluation.required_statuses if s.key == "prd")
        self.assertEqual(prd.artifact_id, art["id"])

    def test_unrelated_artifact_does_not_match(self):
        evaluation = pr.evaluate(Phase.PLANNING, [artifact("notes/todo.txt")])
        self.assertEqual(evaluation.completion, 0)


class JsonAndStabilityTests(unittest.TestCase):
    def test_to_dict_shape_and_order(self):
        evaluation = pr.evaluate(Phase.PLANNING, [artifact("docs/PRD.md")])
        payload = evaluation.to_dict()
        self.assertEqual(
            list(payload.keys()),
            ["phase", "completion", "ready_to_progress", "completed", "missing"],
        )
        self.assertEqual(payload["phase"], "planning")
        self.assertEqual(payload["completion"], 50)
        self.assertEqual(payload["completed"], ["prd"])
        self.assertEqual(payload["missing"], ["roadmap"])

    def test_deterministic(self):
        artifacts = [artifact("docs/PRD.md"), artifact("docs/roadmap.md")]
        first = pr.evaluate(Phase.PLANNING, artifacts).to_dict()
        second = pr.evaluate(Phase.PLANNING, artifacts).to_dict()
        self.assertEqual(first, second)

    def test_requirements_for_returns_defined(self):
        self.assertEqual(
            [r.key for r in pr.requirements_for(Phase.PLANNING).required], ["prd", "roadmap"]
        )
        self.assertEqual(pr.requirements_for(Phase.SETUP_ADVICE).required, ())


if __name__ == "__main__":
    unittest.main()
