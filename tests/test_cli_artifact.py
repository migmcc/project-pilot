import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main
from projectpilot.phases import Phase
from projectpilot.state import ProjectState, save_state

FROZEN = "2026-07-01T12:00:00Z"


def frozen_clock():
    return FROZEN


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


class ArtifactCliTests(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = main(argv, clock=frozen_clock)
        return rc, out.getvalue()

    def test_add_prints_registered_id_and_persists_inventory(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            artifact = base / "docs" / "PRD.md"
            artifact.parent.mkdir()
            artifact.write_text("content", encoding="utf-8")

            rc, text = self._run(["artifact", "add", str(artifact), "--dir", d])

            self.assertEqual(rc, 0)
            self.assertIn("Registered artifact: docs-prd-md", text)
            self.assertTrue((base / ".project-pilot" / "artifacts.json").is_file())

    def test_add_missing_file_returns_failure(self):
        with tempfile.TemporaryDirectory() as d:
            seed_state(Path(d))

            rc, text = self._run(["artifact", "add", str(Path(d) / "missing.md"), "--dir", d])

            self.assertEqual(rc, 1)
            self.assertIn("Artifact file does not exist", text)

    def test_list_text_is_stably_ordered(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            (base / "z.md").write_text("z", encoding="utf-8")
            (base / "a.md").write_text("a", encoding="utf-8")
            self._run(["artifact", "add", "z.md", "--dir", d])
            self._run(["artifact", "add", "a.md", "--dir", d])

            rc, text = self._run(["artifact", "list", "--dir", d])

            self.assertEqual(rc, 0)
            self.assertLess(text.index("a-md"), text.index("z-md"))
            self.assertIn("registered", text)

    def test_list_json_emits_deterministic_json(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            (base / "PRD.md").write_text("content", encoding="utf-8")
            self._run(["artifact", "add", "PRD.md", "--dir", d])

            rc, first = self._run(["artifact", "list", "--json", "--dir", d])
            _, second = self._run(["artifact", "list", "--json", "--dir", d])

            self.assertEqual(rc, 0)
            self.assertEqual(first, second)
            payload = json.loads(first)
            self.assertEqual(payload["artifacts"][0]["id"], "prd-md")

    def test_show_outputs_full_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            (base / "PRD.md").write_text("content", encoding="utf-8")
            self._run(["artifact", "add", "PRD.md", "--dir", d])

            rc, text = self._run(["artifact", "show", "prd-md", "--dir", d])

            self.assertEqual(rc, 0)
            self.assertIn("id: prd-md", text)
            self.assertIn("sha256:", text)

    def test_remove_does_not_delete_original_file(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            artifact = base / "PRD.md"
            artifact.write_text("content", encoding="utf-8")
            self._run(["artifact", "add", "PRD.md", "--dir", d])

            rc, text = self._run(["artifact", "remove", "prd-md", "--dir", d])

            self.assertEqual(rc, 0)
            self.assertIn("Removed artifact: prd-md", text)
            self.assertTrue(artifact.is_file())


if __name__ == "__main__":
    unittest.main()
