import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main


class AnalyzeTests(unittest.TestCase):
    def test_analyze_empty_dir_reports_new_and_uninitialized(self):
        with tempfile.TemporaryDirectory() as d:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["analyze", "--dir", d])
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("new", text)
            self.assertIn("ProjectPilot initialized: no", text)
            self.assertIn('pp init', text)

    def test_analyze_python_project(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            (base / "tests").mkdir()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["analyze", "--dir", d])
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("python", text)
            self.assertIn("Tests detected: yes", text)
            self.assertIn("existing", text)

    def test_analyze_does_not_call_empty_git_valid(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".git").mkdir()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["analyze", "--dir", d])
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertNotIn("Git repository: OK", text)
            self.assertIn("Git repository: invalid", text)

    def test_analyze_reports_valid_git_ok(self):
        with tempfile.TemporaryDirectory() as d:
            git = Path(d) / ".git"
            git.mkdir()
            (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (git / "objects").mkdir()
            (git / "refs").mkdir()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["analyze", "--dir", d])
            self.assertEqual(rc, 0)
            self.assertIn("Git repository: OK", out.getvalue())

    def test_analyze_is_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["analyze", "--dir", d])
            self.assertFalse((Path(d) / ".project-pilot").exists())


class AnalyzePositionalDirTests(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = main(argv)
        return rc, out.getvalue()

    def test_no_args_uses_current_dir(self):
        rc, text = self._run(["analyze"])
        self.assertEqual(rc, 0)
        self.assertIn("ProjectPilot analyze:", text)

    def test_positional_dot(self):
        rc, text = self._run(["analyze", "."])
        self.assertEqual(rc, 0)
        self.assertIn("ProjectPilot analyze:", text)

    def test_dir_flag_dot_still_works(self):
        rc, _ = self._run(["analyze", "--dir", "."])
        self.assertEqual(rc, 0)

    def test_positional_path_points_at_temp_project(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            rc, text = self._run(["analyze", d])
            self.assertEqual(rc, 0)
            self.assertIn("python", text)
            self.assertIn(str(Path(d).resolve()), text)

    def test_positional_and_dir_conflict_fails_clean(self):
        with tempfile.TemporaryDirectory() as d:
            rc, text = self._run(["analyze", ".", "--dir", d])
            self.assertEqual(rc, 2)
            self.assertIn("Use either positional path or --dir, not both.", text)
            # Nothing was written to either location.
            self.assertFalse((Path(d) / ".project-pilot").exists())

    def test_positional_initialized_project(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["init", "an idea", "--dir", d, "--name", "Demo"])
            rc, text = self._run(["analyze", d])
            self.assertEqual(rc, 0)
            self.assertIn("ProjectPilot initialized: yes", text)

    def test_positional_uninitialized_project(self):
        with tempfile.TemporaryDirectory() as d:
            rc, text = self._run(["analyze", d])
            self.assertEqual(rc, 0)
            self.assertIn("ProjectPilot initialized: no", text)


if __name__ == "__main__":
    unittest.main()
