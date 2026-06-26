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

    def test_analyze_is_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["analyze", "--dir", d])
            self.assertFalse((Path(d) / ".project-pilot").exists())


if __name__ == "__main__":
    unittest.main()
