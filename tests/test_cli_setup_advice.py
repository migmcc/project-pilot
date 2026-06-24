import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main
from projectpilot.state import state_path

FROZEN = "2026-06-24T11:00:00Z"


def clock() -> str:
    return FROZEN


def _read(d: str) -> dict:
    return json.loads(state_path(Path(d)).read_text(encoding="utf-8"))


def _reach_brief_without_import(d: str) -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        main(["init", "an idea", "--dir", d, "--name", "Demo"], clock=clock)
        main(["validate", "--dir", d], clock=clock)
        main(["decision", "set", "APPROVED", "--reason", "ok", "--dir", d], clock=clock)
        main(["advance", "brief", "--dir", d], clock=clock)


def _reach_setup_advice(d: str) -> None:
    _reach_brief_without_import(d)
    source = Path(d) / "skilllab-brief.md"
    source.write_text("# Approved brief\n", encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        main(["brief", "import", str(source), "--dir", d], clock=clock)


class SetupAdviceTests(unittest.TestCase):
    def test_advise_setup_without_state_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["advise-setup", "--dir", d], clock=clock)
            self.assertEqual(rc, 1)

    def test_advise_setup_outside_setup_advice_phase_fails(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_brief_without_import(d)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["advise-setup", "--dir", d], clock=clock)
            self.assertEqual(rc, 1)
            self.assertIsNone(_read(d)["setup_advice"])

    def test_advise_setup_requires_imported_brief(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_brief_without_import(d)
            state = _read(d)
            state["current_phase"] = "setup-advice"
            state_path(Path(d)).write_text(json.dumps(state), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["advise-setup", "--dir", d], clock=clock)
            self.assertEqual(rc, 1)
            self.assertIsNone(_read(d)["setup_advice"])

    def test_advise_setup_outputs_deterministic_manual_recommendations(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_setup_advice(d)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["advise-setup", "--dir", d], clock=clock)
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("Install A-team in the project repo", text)
            self.assertIn("Install only minimal builders", text)
            self.assertIn("Fill INIT.md", text)
            self.assertIn("Run /orchestrate init", text)
            self.assertIn(".agent-sync/TEAM.md", text)
            self.assertIn(".agent-sync/ROUTING.md", text)
            self.assertIn("AgentDesk is optional support", text)

    def test_advise_setup_records_metadata_and_advances_to_planning(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_setup_advice(d)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["advise-setup", "--dir", d], clock=clock)
            self.assertEqual(rc, 0)
            state = _read(d)
            advice = state["setup_advice"]
            self.assertEqual(state["current_phase"], "planning")
            self.assertEqual(advice["prepared_at"], FROZEN)
            self.assertEqual(advice["source"], "deterministic")
            self.assertIn("A-team", advice["recommended_builders"][0])
            self.assertIn("Fill INIT.md", advice["readiness_checks"])

    def test_advise_setup_appends_history(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_setup_advice(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["advise-setup", "--dir", d], clock=clock)
            events = [h["event"] for h in _read(d)["history"]]
            self.assertIn("setup_advice_prepared", events)

    def test_advise_setup_preserves_decision_and_brief_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_setup_advice(d)
            before = _read(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["advise-setup", "--dir", d], clock=clock)
            after = _read(d)
            self.assertEqual(after["decision"], before["decision"])
            self.assertEqual(after["brief"], before["brief"])

    def test_status_shows_advice_prepared_and_planning_action(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_setup_advice(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["advise-setup", "--dir", d], clock=clock)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main(["status", "--dir", d])
            text = out.getvalue()
            self.assertIn("Current phase: planning", text)
            self.assertIn("Setup advice: prepared", text)
            self.assertIn("plan", text.lower())


if __name__ == "__main__":
    unittest.main()
