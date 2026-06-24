import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main
from projectpilot.phases import Phase
from projectpilot.state import ProjectState, save_state, state_dir, state_path

FROZEN = "2026-06-24T15:00:00Z"


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


def _na(d: str) -> str:
    return (state_dir(Path(d)) / "NEXT_ACTION.md").read_text(encoding="utf-8")


def _ar_path(d: str) -> Path:
    return state_dir(Path(d)) / "ACTION_REQUIRED.md"


class ContinueTests(unittest.TestCase):
    def test_continue_without_state_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["continue", "--dir", d], clock=clock)
            self.assertEqual(rc, 1)

    def test_continue_from_idea_advances_to_validation(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.IDEA)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["continue", "--dir", d], clock=clock)
            self.assertEqual(rc, 0)
            self.assertEqual(_read(d)["current_phase"], "validation")
            self.assertTrue(_ar_path(d).exists())

    def test_continue_after_approved_advances_to_brief(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(
                d,
                Phase.VALIDATION,
                decision={
                    "decision": "APPROVED",
                    "reason": "ok",
                    "timestamp": FROZEN,
                    "source": "manual",
                    "current_stage": "validation",
                },
            )
            with contextlib.redirect_stdout(io.StringIO()):
                main(["continue", "--dir", d], clock=clock)
            self.assertEqual(_read(d)["current_phase"], "brief")
            self.assertIn("brief import", _ar_path(d).read_text(encoding="utf-8"))

    def test_continue_blocks_when_decision_not_approved(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(
                d,
                Phase.VALIDATION,
                decision={
                    "decision": "NEEDS_REWORK",
                    "reason": "x",
                    "timestamp": FROZEN,
                    "source": "manual",
                    "current_stage": "validation",
                },
            )
            with contextlib.redirect_stdout(io.StringIO()):
                main(["continue", "--dir", d], clock=clock)
            self.assertEqual(_read(d)["current_phase"], "validation")
            self.assertIn("NEEDS_REWORK", _ar_path(d).read_text(encoding="utf-8"))

    def test_continue_from_setup_advice_advances_to_planning(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.SETUP_ADVICE, brief={"brief_path": "PROJECT_BRIEF.md"})
            with contextlib.redirect_stdout(io.StringIO()):
                main(["continue", "--dir", d], clock=clock)
            self.assertEqual(_read(d)["current_phase"], "planning")
            self.assertIn("approve execution", _ar_path(d).read_text(encoding="utf-8"))

    def test_continue_at_done_removes_action_required(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.DONE)
            _ar_path(d).write_text("stale\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["continue", "--dir", d], clock=clock)
            self.assertEqual(rc, 0)
            self.assertFalse(_ar_path(d).exists())
            self.assertIn("complete", _na(d).lower())

    def test_next_action_is_deterministic(self):
        # A blocked state does not change between runs, so two continues with a
        # frozen clock must produce byte-identical NEXT_ACTION.md.
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.VALIDATION)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["continue", "--dir", d], clock=clock)
            first = _na(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["continue", "--dir", d], clock=clock)
            self.assertEqual(_na(d), first)


if __name__ == "__main__":
    unittest.main()
