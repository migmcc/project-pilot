"""Portability of ecosystem integration points (PP-AUDIT-003).

Covers the config-driven A-team source candidates and readiness paths, and
guards the generic wording of user-facing text: SkillLab, the A-team, and
AgentDesk are optional example integrations, never assumed to be present.
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from projectpilot import ateam
from projectpilot.cli import build_parser, main
from projectpilot.commands.check_ateam_cmd import REQUIRED_PATHS, readiness_paths
from projectpilot.state import state_path

FROZEN = "2026-06-24T11:00:00Z"


def clock() -> str:
    return FROZEN


def _write_config(base: Path, text: str) -> None:
    config_dir = base / ".project-pilot"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(text, encoding="utf-8")


def _read(d: str) -> dict:
    return json.loads(state_path(Path(d)).read_text(encoding="utf-8"))


def _reach_planning(d: str) -> None:
    source = Path(d) / "approved-brief.md"
    source.write_text("# Approved brief\n", encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        main(["init", "an idea", "--dir", d, "--name", "Demo"], clock=clock)
        main(["validate", "--dir", d], clock=clock)
        main(["decision", "set", "APPROVED", "--reason", "ok", "--dir", d], clock=clock)
        main(["advance", "brief", "--dir", d], clock=clock)
        main(["brief", "import", str(source), "--dir", d], clock=clock)
        main(["advise-setup", "--dir", d], clock=clock)


class SourceCandidatesConfigTests(unittest.TestCase):
    def test_defaults_when_no_config(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(
                ateam.source_candidates(Path(d)), ateam.DEFAULT_SOURCE_CANDIDATES
            )

    def test_configured_list_overrides_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            _write_config(
                base,
                "ateam_source_paths:\n  - my-templates/.claude\n  - other/.claude\n",
            )
            self.assertEqual(
                ateam.source_candidates(base),
                (Path("my-templates/.claude"), Path("other/.claude")),
            )

    def test_scalar_value_becomes_single_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            _write_config(base, "ateam_source_paths: my-templates/.claude\n")
            self.assertEqual(
                ateam.source_candidates(base), (Path("my-templates/.claude"),)
            )

    def test_empty_list_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            _write_config(base, "ateam_source_paths:\n")
            self.assertEqual(
                ateam.source_candidates(base), ateam.DEFAULT_SOURCE_CANDIDATES
            )

    def test_discover_sources_finds_configured_candidate(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as d:
            home = Path(home_dir)
            base = Path(d)
            source = home / "my-templates" / ".claude"
            (source / "skills").mkdir(parents=True)
            _write_config(base, "ateam_source_paths:\n  - my-templates/.claude\n")
            found = ateam.discover_sources(home, ateam.source_candidates(base))
            self.assertEqual(found, [source])

    def test_setup_ateam_dry_run_uses_configured_source(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as d:
            home = Path(home_dir)
            base = Path(d)
            source = home / "my-templates" / ".claude"
            (source / "skills" / "skill-a").mkdir(parents=True)
            (source / "skills" / "skill-a" / "SKILL.md").write_text("a\n", encoding="utf-8")
            _write_config(base, "ateam_source_paths:\n  - my-templates/.claude\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["setup", "ateam", "--home", home_dir, "--dir", d], clock=clock)
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("Would install from", text)
            self.assertIn("my-templates", text)
            # Dry-run still writes nothing.
            self.assertFalse((home / ".claude").exists())

    def test_doctor_reports_configured_source(self):
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as d:
            home = Path(home_dir)
            base = Path(d)
            source = home / "my-templates" / ".claude"
            (source / "skills").mkdir(parents=True)
            _write_config(base, "ateam_source_paths:\n  - my-templates/.claude\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["doctor", "--dir", d, "--home", home_dir])
            self.assertEqual(rc, 0)
            self.assertIn("my-templates", out.getvalue())


class ReadinessPathsConfigTests(unittest.TestCase):
    def test_defaults_when_no_config(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(readiness_paths(Path(d)), list(REQUIRED_PATHS))

    def test_configured_paths_override_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            _write_config(
                base,
                "ateam_readiness_paths:\n  - docs/TEAM_SETUP.md\n  - .toolkit/\n",
            )
            self.assertEqual(readiness_paths(base), ["docs/TEAM_SETUP.md", ".toolkit/"])

    def test_check_ateam_ready_with_configured_paths(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            base = Path(d)
            _write_config(
                base,
                "ateam_readiness_paths:\n  - docs/TEAM_SETUP.md\n  - .toolkit/\n",
            )
            (base / "docs").mkdir()
            (base / "docs" / "TEAM_SETUP.md").write_text("setup\n", encoding="utf-8")
            (base / ".toolkit").mkdir()
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["check-ateam", "--dir", d], clock=clock)
            self.assertEqual(rc, 0)
            check = _read(d)["ateam_check"]
            self.assertTrue(check["ready"])
            self.assertEqual(check["required_paths"], ["docs/TEAM_SETUP.md", ".toolkit/"])
            self.assertEqual(check["missing_paths"], [])

    def test_check_ateam_missing_configured_paths_not_ready(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            base = Path(d)
            _write_config(base, "ateam_readiness_paths:\n  - docs/TEAM_SETUP.md\n")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["check-ateam", "--dir", d], clock=clock)
            check = _read(d)["ateam_check"]
            self.assertFalse(check["ready"])
            self.assertEqual(check["missing_paths"], ["docs/TEAM_SETUP.md"])

    def test_trailing_slash_requires_a_directory(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_planning(d)
            base = Path(d)
            _write_config(base, "ateam_readiness_paths:\n  - .toolkit/\n")
            # A *file* named .toolkit does not satisfy a directory requirement.
            (base / ".toolkit").write_text("not a dir\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["check-ateam", "--dir", d], clock=clock)
            self.assertFalse(_read(d)["ateam_check"]["ready"])


class GenericWordingTests(unittest.TestCase):
    def test_validate_prompt_mentions_skilllab_only_as_example(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["init", "an idea", "--dir", d], clock=clock)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main(["validate", "--dir", d], clock=clock)
            text = out.getvalue()
            self.assertIn("# Idea validation prompt", text)
            self.assertIn("example", text.lower())
            # The SkillLab slash command survives as a worked example.
            self.assertIn("/skilllab-start-project", text)

    def test_next_at_validation_does_not_assume_skilllab(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["init", "an idea", "--dir", d], clock=clock)
                main(["validate", "--dir", d], clock=clock)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main(["next", "--dir", d])
            self.assertNotIn("SkillLab", out.getvalue())

    def test_status_at_validation_does_not_assume_skilllab(self):
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["init", "an idea", "--dir", d], clock=clock)
                main(["validate", "--dir", d], clock=clock)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main(["status", "--dir", d])
            text = out.getvalue()
            self.assertNotIn("SkillLab", text)
            self.assertIn("Waiting for a recorded validation decision.", text)

    def test_cli_help_does_not_assume_skilllab(self):
        self.assertNotIn("SkillLab", build_parser().format_help())


if __name__ == "__main__":
    unittest.main()
