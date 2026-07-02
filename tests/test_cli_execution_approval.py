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


def _make_ateam_ready(d: str) -> None:
    base = Path(d)
    (base / "INIT.md").write_text("init\n", encoding="utf-8")
    (base / ".agent-sync").mkdir()
    (base / ".agent-sync" / "TEAM.md").write_text("team\n", encoding="utf-8")
    (base / ".agent-sync" / "ROUTING.md").write_text("routing\n", encoding="utf-8")


def _check_ateam(d: str) -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        main(["check-ateam", "--dir", d], clock=clock)


class ExecutionApprovalTests(unittest.TestCase):
    def test_execution_approve_without_state_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    ["execution", "approve", "--reason", "ready", "--dir", d],
                    clock=clock,
                )
            self.assertEqual(rc, 1)

    def test_execution_approve_outside_planning_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["init", "idea", "--dir", d], clock=clock)
                rc = main(
                    ["execution", "approve", "--reason", "ready", "--dir", d],
                    clock=clock,
                )
            self.assertEqual(rc, 1)
            self.assertIsNone(_read(d)["execution_approval"])

    def test_execution_approve_requires_ateam_check(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    ["execution", "approve", "--reason", "ready", "--dir", d],
                    clock=clock,
                )
            self.assertEqual(rc, 1)
            self.assertIsNone(_read(d)["execution_approval"])

    def test_execution_approve_blocks_not_ready_without_override(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            _check_ateam(d)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    ["execution", "approve", "--reason", "manual review", "--dir", d],
                    clock=clock,
                )
            self.assertEqual(rc, 1)
            self.assertEqual(_read(d)["current_phase"], "planning")

    def test_execution_approve_passes_when_ateam_ready(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            _make_ateam_ready(d)
            _check_ateam(d)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    ["execution", "approve", "--reason", "all files present", "--dir", d],
                    clock=clock,
                )
            self.assertEqual(rc, 0)
            state = _read(d)
            self.assertEqual(state["current_phase"], "execution")
            self.assertFalse(state["execution_approval"]["override"])
            self.assertTrue(state["execution_approval"]["ateam_ready_at_approval"])

    def test_execution_approve_passes_with_override_when_not_ready(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            _check_ateam(d)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "execution",
                        "approve",
                        "--reason",
                        "temporary manual override",
                        "--override",
                        "--dir",
                        d,
                    ],
                    clock=clock,
                )
            self.assertEqual(rc, 0)
            approval = _read(d)["execution_approval"]
            self.assertTrue(approval["override"])
            self.assertEqual(approval["reason"], "temporary manual override")
            self.assertFalse(approval["ateam_ready_at_approval"])

    def test_execution_approve_requires_reason(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            _make_ateam_ready(d)
            _check_ateam(d)
            with self.assertRaises(SystemExit) as cm:
                with contextlib.redirect_stderr(io.StringIO()):
                    main(["execution", "approve", "--dir", d], clock=clock)
            self.assertEqual(cm.exception.code, 2)

    def test_execution_approve_preserves_existing_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            _make_ateam_ready(d)
            _check_ateam(d)
            before = _read(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(
                    ["execution", "approve", "--reason", "all files present", "--dir", d],
                    clock=clock,
                )
            after = _read(d)
            self.assertEqual(after["decision"], before["decision"])
            self.assertEqual(after["brief"], before["brief"])
            self.assertEqual(after["setup_advice"], before["setup_advice"])
            self.assertEqual(after["ateam_check"], before["ateam_check"])

    def test_execution_approve_records_metadata_and_history(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            _make_ateam_ready(d)
            _check_ateam(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(
                    ["execution", "approve", "--reason", "all files present", "--dir", d],
                    clock=clock,
                )
            state = _read(d)
            approval = state["execution_approval"]
            self.assertEqual(approval["approved_at"], FROZEN)
            self.assertEqual(approval["reason"], "all files present")
            self.assertEqual(approval["source"], "manual")
            self.assertIn("execution_approved", [h["event"] for h in state["history"]])

    def test_status_shows_execution_approval(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            _make_ateam_ready(d)
            _check_ateam(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(
                    ["execution", "approve", "--reason", "all files present", "--dir", d],
                    clock=clock,
                )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main(["status", "--dir", d])
            text = out.getvalue()
            self.assertIn("Current phase: execution", text)
            self.assertIn("Execution approval: approved", text)
            self.assertIn("all files present", text)

    def test_execution_approve_warns_when_requirements_incomplete(self):
        # Advisory only: the approval is still recorded and the phase advances.
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            _make_ateam_ready(d)
            _check_ateam(d)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(
                    ["execution", "approve", "--reason", "go", "--dir", d],
                    clock=clock,
                )
            self.assertEqual(rc, 0)
            self.assertIn("Warning: planning requirements are incomplete", out.getvalue())
            self.assertEqual(_read(d)["current_phase"], "execution")

    def test_execution_approve_no_warning_when_requirements_complete(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            _make_ateam_ready(d)
            _check_ateam(d)
            for rel in ("docs/PRD.md", "docs/roadmap.md"):
                path = Path(d) / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("content", encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()):
                    main(["artifact", "add", str(path), "--dir", d], clock=clock)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(
                    ["execution", "approve", "--reason", "go", "--dir", d],
                    clock=clock,
                )
            self.assertEqual(rc, 0)
            self.assertNotIn("Warning:", out.getvalue())


if __name__ == "__main__":
    unittest.main()
