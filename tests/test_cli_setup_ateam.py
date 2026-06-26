import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main


def _make(root: Path, *categories):
    for category in categories:
        d = root / category
        d.mkdir(parents=True, exist_ok=True)
        (d / "placeholder").write_text("x", encoding="utf-8")


class SetupAteamTests(unittest.TestCase):
    def test_no_source_is_dry_run(self):
        with tempfile.TemporaryDirectory() as home:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["setup", "ateam", "--home", home])
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("dry-run", text)
            self.assertIn("No A-team source found", text)

    def test_changes_nothing(self):
        with tempfile.TemporaryDirectory() as home:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["setup", "ateam", "--home", home])
            self.assertFalse((Path(home) / ".claude").exists())

    def test_reports_conflicts_and_backup_recommendation(self):
        with tempfile.TemporaryDirectory() as home:
            home_path = Path(home)
            _make(home_path / "00_Base" / ".claude", "skills", "agents")
            _make(home_path / ".claude", "skills")  # target already has skills
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["setup", "ateam", "--home", home])
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("Would install from", text)
            self.assertIn("conflicts", text.lower())
            self.assertIn("back up ~/.claude", text)
            self.assertIn("not touched", text)
            # Target was not modified: only the pre-existing 'skills' remains.
            self.assertFalse((home_path / ".claude" / "agents").exists())


if __name__ == "__main__":
    unittest.main()
