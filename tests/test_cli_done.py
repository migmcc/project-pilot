import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main
from projectpilot.phases import Phase
from projectpilot.state import ProjectState, save_state, state_path

FROZEN = "2026-06-24T13:00:00Z"


def clock() -> str:
    return FROZEN


def _state_at(d: str, phase: Phase) -> None:
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
        ),
    )


def _read(d: str) -> dict:
    return json.loads(state_path(Path(d)).read_text(encoding="utf-8"))


class DoneApproveTests(unittest.TestCase):
    def test_approve_from_final_validation_advances_to_done(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.FINAL_VALIDATION)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["done", "approve", "--reason", "all checks pass", "--dir", d], clock=clock)
            self.assertEqual(rc, 0)
            data = _read(d)
            self.assertEqual(data["current_phase"], "done")
            approval = data["done_approval"]
            self.assertEqual(approval["reason"], "all checks pass")
            self.assertEqual(approval["source"], "manual")
            self.assertEqual(approval["approved_at"], FROZEN)

    def test_approve_outside_final_validation_fails(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.EXECUTION)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["done", "approve", "--reason", "r", "--dir", d], clock=clock)
            self.assertEqual(rc, 1)
            self.assertEqual(_read(d)["current_phase"], "execution")

    def test_reason_is_required(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.FINAL_VALIDATION)
            with self.assertRaises(SystemExit) as cm:
                with contextlib.redirect_stderr(io.StringIO()):
                    main(["done", "approve", "--dir", d], clock=clock)
            self.assertEqual(cm.exception.code, 2)

    def test_approve_without_state_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["done", "approve", "--reason", "r", "--dir", d], clock=clock)
            self.assertEqual(rc, 1)

    def test_approve_appends_history(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.FINAL_VALIDATION)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["done", "approve", "--reason", "r", "--dir", d], clock=clock)
            events = [h["event"] for h in _read(d)["history"]]
            self.assertIn("done_approved", events)

    def test_status_shows_done_after_approve(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.FINAL_VALIDATION)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["done", "approve", "--reason", "r", "--dir", d], clock=clock)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main(["status", "--dir", d])
            text = out.getvalue()
            self.assertIn("done", text.lower())


if __name__ == "__main__":
    unittest.main()
