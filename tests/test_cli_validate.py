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


def _init(d: str) -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        main(["init", "discover local businesses", "--dir", d, "--name", "Demo"], clock=clock)


def _read(d: str) -> dict:
    return json.loads(state_path(Path(d)).read_text(encoding="utf-8"))


class ValidateTests(unittest.TestCase):
    def test_validate_moves_to_validation_and_emits_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            _init(d)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["validate", "--dir", d], clock=clock)
            self.assertEqual(rc, 0)
            text = out.getvalue()
            self.assertIn("/skilllab-start-project", text)
            self.assertIn("discover local businesses", text)
            self.assertEqual(_read(d)["current_phase"], "validation")

    def test_validate_does_not_record_decision(self):
        with tempfile.TemporaryDirectory() as d:
            _init(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["validate", "--dir", d], clock=clock)
            self.assertIsNone(_read(d)["decision"])

    def test_validate_is_idempotent_in_validation_phase(self):
        with tempfile.TemporaryDirectory() as d:
            _init(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["validate", "--dir", d], clock=clock)
                rc = main(["validate", "--dir", d], clock=clock)
            self.assertEqual(rc, 0)
            self.assertEqual(_read(d)["current_phase"], "validation")

    def test_validate_without_state_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["validate", "--dir", d], clock=clock)
            self.assertEqual(rc, 1)

    def test_validate_appends_history(self):
        with tempfile.TemporaryDirectory() as d:
            _init(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["validate", "--dir", d], clock=clock)
            events = [h["event"] for h in _read(d)["history"]]
            self.assertIn("validate", events)


if __name__ == "__main__":
    unittest.main()
