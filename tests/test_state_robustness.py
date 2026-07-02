"""Robust state handling (PP-AUDIT-001) and atomic writes (PP-AUDIT-004).

Corrupted or hand-edited ``status.json`` / ``artifacts.json`` files must fail
with a friendly message (exit code 1, file path, reason, recovery hint) instead
of a raw traceback, and state writes must be atomic (temp file + ``os.replace``).
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from projectpilot import state as state_mod
from projectpilot.cli import main
from projectpilot.errors import ProjectPilotError, StateCorruptedError
from projectpilot.state import atomic_write_text, load_state, state_dir, state_path

FROZEN = "2026-07-02T10:00:00Z"


def clock() -> str:
    return FROZEN


def _run(argv) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = main(argv, clock=clock)
    return rc, out.getvalue()


def _init(d: str) -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        main(["init", "an idea", "--dir", d, "--name", "Demo"], clock=clock)


def _valid_status(phase: str = "idea", **overrides) -> dict:
    data = {
        "schema_version": 1,
        "project": {
            "name": "Demo",
            "slug": "demo",
            "idea": "an idea",
            "created_at": FROZEN,
            "idea_source": None,
        },
        "current_phase": phase,
        "decision": None,
        "brief": None,
        "setup_advice": None,
        "ateam_check": None,
        "execution_approval": None,
        "final_validation": None,
        "done_approval": None,
        "history": [],
        "updated_at": FROZEN,
    }
    data.update(overrides)
    return data


def _write_status(d: str, payload) -> Path:
    path = state_path(Path(d))
    path.parent.mkdir(parents=True, exist_ok=True)
    text = payload if isinstance(payload, str) else json.dumps(payload, indent=2)
    path.write_text(text, encoding="utf-8")
    return path


def _write_artifacts(d: str, payload) -> Path:
    path = state_dir(Path(d)) / "artifacts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = payload if isinstance(payload, str) else json.dumps(payload, indent=2)
    path.write_text(text, encoding="utf-8")
    return path


#: Commands that read status.json and must fail cleanly when it is corrupted.
_STATE_READING_COMMANDS = (
    ["status"],
    ["next"],
    ["dashboard"],
    ["phase", "check"],
    ["artifact", "list"],
)


class CorruptedStatusTests(unittest.TestCase):
    def _assert_friendly_failure(self, d: str, path: Path, argv: list[str], detail: str):
        rc, out = _run([*argv, "--dir", d])
        label = f"{argv} with {detail}"
        self.assertEqual(rc, 1, label)
        self.assertIn(str(path), out, label)
        self.assertNotIn("Traceback", out, label)
        self.assertIn("Problem:", out, label)

    def test_malformed_json_fails_cleanly_everywhere(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write_status(d, "{ this is not json")
            for argv in _STATE_READING_COMMANDS:
                self._assert_friendly_failure(d, path, argv, "malformed JSON")
            rc, out = _run(["status", "--dir", d])
            self.assertIn("not valid JSON", out)
            self.assertIn("pp init", out)  # recovery hint

    def test_missing_project_key_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            payload = _valid_status()
            del payload["project"]
            path = _write_status(d, payload)
            rc, out = _run(["status", "--dir", d])
            self.assertEqual(rc, 1)
            self.assertIn(str(path), out)
            self.assertIn("'project'", out)
            self.assertNotIn("Traceback", out)

    def test_invalid_phase_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write_status(d, _valid_status(phase="banana"))
            for argv in (["status"], ["next"], ["dashboard"]):
                rc, out = _run([*argv, "--dir", d])
                self.assertEqual(rc, 1, argv)
                self.assertIn(str(path), out, argv)
                self.assertIn("banana", out, argv)
                self.assertNotIn("Traceback", out, argv)

    def test_wrong_typed_optional_section_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write_status(d, _valid_status(decision="APPROVED"))
            rc, out = _run(["status", "--dir", d])
            self.assertEqual(rc, 1)
            self.assertIn(str(path), out)
            self.assertIn("'decision'", out)
            self.assertNotIn("Traceback", out)

    def test_wrong_typed_history_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            path = _write_status(d, _valid_status(history=["not-an-object"]))
            rc, out = _run(["status", "--dir", d])
            self.assertEqual(rc, 1)
            self.assertIn(str(path), out)
            self.assertIn("'history'", out)

    def test_load_state_raises_typed_error(self):
        with tempfile.TemporaryDirectory() as d:
            _write_status(d, "not json at all")
            with self.assertRaises(StateCorruptedError) as ctx:
                load_state(Path(d))
            self.assertIsInstance(ctx.exception, ProjectPilotError)
            self.assertTrue(ctx.exception.hint)

    def test_init_force_recovers_from_corrupted_state(self):
        with tempfile.TemporaryDirectory() as d:
            _write_status(d, "{ broken")
            rc, _ = _run(["init", "fresh idea", "--dir", d, "--force"])
            self.assertEqual(rc, 0)
            rc, out = _run(["status", "--dir", d])
            self.assertEqual(rc, 0)
            self.assertIn("Current phase: idea", out)
            data = json.loads(state_path(Path(d)).read_text(encoding="utf-8"))
            self.assertEqual(data["project"]["idea"], "fresh idea")


class ToleratedHandEditsTests(unittest.TestCase):
    """Optional sub-dicts missing expected keys degrade gracefully in status."""

    def test_decision_missing_verdict_key(self):
        with tempfile.TemporaryDirectory() as d:
            _write_status(
                d, _valid_status(phase="validation", decision={"reason": "hand-edited"})
            )
            rc, out = _run(["status", "--dir", d])
            self.assertEqual(rc, 0)
            self.assertIn("(unknown)", out)

    def test_recorded_sections_missing_keys(self):
        with tempfile.TemporaryDirectory() as d:
            _write_status(
                d,
                _valid_status(
                    phase="execution",
                    ateam_check={"checked_at": FROZEN},
                    execution_approval={"approved_at": FROZEN},
                    brief={"brief_imported_at": FROZEN},
                    setup_advice={"source": "deterministic"},
                    done_approval={"source": "manual"},
                    final_validation={"source": "deterministic"},
                ),
            )
            rc, out = _run(["status", "--dir", d])
            self.assertEqual(rc, 0)
            self.assertNotIn("Traceback", out)


class CorruptedInventoryTests(unittest.TestCase):
    def test_malformed_artifacts_json_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            _init(d)
            path = _write_artifacts(d, "[ broken")
            for argv in (["artifact", "list"], ["dashboard"], ["phase", "check"]):
                rc, out = _run([*argv, "--dir", d])
                self.assertEqual(rc, 1, argv)
                self.assertIn(str(path), out, argv)
                self.assertNotIn("Traceback", out, argv)
            rc, out = _run(["artifact", "list", "--dir", d])
            self.assertIn("not valid JSON", out)
            self.assertIn("pp artifact add", out)  # recovery hint

    def test_record_missing_required_field_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            _init(d)
            path = _write_artifacts(d, {"artifacts": [{"id": "x", "path": "a.md"}]})
            rc, out = _run(["artifact", "list", "--dir", d])
            self.assertEqual(rc, 1)
            self.assertIn(str(path), out)
            self.assertIn("missing the required field", out)
            self.assertNotIn("Traceback", out)

    def test_record_not_an_object_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            _init(d)
            path = _write_artifacts(d, {"artifacts": ["not-a-record"]})
            rc, out = _run(["artifact", "list", "--dir", d])
            self.assertEqual(rc, 1)
            self.assertIn(str(path), out)
            self.assertNotIn("Traceback", out)


class AtomicWriteTests(unittest.TestCase):
    def test_write_creates_and_replaces_content(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "data.json"
            atomic_write_text(target, "one")
            self.assertEqual(target.read_text(encoding="utf-8"), "one")
            atomic_write_text(target, "two")
            self.assertEqual(target.read_text(encoding="utf-8"), "two")
            self.assertEqual(list(Path(d).glob("*.tmp")), [])

    def test_failed_replace_keeps_original_and_no_temp(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "data.json"
            target.write_text("keep", encoding="utf-8")
            with mock.patch.object(state_mod.os, "replace", side_effect=OSError("boom")):
                with self.assertRaises(OSError):
                    atomic_write_text(target, "lost")
            self.assertEqual(target.read_text(encoding="utf-8"), "keep")
            self.assertEqual(list(Path(d).glob("*.tmp")), [])

    def test_save_state_and_inventory_leave_no_temp_files(self):
        with tempfile.TemporaryDirectory() as d:
            _init(d)
            artifact = Path(d) / "PRD.md"
            artifact.write_text("# PRD\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["artifact", "add", str(artifact), "--dir", d], clock=clock)
            leftovers = list(state_dir(Path(d)).glob("*.tmp"))
            self.assertEqual(leftovers, [])
            # Both files are valid JSON after the atomic writes.
            json.loads(state_path(Path(d)).read_text(encoding="utf-8"))
            json.loads((state_dir(Path(d)) / "artifacts.json").read_text(encoding="utf-8"))


class ValidStateUnchangedTests(unittest.TestCase):
    def test_valid_state_still_works(self):
        with tempfile.TemporaryDirectory() as d:
            _init(d)
            rc, out = _run(["status", "--dir", d])
            self.assertEqual(rc, 0)
            self.assertIn("Current phase: idea", out)


if __name__ == "__main__":
    unittest.main()
