import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main
from projectpilot.phases import Phase
from projectpilot.state import ProjectState, save_state, state_path

FROZEN = "2026-06-24T16:00:00Z"


def clock() -> str:
    return FROZEN


def _read(d: str) -> dict:
    return json.loads(state_path(Path(d)).read_text(encoding="utf-8"))


def _state_at(d: str, phase: Phase, **fields) -> None:
    save_state(
        Path(d),
        ProjectState(
            name="Demo",
            slug="demo",
            idea="an idea",
            created_at=FROZEN,
            updated_at=FROZEN,
            current_phase=phase,
            history=[],
            **fields,
        ),
    )


class ApproveAliasTests(unittest.TestCase):
    def test_approve_decision_records_without_advancing(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.VALIDATION)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["approve", "decision", "APPROVED", "--reason", "ok", "--dir", d], clock=clock)
            self.assertEqual(rc, 0)
            data = _read(d)
            self.assertEqual(data["decision"]["decision"], "APPROVED")
            self.assertEqual(data["decision"]["source"], "manual")
            self.assertEqual(data["current_phase"], "validation")  # not advanced

    def test_approve_decision_then_continue_advances_to_brief(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.VALIDATION)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["approve", "decision", "APPROVED", "--reason", "ok", "--dir", d], clock=clock)
                main(["continue", "--dir", d], clock=clock)
            self.assertEqual(_read(d)["current_phase"], "brief")

    def test_approve_decision_rejected_value(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.VALIDATION)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["approve", "decision", "REJECTED", "--reason", "no", "--dir", d], clock=clock)
            self.assertEqual(rc, 0)
            self.assertEqual(_read(d)["decision"]["decision"], "REJECTED")

    def test_approve_decision_invalid_value_is_usage_error(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.VALIDATION)
            with self.assertRaises(SystemExit) as cm:
                with contextlib.redirect_stderr(io.StringIO()):
                    main(["approve", "decision", "MAYBE", "--reason", "x", "--dir", d], clock=clock)
            self.assertEqual(cm.exception.code, 2)

    def test_approve_execution_respects_override(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.PLANNING, ateam_check={"ready": False, "missing_paths": ["INIT.md"]})
            with contextlib.redirect_stdout(io.StringIO()):
                blocked = main(["approve", "execution", "--reason", "go", "--dir", d], clock=clock)
            self.assertEqual(blocked, 1)
            self.assertEqual(_read(d)["current_phase"], "planning")
            with contextlib.redirect_stdout(io.StringIO()):
                ok = main(["approve", "execution", "--reason", "go", "--override", "--dir", d], clock=clock)
            self.assertEqual(ok, 0)
            data = _read(d)
            self.assertEqual(data["current_phase"], "execution")
            self.assertTrue(data["execution_approval"]["override"])

    def test_approve_done_requires_reason(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.FINAL_VALIDATION)
            with self.assertRaises(SystemExit) as cm:
                with contextlib.redirect_stderr(io.StringIO()):
                    main(["approve", "done", "--dir", d], clock=clock)
            self.assertEqual(cm.exception.code, 2)

    def test_approve_done_advances_to_done(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.FINAL_VALIDATION)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["approve", "done", "--reason", "ship", "--dir", d], clock=clock)
            self.assertEqual(rc, 0)
            self.assertEqual(_read(d)["current_phase"], "done")

    def test_approve_done_refreshes_and_clears_action_required(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.FINAL_VALIDATION)
            from projectpilot.state import state_dir

            ar = state_dir(Path(d)) / "ACTION_REQUIRED.md"
            ar.parent.mkdir(parents=True, exist_ok=True)
            ar.write_text("stale\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["approve", "done", "--reason", "ship", "--dir", d], clock=clock)
            self.assertFalse(ar.exists())

    def test_old_decision_set_still_works(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.VALIDATION)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["decision", "set", "APPROVED", "--reason", "ok", "--dir", d], clock=clock)
            self.assertEqual(rc, 0)
            self.assertEqual(_read(d)["decision"]["decision"], "APPROVED")


if __name__ == "__main__":
    unittest.main()
