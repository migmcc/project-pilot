import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main
from projectpilot.phases import Phase
from projectpilot.state import ProjectState, save_state, state_path

FROZEN = "2026-06-24T12:00:00Z"


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


class FinalValidationTests(unittest.TestCase):
    def test_prepare_from_execution_advances_and_records_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.EXECUTION)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["final-validation", "prepare", "--dir", d], clock=clock)
            self.assertEqual(rc, 0)
            data = _read(d)
            self.assertEqual(data["current_phase"], "final-validation")
            fv = data["final_validation"]
            self.assertEqual(fv["prepared_at"], FROZEN)
            self.assertEqual(fv["source"], "deterministic")
            self.assertTrue(fv["required_checks"])

    def test_prepare_outside_execution_fails(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.IDEA)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["final-validation", "prepare", "--dir", d], clock=clock)
            self.assertEqual(rc, 1)
            self.assertEqual(_read(d)["current_phase"], "idea")

    def test_prepare_without_state_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["final-validation", "prepare", "--dir", d], clock=clock)
            self.assertEqual(rc, 1)

    def test_prepare_appends_history(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.EXECUTION)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["final-validation", "prepare", "--dir", d], clock=clock)
            events = [h["event"] for h in _read(d)["history"]]
            self.assertIn("final_validation_prepared", events)

    def test_prepare_creates_no_extra_files(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.EXECUTION)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["final-validation", "prepare", "--dir", d], clock=clock)
            # Only the .project-pilot state dir should exist at the project root.
            entries = sorted(p.name for p in Path(d).iterdir())
            self.assertEqual(entries, [".project-pilot"])

    def test_status_shows_final_validation_after_prepare(self):
        with tempfile.TemporaryDirectory() as d:
            _state_at(d, Phase.EXECUTION)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["final-validation", "prepare", "--dir", d], clock=clock)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main(["status", "--dir", d])
            self.assertIn("Final validation", out.getvalue())


if __name__ == "__main__":
    unittest.main()
