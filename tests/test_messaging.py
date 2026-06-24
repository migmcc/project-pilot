"""Run G — guard against stale/obsolete lifecycle messaging.

Ensures hints no longer advertise already-shipped commands as "(future:)" and
that the CLI description is neutral (not pinned to "Run A foundation").
"""
import contextlib
import io
import tempfile
import unittest

from projectpilot.cli import build_parser, main
from projectpilot.phases import GATE_FOR_NEXT, NEXT_ACTION


class MessagingTests(unittest.TestCase):
    def test_next_action_has_no_future_markers(self):
        offenders = [v for v in NEXT_ACTION.values() if "future" in v.lower()]
        self.assertEqual(offenders, [])

    def test_gate_text_has_no_future_markers(self):
        offenders = [v for v in GATE_FOR_NEXT.values() if "future" in v.lower()]
        self.assertEqual(offenders, [])

    def test_cli_description_is_neutral(self):
        self.assertEqual(build_parser().description, "ProjectPilot lifecycle orchestrator")

    def test_status_output_has_no_future_marker(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["init", "an idea", "--dir", d])
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main(["status", "--dir", d])
            self.assertNotIn("future", out.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
