import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main


class DoctorTests(unittest.TestCase):
    def test_doctor_runs_and_reports(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["doctor", "--dir", d, "--home", home])
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("doctor", text)
            self.assertIn("Python", text)
            self.assertIn("Git", text)
            self.assertIn("~/.claude", text)
            self.assertIn("changed nothing", text)

    def test_doctor_changes_nothing(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["doctor", "--dir", d, "--home", home])
            # No ~/.claude was created in the injected home.
            self.assertFalse((Path(home) / ".claude").exists())
            # No project state was created in the inspected directory.
            self.assertFalse((Path(d) / ".project-pilot").exists())

    def test_doctor_flags_ambiguous_source(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            source = Path(home) / "00_Base" / ".claude" / "skills"
            source.mkdir(parents=True)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main(["doctor", "--dir", d, "--home", home])
            self.assertIn("00_Base", out.getvalue())

    def test_doctor_does_not_report_ok_for_empty_git(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            (Path(d) / ".git").mkdir()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["doctor", "--dir", d, "--home", home])
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertNotIn("Git repository: OK", text)
            self.assertIn("Git repository: invalid", text)

    def test_doctor_reports_valid_git_as_ok(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            git = Path(d) / ".git"
            git.mkdir()
            (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (git / "objects").mkdir()
            (git / "refs").mkdir()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["doctor", "--dir", d, "--home", home])
            self.assertEqual(rc, 0)
            self.assertIn("Git repository: OK", out.getvalue())

    def test_doctor_reports_missing_git(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["doctor", "--dir", d, "--home", home])
            self.assertEqual(rc, 0)
            self.assertIn("Git repository: missing", out.getvalue())

    def test_doctor_reports_partial_superpowers_install(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            root = Path(home) / ".claude"
            skill = root / "skills" / "using-superpowers"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("name: using-superpowers\n", encoding="utf-8")
            (root / "agents").mkdir()
            (root / "commands").mkdir()

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["doctor", "--dir", d, "--home", home])

            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("Claude global directory: yes", text)
            self.assertIn("Claude global skills: yes", text)
            self.assertIn("Global skills count: 1", text)
            self.assertIn("Superpowers skills detected: yes", text)
            self.assertIn("A-team full install: no", text)
            self.assertIn("A-team install status: partial", text)
            self.assertIn("Missing categories: agents, commands", text)
            self.assertFalse((Path(home) / ".project-pilot").exists())


if __name__ == "__main__":
    unittest.main()
