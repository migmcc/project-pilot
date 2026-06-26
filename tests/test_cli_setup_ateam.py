import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main

FROZEN = "2026-06-26T10:00:00Z"
STAMP = "20260626-100000"


def clock() -> str:
    return FROZEN


def _make(root: Path, *categories):
    for category in categories:
        d = root / category
        d.mkdir(parents=True, exist_ok=True)
        (d / "placeholder").write_text("x", encoding="utf-8")


def _make_source(home: Path) -> Path:
    """Build a realistic A-team source under <home>/00_Base/.claude."""
    src = home / "00_Base" / ".claude"
    (src / "skills" / "skill-a").mkdir(parents=True)
    (src / "skills" / "skill-a" / "SKILL.md").write_text("alpha\n", encoding="utf-8")
    (src / "agents").mkdir()
    (src / "agents" / "agent-a.md").write_text("agent\n", encoding="utf-8")
    (src / "commands").mkdir()
    (src / "commands" / "cmd-a.md").write_text("cmd\n", encoding="utf-8")
    (src / "settings.json").write_text('{"a": 1}', encoding="utf-8")
    return src


def _run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = main(argv, clock=clock)
    return rc, out.getvalue()


class DryRunTests(unittest.TestCase):
    def test_no_source_is_dry_run(self):
        with tempfile.TemporaryDirectory() as home:
            rc, text = _run(["setup", "ateam", "--home", home])
            self.assertEqual(rc, 0)
            self.assertIn("dry-run", text)
            self.assertIn("No A-team source found", text)

    def test_dry_run_changes_nothing(self):
        with tempfile.TemporaryDirectory() as home:
            _make_source(Path(home))
            _run(["setup", "ateam", "--home", home])
            self.assertFalse((Path(home) / ".claude").exists())

    def test_dry_run_mentions_apply(self):
        with tempfile.TemporaryDirectory() as home:
            _make_source(Path(home))
            _, text = _run(["setup", "ateam", "--home", home])
            self.assertIn("--apply", text)

    def test_dry_run_reports_partial_superpowers_without_writing(self):
        with tempfile.TemporaryDirectory() as home:
            home_path = Path(home)
            root = home_path / ".claude"
            skill = root / "skills" / "using-superpowers"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("name: using-superpowers\n", encoding="utf-8")
            (root / "agents").mkdir()
            (root / "commands").mkdir()

            rc, text = _run(["setup", "ateam", "--home", home])

            self.assertEqual(rc, 0)
            self.assertIn("dry-run", text)
            self.assertIn("skills: present", text)
            self.assertIn("agents: empty", text)
            self.assertIn("commands: empty", text)
            self.assertIn("Superpowers skills detected: yes", text)
            self.assertIn("A-team full install: no", text)
            self.assertIn("A-team install status: partial", text)
            self.assertTrue((skill / "SKILL.md").is_file())


