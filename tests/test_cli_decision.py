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


def _init_validated(d: str) -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        main(["init", "an idea", "--dir", d, "--name", "Demo"], clock=clock)
        main(["validate", "--dir", d], clock=clock)


class DecisionSetTests(unittest.TestCase):
    def test_records_all_fields(self):
        with tempfile.TemporaryDirectory() as d:
            _init_validated(d)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    ["decision", "set", "APPROVED", "--reason", "looks good", "--dir", d],
                    clock=clock,
                )
            self.assertEqual(rc, 0)
            decision = _read(d)["decision"]
            self.assertEqual(decision["decision"], "APPROVED")
            self.assertEqual(decision["reason"], "looks good")
            self.assertEqual(decision["source"], "manual")
            self.assertEqual(decision["timestamp"], FROZEN)
            self.assertEqual(decision["current_stage"], "validation")

    def test_decision_does_not_advance_phase(self):
        with tempfile.TemporaryDirectory() as d:
            _init_validated(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(
                    ["decision", "set", "APPROVED", "--reason", "ok", "--dir", d],
                    clock=clock,
                )
            self.assertEqual(_read(d)["current_phase"], "validation")

    def test_needs_rework_and_rejected_are_accepted_values(self):
        for value in ("NEEDS_REWORK", "REJECTED"):
            with tempfile.TemporaryDirectory() as d:
                _init_validated(d)
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = main(
                        ["decision", "set", value, "--reason", "r", "--dir", d],
                        clock=clock,
                    )
                self.assertEqual(rc, 0)
                self.assertEqual(_read(d)["decision"]["decision"], value)

    def test_invalid_decision_value_is_usage_error(self):
        with tempfile.TemporaryDirectory() as d:
            _init_validated(d)
            with self.assertRaises(SystemExit) as cm:
                with contextlib.redirect_stderr(io.StringIO()):
                    main(["decision", "set", "MAYBE", "--reason", "r", "--dir", d], clock=clock)
            self.assertEqual(cm.exception.code, 2)

    def test_decision_before_validation_fails(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["init", "idea", "--dir", d], clock=clock)
                rc = main(
                    ["decision", "set", "APPROVED", "--reason", "r", "--dir", d],
                    clock=clock,
                )
            self.assertEqual(rc, 1)

    def test_decision_appends_history(self):
        with tempfile.TemporaryDirectory() as d:
            _init_validated(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["decision", "set", "APPROVED", "--reason", "r", "--dir", d], clock=clock)
            events = [h["event"] for h in _read(d)["history"]]
            self.assertIn("decision", events)


if __name__ == "__main__":
    unittest.main()
