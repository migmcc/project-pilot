import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from projectpilot import artifact_store
from projectpilot.cli import main
from projectpilot.config import config_path
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


def configure_graphify(base: Path, *, ready: bool) -> None:
    path = config_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("graphify_enabled: true\n", encoding="utf-8")
    if ready:
        out = base / "graphify-out"
        out.mkdir()
        (out / "graph.json").write_text("{}\n", encoding="utf-8")
        (out / "GRAPH_REPORT.md").write_text("# Report\n", encoding="utf-8")


class DashboardCliFixture(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = main(argv)
        return rc, out.getvalue()


class DashboardTextTests(DashboardCliFixture):
    def test_enabled_graphify_context_renders_status_and_budget(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            configure_graphify(base, ready=True)
            rc, text = self._run(["dashboard", "--dir", d])
            self.assertEqual(rc, 0)
            context = (
                "Knowledge context\n\n"
                "Provider: Graphify\n"
                "Status: Ready\n"
                "Query budget: 1200 tokens"
            )
            self.assertIn(f"Ready to progress:\nNo\n\n{context}", text)
            self.assertIn(f"{context}\n\nTop recommendation", text)

    def test_enabled_graphify_context_precedes_uninitialized_recommendation(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            configure_graphify(base, ready=False)
            rc, text = self._run(["dashboard", "--dir", d])
            self.assertEqual(rc, 0)
            context = (
                "Knowledge context\n\n"
                "Provider: Graphify\n"
                "Status: Missing\n"
                "Query budget: 1200 tokens"
            )
            self.assertIn(
                "ProjectPilot is not initialized in this directory.\n\n"
                f"{context}\n\nTop recommendation",
                text,
            )

    def test_graphify_context_lines_are_independent_of_verbose_mode(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            configure_graphify(base, ready=True)
            _, plain = self._run(["dashboard", "--dir", d])
            _, verbose = self._run(["dashboard", "--verbose", "--dir", d])
            expected = [
                "Knowledge context",
                "",
                "Provider: Graphify",
                "Status: Ready",
                "Query budget: 1200 tokens",
            ]
            for label, text in (("plain", plain), ("verbose", verbose)):
                with self.subTest(mode=label):
                    lines = text.splitlines()
                    start = lines.index("Knowledge context")
                    self.assertEqual(lines[start : start + len(expected)], expected)

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
    def test_enabled_graphify_context_is_present_in_json(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            configure_graphify(base, ready=False)
            rc, text = self._run(["dashboard", "--json", "--dir", d])
            self.assertEqual(rc, 0)
            payload = json.loads(text)
            self.assertEqual(payload["context"]["provider"], "graphify")
            self.assertEqual(payload["context"]["status"], "missing")

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
