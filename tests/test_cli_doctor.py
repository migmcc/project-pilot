import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from projectpilot.cli import main
from projectpilot.config import config_path


def configure_graphify(base: Path, text="graphify_enabled: true\n") -> None:
    path = config_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class DoctorTests(unittest.TestCase):
    def test_doctor_runs_and_reports(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["doctor", "--dir", d, "--home", home])
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("doctor", text)
            self.assertIn("Python", text)
            self.assertIn("Git", text)
            self.assertIn("~/.claude", text)
            self.assertIn("changed nothing", text)

    def test_doctor_changes_nothing(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                main(["doctor", "--dir", d, "--home", home])
            # No ~/.claude was created in the injected home.
            self.assertFalse((Path(home) / ".claude").exists())
            # No project state was created in the inspected directory.
            self.assertFalse((Path(d) / ".project-pilot").exists())

    def test_doctor_flags_ambiguous_source(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            source = Path(home) / "00_Base" / ".claude" / "skills"
            source.mkdir(parents=True)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main(["doctor", "--dir", d, "--home", home])
            self.assertIn("00_Base", out.getvalue())

    def test_doctor_does_not_report_ok_for_empty_git(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            (Path(d) / ".git").mkdir()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["doctor", "--dir", d, "--home", home])
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertNotIn("Git repository: OK", text)
            self.assertIn("Git repository: invalid", text)

    def test_doctor_reports_valid_git_as_ok(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            git = Path(d) / ".git"
            git.mkdir()
            (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
            (git / "objects").mkdir()
            (git / "refs").mkdir()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["doctor", "--dir", d, "--home", home])
            self.assertEqual(rc, 0)
            self.assertIn("Git repository: OK", out.getvalue())

    def test_doctor_reports_missing_git(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["doctor", "--dir", d, "--home", home])
            self.assertEqual(rc, 0)
            self.assertIn("Git repository: missing", out.getvalue())

    def test_doctor_reports_partial_superpowers_install(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            root = Path(home) / ".claude"
            skill = root / "skills" / "using-superpowers"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("name: using-superpowers\n", encoding="utf-8")
            (root / "agents").mkdir()
            (root / "commands").mkdir()

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["doctor", "--dir", d, "--home", home])

            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("Claude global directory: yes", text)
            self.assertIn("Claude global skills: yes", text)
            self.assertIn("Global skills count: 1", text)
            self.assertIn("Superpowers skills detected: yes", text)
            self.assertIn("A-team full install: no", text)
            self.assertIn("A-team install status: partial", text)
            self.assertIn("Missing categories: agents, commands", text)
            self.assertFalse((Path(home) / ".project-pilot").exists())

    @mock.patch("projectpilot.commands.doctor_cmd.shutil.which", return_value=None)
    def test_doctor_distinguishes_enabled_but_unavailable(self, which):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            base = Path(d)
            configure_graphify(base)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["doctor", "--dir", d, "--home", home])
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("Knowledge context:", text)
            self.assertIn("Graphify integration: enabled", text)
            self.assertIn("Graphify command on PATH: no", text)
            self.assertIn("Graphify outputs: missing", text)
            self.assertEqual(which.call_args_list.count(mock.call("graphify")), 1)

    @mock.patch(
        "projectpilot.commands.doctor_cmd.shutil.which",
        return_value="C:/Tools/graphify.exe",
    )
    def test_doctor_reports_ready_outputs_without_reading_them(self, which):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            base = Path(d)
            configure_graphify(base)
            graph_dir = base / "graphify-out"
            graph_dir.mkdir()
            (graph_dir / "graph.json").write_text("SECRET GRAPH\n", encoding="utf-8")
            (graph_dir / "GRAPH_REPORT.md").write_text("SECRET REPORT\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["doctor", "--dir", d, "--home", home])
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("Graphify command on PATH: yes", text)
            self.assertIn("Graphify outputs: ready", text)
            self.assertIn("Query budget: 1200", text)
            self.assertNotIn("SECRET GRAPH", text)
            self.assertNotIn("SECRET REPORT", text)

    @mock.patch("projectpilot.commands.doctor_cmd.shutil.which", return_value=None)
    def test_doctor_surfaces_invalid_configuration_defaults(self, which):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            base = Path(d)
            configure_graphify(
                base,
                "graphify_enabled: perhaps\ngraphify_query_budget: huge\n",
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main(["doctor", "--dir", d, "--home", home])
            text = out.getvalue()
            self.assertIn("Graphify integration: disabled", text)
            self.assertIn("graphify_enabled is invalid; using false.", text)
            self.assertIn("using 1200", text)
            self.assertEqual(which.call_args_list.count(mock.call("graphify")), 0)

    @mock.patch("projectpilot.commands.doctor_cmd.shutil.which", return_value=None)
    def test_doctor_tolerates_invalid_utf8_configuration(self, which):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            base = Path(d)
            path = config_path(base)
            path.parent.mkdir(parents=True)
            path.write_bytes(b"graphify_enabled: \xff\n")
            out = io.StringIO()

            with contextlib.redirect_stdout(out):
                rc = main(["doctor", "--dir", d, "--home", home])

            self.assertEqual(rc, 0)
            self.assertIn("Graphify integration: disabled", out.getvalue())
            self.assertEqual(which.call_args_list.count(mock.call("graphify")), 0)

    @mock.patch("projectpilot.commands.doctor_cmd.shutil.which", return_value=None)
    def test_doctor_does_not_crash_on_embedded_nul_output_dir(self, which):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            base = Path(d)
            configure_graphify(
                base,
                "graphify_enabled: true\ngraphify_output_dir: bad\x00path\n",
            )
            out = io.StringIO()

            with contextlib.redirect_stdout(out):
                rc = main(["doctor", "--dir", d, "--home", home])

            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("Graphify integration: enabled", text)
            self.assertIn("Graphify outputs: missing", text)
            self.assertIn(
                "graphify_output_dir cannot be resolved; using graphify-out.",
                text,
            )
            self.assertEqual(which.call_args_list.count(mock.call("graphify")), 1)


if __name__ == "__main__":
    unittest.main()
