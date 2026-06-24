import contextlib
import io
import tempfile
import unittest

from projectpilot.cli import main

FROZEN = "2026-06-24T11:00:00Z"


def clock() -> str:
    return FROZEN


def _status(d: str) -> str:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        main(["status", "--dir", d])
    return out.getvalue()


class StatusDecisionTests(unittest.TestCase):
    def test_status_shows_no_decision_initially(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["init", "idea", "--dir", d], clock=clock)
                main(["validate", "--dir", d], clock=clock)
            text = _status(d)
            self.assertIn("Decision:", text)
            self.assertIn("none", text.lower())

    def test_status_shows_recorded_decision_and_gate(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["init", "idea", "--dir", d], clock=clock)
                main(["validate", "--dir", d], clock=clock)
                main(["decision", "set", "APPROVED", "--reason", "ok", "--dir", d], clock=clock)
            text = _status(d)
            self.assertIn("APPROVED", text)
            self.assertIn("advance brief", text)


if __name__ == "__main__":
    unittest.main()
