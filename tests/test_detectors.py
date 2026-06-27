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


def _make_valid_git_dir(base: Path) -> Path:
    """Create a minimally valid ``.git`` directory under ``base``."""
    git = base / ".git"
    git.mkdir()
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "objects").mkdir()
    (git / "refs").mkdir()
    return git


class GitRepoStatusTests(unittest.TestCase):
    def test_missing_when_no_git(self):
        with tempfile.TemporaryDirectory() as d:
            status = detectors.git_repo_status(Path(d))
            self.assertEqual(status.status, detectors.GIT_MISSING)
            self.assertIsNone(status.root)
            self.assertFalse(status.ok)

    def test_empty_git_dir_is_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / ".git").mkdir()
            status = detectors.git_repo_status(base)
            self.assertEqual(status.status, detectors.GIT_INVALID)
            self.assertEqual(status.root, base.resolve())
            self.assertFalse(status.ok)

    def test_incomplete_git_dir_is_invalid(self):
        # HEAD present but objects/ and refs/ missing.
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            git = base / ".git"
            git.mkdir()
            (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            status = detectors.git_repo_status(base)
            self.assertEqual(status.status, detectors.GIT_INVALID)

    def test_valid_git_dir_is_ok(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            _make_valid_git_dir(base)
            status = detectors.git_repo_status(base)
            self.assertEqual(status.status, detectors.GIT_OK)
            self.assertTrue(status.ok)
            self.assertEqual(status.root, base.resolve())

    def test_valid_git_dir_found_from_nested(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            _make_valid_git_dir(base)
            nested = base / "a" / "b"
            nested.mkdir(parents=True)
            status = detectors.git_repo_status(nested)
            self.assertEqual(status.status, detectors.GIT_OK)
            self.assertEqual(status.root, base.resolve())

    def test_gitdir_file_pointing_to_valid_dir_is_ok(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            real = base / "real-git"
            real.mkdir()
            (real / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (real / "objects").mkdir()
            (real / "refs").mkdir()
            work = base / "work"
            work.mkdir()
            (work / ".git").write_text(f"gitdir: {real}\n", encoding="utf-8")
            status = detectors.git_repo_status(work)
            self.assertEqual(status.status, detectors.GIT_OK)
            self.assertEqual(status.root, work.resolve())

    def test_gitdir_file_relative_target_is_ok(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            real = base / "real-git"
            real.mkdir()
            (real / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (real / "objects").mkdir()
            (real / "refs").mkdir()
            work = base / "work"
            work.mkdir()
            (work / ".git").write_text("gitdir: ../real-git\n", encoding="utf-8")
            status = detectors.git_repo_status(work)
            self.assertEqual(status.status, detectors.GIT_OK)

    def test_gitdir_file_pointing_to_missing_dir_is_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / ".git").write_text("gitdir: ./nowhere\n", encoding="utf-8")
            status = detectors.git_repo_status(base)
            self.assertEqual(status.status, detectors.GIT_INVALID)

    def test_gitdir_file_without_gitdir_line_is_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / ".git").write_text("garbage\n", encoding="utf-8")
            status = detectors.git_repo_status(base)
            self.assertEqual(status.status, detectors.GIT_INVALID)

    def test_worktree_gitdir_with_commondir_is_ok(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            # Shared common dir holds objects/ and refs/.
            common = base / ".git"
            common.mkdir()
            (common / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (common / "objects").mkdir()
            (common / "refs").mkdir()
            # Linked worktree git dir: HEAD + commondir pointing back to common.
            wt_gitdir = common / "worktrees" / "wt1"
            wt_gitdir.mkdir(parents=True)
            (wt_gitdir / "HEAD").write_text("ref: refs/heads/wt1\n", encoding="utf-8")
            (wt_gitdir / "commondir").write_text("../..\n", encoding="utf-8")
            work = base / "wt1"
            work.mkdir()
            (work / ".git").write_text(f"gitdir: {wt_gitdir}\n", encoding="utf-8")
            status = detectors.git_repo_status(work)
            self.assertEqual(status.status, detectors.GIT_OK)


if __name__ == "__main__":
    unittest.main()
