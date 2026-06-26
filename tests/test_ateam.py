import tempfile
import unittest
from pathlib import Path

from projectpilot import ateam


def _make_claude(root: Path, *, categories=(), settings=False, signal=False):
    root.mkdir(parents=True, exist_ok=True)
    for category in categories:
        cat_dir = root / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        (cat_dir / "placeholder").write_text("x", encoding="utf-8")
    if signal:
        (root / "skills" / ateam.ATEAM_SIGNAL_SKILL).mkdir(parents=True, exist_ok=True)
    if settings:
        (root / "settings.json").write_text("{}", encoding="utf-8")


class InspectEnvTests(unittest.TestCase):
    def test_missing_home(self):
        with tempfile.TemporaryDirectory() as d:
            env = ateam.inspect_env(Path(d))
            self.assertFalse(env.root_exists)
            self.assertFalse(env.ateam_likely)
            self.assertFalse(any(env.categories.values()))

    def test_signal_marks_ateam_likely(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            _make_claude(ateam.claude_home(home), categories=("skills",), signal=True)
            env = ateam.inspect_env(home)
            self.assertTrue(env.root_exists)
            self.assertTrue(env.ateam_signal)
            self.assertTrue(env.ateam_likely)

    def test_fully_populated_marks_likely_without_signal(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            _make_claude(ateam.claude_home(home), categories=ateam.ATEAM_CATEGORIES)
            env = ateam.inspect_env(home)
            self.assertFalse(env.ateam_signal)
            self.assertTrue(env.ateam_likely)


class DiscoverSourcesTests(unittest.TestCase):
    def test_finds_00_base_source(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            source = home / "00_Base" / ".claude"
            _make_claude(source, categories=("skills", "agents"))
            found = ateam.discover_sources(home)
            self.assertIn(source, found)

    def test_no_sources(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(ateam.discover_sources(Path(d)), [])


class PlanInstallTests(unittest.TestCase):
    def test_conflict_when_target_populated(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            source = home / "00_Base" / ".claude"
            _make_claude(source, categories=("skills",), settings=True)
            _make_claude(ateam.claude_home(home), categories=("skills",), settings=True)
            plan = ateam.plan_install(source, home)
            self.assertIn("skills", plan.conflicts)
            self.assertIn("settings.json", plan.conflicts)

    def test_no_conflict_when_target_empty(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            source = home / "00_Base" / ".claude"
            _make_claude(source, categories=("skills", "agents", "commands"))
            plan = ateam.plan_install(source, home)
            self.assertEqual(plan.conflicts, [])
            skills_plan = next(c for c in plan.categories if c.category == "skills")
            self.assertEqual(skills_plan.source_count, 1)


if __name__ == "__main__":
    unittest.main()
