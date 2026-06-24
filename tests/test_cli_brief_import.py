import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main
from projectpilot.state import state_path

FROZEN = "2026-06-24T11:00:00Z"


def clock() -> str:
    return FROZEN


def _read(d: str) -> dict:
    return json.loads(state_path(Path(d)).read_text(encoding="utf-8"))


def _reach_brief(d: str) -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        main(["init", "an idea", "--dir", d, "--name", "Demo"], clock=clock)
        main(["validate", "--dir", d], clock=clock)
        main(["decision", "set", "APPROVED", "--reason", "ok", "--dir", d], clock=clock)
        main(["advance", "brief", "--dir", d], clock=clock)


def _write_source(d: str, content: str = "# Approved brief\n\nFrom SkillLab.\n") -> Path:
    source = Path(d) / "skilllab-brief.md"
    source.write_text(content, encoding="utf-8")
    return source


class BriefImportTests(unittest.TestCase):
    def test_import_without_state_fails(self):
        with tempfile.TemporaryDirectory() as d:
            source = _write_source(d)
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["brief", "import", str(source), "--dir", d], clock=clock)
            self.assertEqual(rc, 1)

    def test_import_outside_brief_phase_fails(self):
        with tempfile.TemporaryDirectory() as d:
            source = _write_source(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["init", "idea", "--dir", d], clock=clock)
                rc = main(["brief", "import", str(source), "--dir", d], clock=clock)
            self.assertEqual(rc, 1)
            self.assertFalse((Path(d) / "PROJECT_BRIEF.md").exists())

    def test_import_missing_source_fails(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_brief(d)
            missing = Path(d) / "missing.md"
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["brief", "import", str(missing), "--dir", d], clock=clock)
            self.assertEqual(rc, 1)
            self.assertFalse((Path(d) / "PROJECT_BRIEF.md").exists())

    def test_import_copies_brief_and_advances_to_setup_advice(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_brief(d)
            source = _write_source(d, "# Approved brief\n\nDo the thing.\n")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["brief", "import", str(source), "--dir", d], clock=clock)
            self.assertEqual(rc, 0)
            self.assertEqual(
                (Path(d) / "PROJECT_BRIEF.md").read_text(encoding="utf-8"),
                "# Approved brief\n\nDo the thing.\n",
            )
            self.assertEqual(_read(d)["current_phase"], "setup-advice")

    def test_import_refuses_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_brief(d)
            target = Path(d) / "PROJECT_BRIEF.md"
            target.write_text("existing\n", encoding="utf-8")
            source = _write_source(d, "replacement\n")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(["brief", "import", str(source), "--dir", d], clock=clock)
            self.assertEqual(rc, 1)
            self.assertEqual(target.read_text(encoding="utf-8"), "existing\n")

    def test_import_force_replaces_existing_brief(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_brief(d)
            target = Path(d) / "PROJECT_BRIEF.md"
            target.write_text("existing\n", encoding="utf-8")
            source = _write_source(d, "replacement\n")
            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    ["brief", "import", str(source), "--force", "--dir", d],
                    clock=clock,
                )
            self.assertEqual(rc, 0)
            self.assertEqual(target.read_text(encoding="utf-8"), "replacement\n")

    def test_import_preserves_manual_decision(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_brief(d)
            before = _read(d)["decision"]
            source = _write_source(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["brief", "import", str(source), "--dir", d], clock=clock)
            self.assertEqual(_read(d)["decision"], before)

    def test_import_records_metadata_and_history(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_brief(d)
            source = _write_source(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["brief", "import", str(source), "--dir", d], clock=clock)
            state = _read(d)
            self.assertEqual(state["brief"]["brief_path"], "PROJECT_BRIEF.md")
            self.assertEqual(state["brief"]["brief_imported_at"], FROZEN)
            self.assertEqual(state["brief"]["source_path"], str(source.resolve()))
            self.assertIn("brief_imported", [h["event"] for h in state["history"]])

    def test_status_shows_imported_brief_and_next_action(self):
        with tempfile.TemporaryDirectory() as d:
            _reach_brief(d)
            source = _write_source(d)
            with contextlib.redirect_stdout(io.StringIO()):
                main(["brief", "import", str(source), "--dir", d], clock=clock)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main(["status", "--dir", d])
            text = out.getvalue()
            self.assertIn("Current phase: setup-advice", text)
            self.assertIn("Brief: PROJECT_BRIEF.md imported", text)
            self.assertIn("setup", text.lower())


if __name__ == "__main__":
    unittest.main()
