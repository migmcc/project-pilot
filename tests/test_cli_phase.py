import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main
from projectpilot.phases import Phase
from projectpilot.state import ProjectState, save_state


def seed_state(base: Path, phase=Phase.PLANNING):
    save_state(
        base,
        ProjectState(
            name="Demo",
            slug="demo",
            idea="build a thing",
            created_at="2026-06-30T00:00:00Z",
            updated_at="2026-06-30T00:00:00Z",
            current_phase=phase,
        ),
    )


def add_artifact(base: Path, rel: str):
    path = base / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        main(["artifact", "add", rel, "--dir", str(base)])


class PhaseCheckFixture(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = main(argv)
        return rc, out.getvalue()


class PhaseCheckTextTests(PhaseCheckFixture):
    def test_no_state(self):
        with tempfile.TemporaryDirectory() as d:
            rc, text = self._run(["phase", "check", "--dir", d])
            self.assertEqual(rc, 1)
            self.assertIn("No ProjectPilot state", text)

    def test_text_structure_no_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            seed_state(Path(d))
            rc, text = self._run(["phase", "check", "--dir", d])
            self.assertEqual(rc, 0)
            self.assertIn("Current phase: Planning", text)
            self.assertIn("Requirements", text)
            self.assertIn("PRD", text)
            self.assertIn("Roadmap", text)
            self.assertIn("Completion", text)
            self.assertIn("0%", text)
            self.assertIn("Ready to progress", text)
            self.assertIn("No", text)

    def test_verbose_lists_optional(self):
        with tempfile.TemporaryDirectory() as d:
            seed_state(Path(d))
            _, plain = self._run(["phase", "check", "--dir", d])
            _, verbose = self._run(["phase", "check", "--verbose", "--dir", d])
            self.assertNotIn("Optional", plain)
            self.assertIn("Optional", verbose)
            self.assertIn("Risk Analysis", verbose)

    def test_full_completion_ready_yes(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            add_artifact(base, "docs/PRD.md")
            add_artifact(base, "docs/roadmap.md")
            rc, text = self._run(["phase", "check", "--dir", d])
            self.assertEqual(rc, 0)
            self.assertIn("100%", text)
            self.assertIn("Ready to progress\n\nYes", text)


class PhaseCheckJsonTests(PhaseCheckFixture):
    def test_json_shape(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            add_artifact(base, "docs/PRD.md")
            rc, text = self._run(["phase", "check", "--json", "--dir", d])
            self.assertEqual(rc, 0)
            payload = json.loads(text)
            self.assertEqual(payload["phase"], "planning")
            self.assertEqual(payload["completion"], 50)
            self.assertFalse(payload["ready_to_progress"])
            self.assertEqual(payload["completed"], ["prd"])
            self.assertEqual(payload["missing"], ["roadmap"])

    def test_json_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            seed_state(Path(d))
            _, a = self._run(["phase", "check", "--json", "--dir", d])
            _, b = self._run(["phase", "check", "--json", "--dir", d])
            self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
