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


if __name__ == "__main__":
    unittest.main()
