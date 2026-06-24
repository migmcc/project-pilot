import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main
from projectpilot.state import state_dir, state_path

FROZEN = "2026-06-24T15:00:00Z"


def clock() -> str:
    return FROZEN


def _read(d: str) -> dict:
    return json.loads(state_path(Path(d)).read_text(encoding="utf-8"))


def _idea_file(d: str, text: str = "discover local businesses") -> Path:
    p = Path(d) / "idea.md"
    p.write_text(text + "\n", encoding="utf-8")
    return p


class StartTests(unittest.TestCase):
    def test_start_inits_and_stops_at_validation(self):
        with tempfile.TemporaryDirectory() as d:
            idea = _idea_file(d)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["start", "--idea", str(idea), "--dir", d, "--name", "Demo"], clock=clock)
            self.assertEqual(rc, 0)
            data = _read(d)
            self.assertEqual(data["current_phase"], "validation")
            self.assertEqual(data["project"]["idea_source"], str(idea))
            self.assertEqual(data["project"]["idea"], "discover local businesses")

    def test_start_writes_coordination_files(self):
        with tempfile.TemporaryDirectory() as d:
            idea = _idea_file(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["start", "--idea", str(idea), "--dir", d], clock=clock)
            na = state_dir(Path(d)) / "NEXT_ACTION.md"
            ar = state_dir(Path(d)) / "ACTION_REQUIRED.md"
            self.assertTrue(na.exists())
            self.assertTrue(ar.exists())
            self.assertIn("/skilllab-start-project", ar.read_text(encoding="utf-8"))

    def test_start_missing_idea_file_fails_and_creates_no_state(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["start", "--idea", str(Path(d) / "nope.md"), "--dir", d], clock=clock)
            self.assertEqual(rc, 1)
            self.assertFalse(state_path(Path(d)).exists())

    def test_start_existing_state_does_not_clobber(self):
        with tempfile.TemporaryDirectory() as d:
            idea_a = _idea_file(d, "idea A")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["start", "--idea", str(idea_a), "--dir", d], clock=clock)
            idea_b = Path(d) / "idea2.md"
            idea_b.write_text("idea B\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["start", "--idea", str(idea_b), "--dir", d], clock=clock)
            self.assertEqual(rc, 0)
            self.assertEqual(_read(d)["project"]["idea"], "idea A")


if __name__ == "__main__":
    unittest.main()
