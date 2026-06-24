import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main
from projectpilot.state import state_path

FROZEN = "2026-06-24T10:00:00Z"


def clock() -> str:
    return FROZEN


def _read(base: Path) -> dict:
    return json.loads(state_path(base).read_text(encoding="utf-8"))


class InitTests(unittest.TestCase):
    def test_creates_valid_state(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["init", "my idea", "--dir", d, "--name", "Demo"], clock=clock)
            self.assertEqual(rc, 0)
            data = _read(Path(d))
            self.assertEqual(data["schema_version"], 1)
            self.assertEqual(data["current_phase"], "idea")
            self.assertEqual(data["project"]["idea"], "my idea")
            self.assertEqual(data["project"]["created_at"], FROZEN)

    def test_refuses_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["init", "idea1", "--dir", d], clock=clock)
                before = state_path(Path(d)).read_text(encoding="utf-8")
                rc = main(["init", "idea2", "--dir", d], clock=clock)
            self.assertEqual(rc, 1)
            self.assertEqual(state_path(Path(d)).read_text(encoding="utf-8"), before)

    def test_force_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["init", "idea1", "--dir", d], clock=clock)
                rc = main(["init", "idea2", "--dir", d, "--force"], clock=clock)
            self.assertEqual(rc, 0)
            self.assertEqual(_read(Path(d))["project"]["idea"], "idea2")

    def test_missing_idea_is_usage_error(self):
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stderr(io.StringIO()):
                main(["init"], clock=clock)
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
