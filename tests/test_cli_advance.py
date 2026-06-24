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


def _validated(d: str) -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        main(["init", "an idea", "--dir", d, "--name", "Demo"], clock=clock)
        main(["validate", "--dir", d], clock=clock)


def _decide(d: str, value: str) -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        main(["decision", "set", value, "--reason", "r", "--dir", d], clock=clock)


class AdvanceTests(unittest.TestCase):
    def test_advance_brief_requires_approved(self):
        with tempfile.TemporaryDirectory() as d:
            _validated(d)
            _decide(d, "APPROVED")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["advance", "brief", "--dir", d], clock=clock)
            self.assertEqual(rc, 0)
            self.assertEqual(_read(d)["current_phase"], "brief")

    def test_advance_blocked_when_needs_rework(self):
        with tempfile.TemporaryDirectory() as d:
            _validated(d)
            _decide(d, "NEEDS_REWORK")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["advance", "brief", "--dir", d], clock=clock)
            self.assertEqual(rc, 1)
            self.assertEqual(_read(d)["current_phase"], "validation")

    def test_advance_blocked_when_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            _validated(d)
            _decide(d, "REJECTED")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["advance", "brief", "--dir", d], clock=clock)
            self.assertEqual(rc, 1)
            self.assertEqual(_read(d)["current_phase"], "validation")

    def test_advance_blocked_when_no_decision(self):
        with tempfile.TemporaryDirectory() as d:
            _validated(d)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["advance", "brief", "--dir", d], clock=clock)
            self.assertEqual(rc, 1)
            self.assertEqual(_read(d)["current_phase"], "validation")

    def test_advance_does_not_generate_brief_document(self):
        with tempfile.TemporaryDirectory() as d:
            _validated(d)
            _decide(d, "APPROVED")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["advance", "brief", "--dir", d], clock=clock)
            self.assertFalse((Path(d) / "PROJECT_BRIEF.md").exists())

    def test_advance_appends_history(self):
        with tempfile.TemporaryDirectory() as d:
            _validated(d)
            _decide(d, "APPROVED")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["advance", "brief", "--dir", d], clock=clock)
            events = [h["event"] for h in _read(d)["history"]]
            self.assertIn("advance", events)

    def test_advance_unknown_target_is_usage_error(self):
        with tempfile.TemporaryDirectory() as d:
            _validated(d)
            _decide(d, "APPROVED")
            with self.assertRaises(SystemExit) as cm:
                with contextlib.redirect_stderr(io.StringIO()):
                    main(["advance", "execution", "--dir", d], clock=clock)
            self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
