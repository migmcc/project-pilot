import tempfile
import unittest
from pathlib import Path

from projectpilot import detectors


class DetectStackTests(unittest.TestCase):
    def test_empty_dir_looks_new(self):
        with tempfile.TemporaryDirectory() as d:
            report = detectors.detect_stack(Path(d))
            self.assertTrue(report.looks_new)
            self.assertTrue(report.is_empty)
            self.assertEqual(report.languages, [])
            self.assertEqual(report.markers, [])

    def test_python_project_detected(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
            (base / "README.md").write_text("# x\n", encoding="utf-8")
            (base / "tests").mkdir()
            report = detectors.detect_stack(base)
            self.assertIn("python", report.languages)
            self.assertTrue(report.has_readme)
            self.assertTrue(report.has_tests)
            self.assertFalse(report.looks_new)
            self.assertIn("pyproject.toml", report.markers)

    def test_node_project_detected(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "package.json").write_text("{}\n", encoding="utf-8")
            report = detectors.detect_stack(base)
            self.assertIn("node", report.languages)
            self.assertFalse(report.looks_new)

    def test_requirements_implies_python_once(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "pyproject.toml").write_text("", encoding="utf-8")
            (base / "requirements.txt").write_text("", encoding="utf-8")
            report = detectors.detect_stack(base)
            self.assertEqual(report.languages.count("python"), 1)

    def test_ci_detected_without_literal_token_in_source(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            # The literal directory is fine in tests; the no-automation guard
            # only scans src/.
            (base / ".github" / "workflows").mkdir(parents=True)
            report = detectors.detect_stack(base)
            self.assertTrue(report.has_ci)


class ToolchainTests(unittest.TestCase):
    def test_python_info(self):
        info = detectors.python_info()
        self.assertTrue(info["available"])
        self.assertRegex(info["version"], r"^\d+\.\d+\.\d+$")

    def test_git_available_returns_bool(self):
        self.assertIsInstance(detectors.git_available(), bool)

    def test_find_git_root(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            self.assertIsNone(detectors.find_git_root(base))
            (base / ".git").mkdir()
            nested = base / "a" / "b"
            nested.mkdir(parents=True)
            self.assertEqual(detectors.find_git_root(nested), base.resolve())
            self.assertTrue(detectors.in_git_repo(nested))


if __name__ == "__main__":
    unittest.main()
