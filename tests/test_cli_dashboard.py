import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from projectpilot import artifact_store
from projectpilot.cli import main
from projectpilot.phases import Phase
from projectpilot.state import ProjectState, save_state


def seed_state(base: Path, phase=Phase.PLANNING, name="Demo"):
    save_state(
        base,
        ProjectState(
            name=name,
            slug="demo",
            idea="build a thing",
            created_at="2026-06-30T00:00:00Z",
            updated_at="2026-06-30T00:00:00Z",
            current_phase=phase,
        ),
    )


def register(base: Path, rel: str, phase="planning"):
    path = base / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("content", encoding="utf-8")
    artifact_store.add_artifact(base, path, phase, clock=lambda: "2026-07-01T00:00:00Z")


class DashboardCliFixture(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = main(argv)
        return rc, out.getvalue()


class DashboardTextTests(DashboardCliFixture):
    def test_uninitialized(self):
        with tempfile.TemporaryDirectory() as d:
            rc, text = self._run(["dashboard", "--dir", d])
            self.assertEqual(rc, 0)
            self.assertIn("Project Health", text)
            self.assertIn("not initialized", text)
            self.assertIn('pp init', text)

    def test_initialized_sections(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base, name="Demo Project")
            register(base, "PRD.md")
            rc, text = self._run(["dashboard", "--dir", d])
            self.assertEqual(rc, 0)
            self.assertIn("Project Health: Demo Project", text)
            self.assertIn("Phase: Planning", text)
            self.assertIn("50%", text)
            self.assertIn("Ready to progress:", text)
            self.assertIn("Top recommendation", text)
            self.assertIn("Artifacts (1)", text)
            self.assertIn("PRD.md", text)
            self.assertIn("Recommended skills", text)

    def test_verbose_adds_requirements_and_reasoning(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            register(base, "PRD.md")
            _, plain = self._run(["dashboard", "--dir", d])
            _, verbose = self._run(["dashboard", "--verbose", "--dir", d])
            self.assertNotIn("Completed requirements:", plain)
            self.assertIn("Completed requirements:", verbose)
            self.assertIn("Missing requirements:", verbose)
            self.assertIn("Reason:", verbose)

    def test_verbose_artifact_metadata_no_content(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            path = base / "PRD.md"
            path.write_text("SECRET CONTENT", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                main(["artifact", "add", "PRD.md", "--dir", d])
            _, text = self._run(["dashboard", "--verbose", "--dir", d])
            self.assertIn("PRD.md  [md | planning | registered]", text)
            self.assertNotIn("SECRET CONTENT", text)


class DashboardJsonTests(DashboardCliFixture):
    def test_json_shape(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            register(base, "PRD.md")
            rc, text = self._run(["dashboard", "--json", "--dir", d])
            self.assertEqual(rc, 0)
            payload = json.loads(text)
            self.assertEqual(
                list(payload.keys()), ["project", "phase", "workflow", "artifacts", "skills"]
            )
            self.assertEqual(payload["project"]["phase"], "planning")
            self.assertEqual(payload["phase"]["completion"], 50)
            self.assertEqual(payload["artifacts"]["total"], 1)

    def test_json_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            register(base, "PRD.md")
            _, a = self._run(["dashboard", "--json", "--dir", d])
            _, b = self._run(["dashboard", "--json", "--dir", d])
            self.assertEqual(a, b)

    def test_json_verbose_has_extra_fields(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            register(base, "PRD.md")
            _, text = self._run(["dashboard", "--json", "--verbose", "--dir", d])
            payload = json.loads(text)
            self.assertIn("completed", payload["phase"])
            self.assertIn("metadata", payload["artifacts"])


if __name__ == "__main__":
    unittest.main()
