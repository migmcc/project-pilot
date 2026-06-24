import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main
from projectpilot.state import state_path

FROZEN = "2026-06-24T10:00:00Z"


def clock() -> str:
    return FROZEN


def _init(d: str) -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        main(["init", "an idea", "--dir", d, "--name", "Demo"], clock=clock)


class StatusTests(unittest.TestCase):
    def test_status_after_init_shows_current_and_next(self):
        with tempfile.TemporaryDirectory() as d:
            _init(d)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["status", "--dir", d])
            self.assertEqual(rc, 0)
            text = out.getvalue()
            self.assertIn("idea", text)
            self.assertIn("validation", text)

    def test_status_without_state_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["status", "--dir", d])
            self.assertEqual(rc, 1)

    def test_status_is_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            _init(d)
            path = state_path(Path(d))
            before = path.read_text(encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["status", "--dir", d])
            self.assertEqual(path.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
