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


class CompactStampTests(unittest.TestCase):
    def test_iso_to_stamp(self):
        self.assertEqual(ateam.compact_stamp("2026-06-26T10:00:00Z"), "20260626-100000")

    def test_padding_is_safe(self):
        # Never raises and always returns the YYYYMMDD-HHMMSS shape.
        self.assertRegex(ateam.compact_stamp(""), r"^\d{8}-\d{6}$")


class BackupExistingTests(unittest.TestCase):
    def test_nothing_to_back_up(self):
        with tempfile.TemporaryDirectory() as d:
            backup_dir, backed_up = ateam.backup_existing(Path(d), "STAMP")
            self.assertIsNone(backup_dir)
            self.assertEqual(backed_up, [])

    def test_backs_up_existing_categories_and_settings(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            _make_claude(ateam.claude_home(home), categories=("skills",), settings=True)
            backup_dir, backed_up = ateam.backup_existing(home, "STAMP")
            self.assertIsNotNone(backup_dir)
            self.assertTrue((backup_dir / "skills" / "placeholder").is_file())
            self.assertTrue((backup_dir / "settings.json").is_file())
            self.assertIn("skills", backed_up)
            self.assertIn("settings.json", backed_up)


class ApplyAteamTests(unittest.TestCase):
    def _source(self, home: Path) -> Path:
        src = home / "00_Base" / ".claude"
        (src / "skills" / "skill-a").mkdir(parents=True)
        (src / "skills" / "skill-a" / "SKILL.md").write_text("alpha\n", encoding="utf-8")
        (src / "agents").mkdir()
        (src / "agents" / "agent-a.md").write_text("agent\n", encoding="utf-8")
        (src / "commands").mkdir()
        return src

    def test_apply_copies_into_empty_target(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            src = self._source(home)
            result = ateam.apply_ateam(src, home, stamp="STAMP")
            self.assertIsNone(result.backup_dir)
            self.assertEqual(len(result.conflicts), 0)
            statuses = {(i.category, i.name): i.status for i in result.items}
            self.assertEqual(statuses[("skills", "skill-a")], "copied")
            self.assertEqual(statuses[("agents", "agent-a.md")], "copied")
            self.assertTrue(
                (ateam.claude_home(home) / "skills" / "skill-a" / "SKILL.md").is_file()
            )

    def test_apply_conflict_writes_sidecar(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            src = self._source(home)
            agents = ateam.claude_home(home) / "agents"
            agents.mkdir(parents=True)
            (agents / "agent-a.md").write_text("DIFFERENT\n", encoding="utf-8")
            result = ateam.apply_ateam(src, home, stamp="STAMP")
            self.assertEqual(len(result.conflicts), 1)
            self.assertEqual(
                (agents / "agent-a.md").read_text(encoding="utf-8"), "DIFFERENT\n"
            )
            self.assertTrue((agents / "agent-a.md.projectpilot-new").is_file())
            # A backup was taken because the target had pre-existing content.
            self.assertIsNotNone(result.backup_dir)

    def test_apply_unchanged_for_identical(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            src = self._source(home)
            agents = ateam.claude_home(home) / "agents"
            agents.mkdir(parents=True)
            (agents / "agent-a.md").write_text("agent\n", encoding="utf-8")
            result = ateam.apply_ateam(src, home, stamp="STAMP")
            self.assertEqual(len(result.unchanged), 1)
            self.assertFalse((agents / "agent-a.md.projectpilot-new").exists())


if __name__ == "__main__":
    unittest.main()