class ApplyTests(unittest.TestCase):
    def test_apply_creates_claude_and_categories(self):
        with tempfile.TemporaryDirectory() as home:
            home_path = Path(home)
            _make_source(home_path)
            rc, text = _run(["setup", "ateam", "--apply", "--home", home])
            self.assertEqual(rc, 0)
            claude = home_path / ".claude"
            self.assertTrue((claude / "skills" / "skill-a" / "SKILL.md").is_file())
            self.assertTrue((claude / "agents" / "agent-a.md").is_file())
            self.assertTrue((claude / "commands" / "cmd-a.md").is_file())
            self.assertIn("copied", text)

    def test_apply_copies_settings_when_target_absent(self):
        with tempfile.TemporaryDirectory() as home:
            home_path = Path(home)
            _make_source(home_path)
            _run(["setup", "ateam", "--apply", "--home", home])
            self.assertTrue((home_path / ".claude" / "settings.json").is_file())

    def test_apply_makes_backup_when_target_has_content(self):
        with tempfile.TemporaryDirectory() as home:
            home_path = Path(home)
            _make_source(home_path)
            _make(home_path / ".claude", "skills")  # pre-existing content
            rc, text = _run(["setup", "ateam", "--apply", "--home", home])
            self.assertEqual(rc, 0)
            backup = home_path / ".claude" / "backups" / f"projectpilot-ateam-{STAMP}"
            self.assertTrue(backup.is_dir())
            self.assertTrue((backup / "skills" / "placeholder").is_file())
            self.assertIn("Backup:", text)

    def test_apply_no_backup_when_target_empty(self):
        with tempfile.TemporaryDirectory() as home:
            home_path = Path(home)
            _make_source(home_path)
            _, text = _run(["setup", "ateam", "--apply", "--home", home])
            self.assertIn("nothing existing to back up", text)
            self.assertFalse((home_path / ".claude" / "backups").exists())

    def test_apply_does_not_overwrite_differing_file(self):
        with tempfile.TemporaryDirectory() as home:
            home_path = Path(home)
            _make_source(home_path)
            # Pre-existing, DIFFERENT agent file with the same name.
            agents = home_path / ".claude" / "agents"
            agents.mkdir(parents=True)
            existing = agents / "agent-a.md"
            existing.write_text("DO-NOT-TOUCH\n", encoding="utf-8")
            rc, text = _run(["setup", "ateam", "--apply", "--home", home])
            self.assertEqual(rc, 0)
            # Original preserved verbatim.
            self.assertEqual(existing.read_text(encoding="utf-8"), "DO-NOT-TOUCH\n")
            # Incoming written to a sidecar, flagged as conflict.
            sidecar = agents / "agent-a.md.projectpilot-new"
            self.assertTrue(sidecar.is_file())
            self.assertEqual(sidecar.read_text(encoding="utf-8"), "agent\n")
            self.assertIn("conflict", text)

    def test_apply_preserves_identical_file_as_unchanged(self):
        with tempfile.TemporaryDirectory() as home:
            home_path = Path(home)
            _make_source(home_path)
            agents = home_path / ".claude" / "agents"
            agents.mkdir(parents=True)
            (agents / "agent-a.md").write_text("agent\n", encoding="utf-8")  # identical
            _, text = _run(["setup", "ateam", "--apply", "--home", home])
            self.assertIn("agent-a.md: unchanged", text)
            self.assertFalse((agents / "agent-a.md.projectpilot-new").exists())

    def test_apply_preserves_differing_settings(self):
        with tempfile.TemporaryDirectory() as home:
            home_path = Path(home)
            _make_source(home_path)
            claude = home_path / ".claude"
            claude.mkdir(parents=True)
            settings = claude / "settings.json"
            settings.write_text('{"existing": true}', encoding="utf-8")
            _, text = _run(["setup", "ateam", "--apply", "--home", home])
            # Untouched.
            self.assertEqual(settings.read_text(encoding="utf-8"), '{"existing": true}')
            self.assertIn("preserved", text)

    def test_apply_fails_clean_without_source(self):
        with tempfile.TemporaryDirectory() as home:
            home_path = Path(home)
            rc, text = _run(["setup", "ateam", "--apply", "--home", home])
            self.assertEqual(rc, 1)
            self.assertIn("No valid A-team source", text)
            self.assertFalse((home_path / ".claude").exists())

    def test_apply_does_not_modify_source(self):
        with tempfile.TemporaryDirectory() as home:
            home_path = Path(home)
            src = _make_source(home_path)
            _run(["setup", "ateam", "--apply", "--home", home])
            # 00_Base source remains intact.
            self.assertTrue((src / "skills" / "skill-a" / "SKILL.md").is_file())
            self.assertEqual(
                (src / "skills" / "skill-a" / "SKILL.md").read_text(encoding="utf-8"),
                "alpha\n",
            )


if __name__ == "__main__":
    unittest.main()
