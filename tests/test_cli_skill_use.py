import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from projectpilot.cli import main
from projectpilot.config import config_path


def write_config(base: Path, body: str) -> None:
    path = config_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def make_skill(root: Path, dirname: str, name: str, description: str, body: str = "Do it.") -> None:
    skill_dir = root / dirname
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f'---\nname: {name}\ndescription: "{description}"\n---\n\n{body}\n', encoding="utf-8"
    )


class SkillUseFixture(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = main(argv)
        return rc, out.getvalue()

    def _init(self, base: Path):
        with contextlib.redirect_stdout(io.StringIO()):
            main(["init", "build a thing", "--dir", str(base), "--name", "Demo"])

    def _project(self, d):
        base = Path(d) / "project"
        base.mkdir()
        lib = Path(d) / "lib"
        make_skill(lib, "create-prd", "create-prd", "Write a PRD.")
        make_skill(lib, "market-research", "market-research", "Do market research.")
        self._init(base)
        write_config(base, "external_skill_paths:\n  - ../lib\n")
        return base


class UseByIdTests(SkillUseFixture):
    def test_no_state(self):
        with tempfile.TemporaryDirectory() as d:
            rc, text = self._run(["skill", "use", "create-prd", "--dir", d])
            self.assertEqual(rc, 1)
            self.assertIn("No ProjectPilot state", text)

    def test_unknown_id(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project(d)
            rc, text = self._run(["skill", "use", "nope", "--dir", str(base)])
            self.assertEqual(rc, 1)
            self.assertIn("No skill found", text)

    def test_writes_prompt_file(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project(d)
            rc, text = self._run(["skill", "use", "create-prd", "--dir", str(base)])
            self.assertEqual(rc, 0)
            out_path = base / "projectpilot_outputs" / "prompts" / "create-prd.md"
            self.assertTrue(out_path.is_file())
            content = out_path.read_text(encoding="utf-8")
            self.assertIn("Selected skill:\ncreate-prd", content)
            self.assertIn("Instructions", content)
            self.assertIn("Wrote", text)

    def test_print_does_not_write(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project(d)
            rc, text = self._run(["skill", "use", "create-prd", "--print", "--dir", str(base)])
            self.assertEqual(rc, 0)
            self.assertIn("Selected skill:", text)
            self.assertFalse((base / "projectpilot_outputs").exists())

    def test_custom_output_path(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project(d)
            rc, text = self._run(["skill", "use", "create-prd", "--output", "myprompt.md", "--dir", str(base)])
            self.assertEqual(rc, 0)
            self.assertTrue((base / "myprompt.md").is_file())

    def test_no_llm_marker_present(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project(d)
            rc, text = self._run(["skill", "use", "create-prd", "--print", "--dir", str(base)])
            self.assertIn("does not call any model", text)


class UseWizardTests(SkillUseFixture):
    def test_no_sources_configured(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            self._init(base)
            rc, text = self._run(["skill", "use", "--dir", str(base)])
            self.assertEqual(rc, 1)
            self.assertIn("No external skill paths configured", text)

    def test_non_interactive_lists_and_exits_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project(d)
            with mock.patch("sys.stdin.isatty", return_value=False):
                rc, text = self._run(["skill", "use", "--dir", str(base)])
            self.assertEqual(rc, 0)
            self.assertIn("Recommended skills for this phase", text)
            self.assertIn("Re-run with `pp skill use <id>`", text)
            self.assertFalse((base / "projectpilot_outputs").exists())

    def test_interactive_selection_builds_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project(d)
            with mock.patch("sys.stdin.isatty", return_value=True), \
                 mock.patch("builtins.input", return_value="1"):
                rc, text = self._run(["skill", "use", "--dir", str(base)])
            self.assertEqual(rc, 0)
            self.assertIn("Wrote", text)
            prompts = list((base / "projectpilot_outputs" / "prompts").glob("*.md"))
            self.assertEqual(len(prompts), 1)

    def test_interactive_cancel(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project(d)
            with mock.patch("sys.stdin.isatty", return_value=True), \
                 mock.patch("builtins.input", return_value="q"):
                rc, text = self._run(["skill", "use", "--dir", str(base)])
            self.assertEqual(rc, 0)
            self.assertIn("Cancelled", text)
            self.assertFalse((base / "projectpilot_outputs").exists())

    def test_interactive_invalid_choice(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project(d)
            with mock.patch("sys.stdin.isatty", return_value=True), \
                 mock.patch("builtins.input", return_value="999"):
                rc, text = self._run(["skill", "use", "--dir", str(base)])
            self.assertEqual(rc, 1)
            self.assertIn("not a valid choice", text)


if __name__ == "__main__":
    unittest.main()
