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


def _reach_planning(d: str) -> None:
    source = Path(d) / "skilllab-brief.md"
    source.write_text("# Approved brief\n", encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        main(["init", "an idea", "--dir", d, "--name", "Demo"], clock=clock)
        main(["validate", "--dir", d], clock=clock)
        main(["decision", "set", "APPROVED", "--reason", "ok", "--dir", d], clock=clock)
        main(["advance", "brief", "--dir", d], clock=clock)
        main(["brief", "import", str(source), "--dir", d], clock=clock)
        main(["advise-setup", "--dir", d], clock=clock)


class CheckATeamTests(unittest.TestCase):
    def test_check_ateam_without_state_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["check-ateam", "--dir", d], clock=clock)
            self.assertEqual(rc, 1)

    def test_check_ateam_before_planning_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["init", "idea", "--dir", d], clock=clock)
                rc = main(["check-ateam", "--dir", d], clock=clock)
            self.assertEqual(rc, 1)
            self.assertIsNone(_read(d)["ateam_check"])

    def test_check_ateam_reports_missing_and_present_paths(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            (Path(d) / "INIT.md").write_text("init\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["check-ateam", "--dir", d], clock=clock)
            self.assertEqual(rc, 0)
            text = out.getvalue()
            self.assertIn("Present paths:", text)
            self.assertIn("INIT.md", text)
            self.assertIn("Missing paths:", text)
            self.assertIn(".agent-sync/TEAM.md", text)
            check = _read(d)["ateam_check"]
            self.assertEqual(check["present_paths"], ["INIT.md"])
            self.assertEqual(
                check["missing_paths"],
                [".agent-sync", ".agent-sync/TEAM.md", ".agent-sync/ROUTING.md"],
            )

    def test_check_ateam_ready_false_when_paths_are_missing(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["check-ateam", "--dir", d], clock=clock)
            self.assertFalse(_read(d)["ateam_check"]["ready"])

    def test_check_ateam_ready_true_when_all_paths_exist(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            base = Path(d)
            (base / "INIT.md").write_text("init\n", encoding="utf-8")
            (base / ".agent-sync").mkdir()
            (base / ".agent-sync" / "TEAM.md").write_text("team\n", encoding="utf-8")
            (base / ".agent-sync" / "ROUTING.md").write_text("routing\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["check-ateam", "--dir", d], clock=clock)
            check = _read(d)["ateam_check"]
            self.assertTrue(check["ready"])
            self.assertEqual(check["missing_paths"], [])
            self.assertEqual(
                check["present_paths"],
                ["INIT.md", ".agent-sync", ".agent-sync/TEAM.md", ".agent-sync/ROUTING.md"],
            )

    def test_check_ateam_does_not_install_or_advance(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["check-ateam", "--dir", d], clock=clock)
            base = Path(d)
            self.assertFalse((base / "INIT.md").exists())
            self.assertFalse((base / ".agent-sync").exists())
            self.assertEqual(_read(d)["current_phase"], "planning")

    def test_check_ateam_preserves_existing_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            before = _read(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["check-ateam", "--dir", d], clock=clock)
            after = _read(d)
            self.assertEqual(after["decision"], before["decision"])
            self.assertEqual(after["brief"], before["brief"])
            self.assertEqual(after["setup_advice"], before["setup_advice"])

    def test_check_ateam_records_metadata_and_history(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["check-ateam", "--dir", d], clock=clock)
            state = _read(d)
            check = state["ateam_check"]
            self.assertEqual(check["checked_at"], FROZEN)
            self.assertEqual(
                check["required_paths"],
                ["INIT.md", ".agent-sync", ".agent-sync/TEAM.md", ".agent-sync/ROUTING.md"],
            )
            self.assertEqual(check["source"], "read-only-filesystem")
            self.assertIn("ateam_checked", [h["event"] for h in state["history"]])

    def test_status_shows_ateam_check_result(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["check-ateam", "--dir", d], clock=clock)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main(["status", "--dir", d])
            text = out.getvalue()
            self.assertIn("A-team check: not ready", text)
            self.assertIn("INIT.md", text)


if __name__ == "__main__":
    unittest.main()
