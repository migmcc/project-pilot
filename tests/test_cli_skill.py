import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main
from projectpilot.config import config_path


def write_config(base: Path, body: str) -> None:
    path = config_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def make_skill(root: Path, name: str, frontmatter: str, body: str = "Body.") -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8")


class SkillCliFixture(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = main(argv)
        return rc, out.getvalue()

    def _project_with_lib(self, d):
        base = Path(d) / "project"
        base.mkdir()
        lib = Path(d) / "pm-skills"
        make_skill(lib, "discovery", "name: Discovery\ndescription: Kick off discovery.")
        write_config(base, "external_skill_paths:\n  - ../pm-skills\n")
        return base


class SourcesTests(SkillCliFixture):
    def test_sources_none_configured(self):
        with tempfile.TemporaryDirectory() as d:
            rc, text = self._run(["skill", "sources", "--dir", d])
            self.assertEqual(rc, 0)
            self.assertIn("No external skill paths configured", text)
            self.assertIn("external_skill_paths", text)

    def test_sources_lists_configured_with_status(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project_with_lib(d)
            write_config(base, "external_skill_paths:\n  - ../pm-skills\n  - ../nope\n")
            rc, text = self._run(["skill", "sources", "--dir", str(base)])
            self.assertEqual(rc, 0)
            self.assertIn("../pm-skills  [ok]", text)
            self.assertIn("../nope  [missing]", text)


class ListTests(SkillCliFixture):
    def test_list_finds_skill(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project_with_lib(d)
            rc, text = self._run(["skill", "list", "--dir", str(base)])
            self.assertEqual(rc, 0)
            self.assertIn("Found 1 skill(s)", text)
            self.assertIn("discovery", text)
            self.assertIn("Discovery", text)

    def test_list_no_sources(self):
        with tempfile.TemporaryDirectory() as d:
            rc, text = self._run(["skill", "list", "--dir", d])
            self.assertEqual(rc, 0)
            self.assertIn("No external skill paths configured", text)

    def test_list_warns_on_missing_source(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            write_config(base, "external_skill_paths:\n  - ../ghost\n")
            rc, text = self._run(["skill", "list", "--dir", str(base)])
            self.assertEqual(rc, 0)
            self.assertIn("do not exist", text)
            self.assertIn("No skills found", text)


class InfoTests(SkillCliFixture):
    def test_info_shows_details(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project_with_lib(d)
            rc, text = self._run(["skill", "info", "discovery", "--dir", str(base)])
            self.assertEqual(rc, 0)
            self.assertIn("Skill: Discovery", text)
            self.assertIn("Id: discovery", text)
            self.assertIn("Kick off discovery.", text)

    def test_info_missing_skill(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project_with_lib(d)
            rc, text = self._run(["skill", "info", "nope", "--dir", str(base)])
            self.assertEqual(rc, 1)
            self.assertIn("No skill found", text)


class RunTests(SkillCliFixture):
    def test_run_writes_output_file(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project_with_lib(d)
            rc, text = self._run(["skill", "run", "discovery", "--dir", str(base)])
            self.assertEqual(rc, 0)
            out_path = base / "projectpilot_outputs" / "skills" / "discovery.md"
            self.assertTrue(out_path.is_file())
            content = out_path.read_text(encoding="utf-8")
            self.assertIn("# Skill: Discovery", content)
            self.assertIn("No LLM was called", content)
            self.assertIn("Wrote", text)

    def test_run_print_does_not_write(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project_with_lib(d)
            rc, text = self._run(["skill", "run", "discovery", "--print", "--dir", str(base)])
            self.assertEqual(rc, 0)
            self.assertIn("# Skill: Discovery", text)
            self.assertFalse((base / "projectpilot_outputs").exists())

    def test_run_missing_skill(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project_with_lib(d)
            rc, text = self._run(["skill", "run", "nope", "--dir", str(base)])
            self.assertEqual(rc, 1)
            self.assertIn("No skill found", text)


if __name__ == "__main__":
    unittest.main()
