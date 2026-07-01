import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from projectpilot import artifact_store

FROZEN = "2026-07-01T12:00:00Z"


def frozen_clock():
    return FROZEN


class ArtifactStoreTests(unittest.TestCase):
    def test_add_artifact_persists_metadata_without_copying_file(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            artifact = base / "docs" / "PRD.md"
            artifact.parent.mkdir()
            artifact.write_text("hello evidence", encoding="utf-8")

            record = artifact_store.add_artifact(base, artifact, "planning", clock=frozen_clock)

            self.assertEqual(record["id"], "docs-prd-md")
            self.assertEqual(record["path"], "docs/PRD.md")
            self.assertEqual(record["name"], "PRD.md")
            self.assertEqual(record["type"], "md")
            self.assertEqual(record["phase"], "planning")
            self.assertEqual(record["registered_at"], FROZEN)
            self.assertEqual(record["size"], len("hello evidence"))
            self.assertEqual(record["origin"], "manual")
            self.assertEqual(record["status"], "registered")
            self.assertTrue((base / ".project-pilot" / "artifacts.json").is_file())
            self.assertFalse((base / ".project-pilot" / "PRD.md").exists())

    def test_missing_file_fails_clearly(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(FileNotFoundError, "Artifact file does not exist"):
                artifact_store.add_artifact(Path(d), Path(d) / "missing.md", "planning")

    def test_duplicate_add_updates_existing_entry_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            artifact = base / "PRD.md"
            artifact.write_text("v1", encoding="utf-8")
            first = artifact_store.add_artifact(base, artifact, "brief", clock=frozen_clock)
            artifact.write_text("v2 changed", encoding="utf-8")
            second = artifact_store.add_artifact(base, artifact, "planning", clock=frozen_clock)

            records = artifact_store.list_artifacts(base)
            self.assertEqual(len(records), 1)
            self.assertEqual(first["id"], second["id"])
            self.assertEqual(records[0]["sha256"], hashlib.sha256(b"v2 changed").hexdigest())
            self.assertEqual(records[0]["phase"], "planning")

    def test_remove_artifact_removes_only_inventory_entry(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            artifact = base / "PRD.md"
            artifact.write_text("content", encoding="utf-8")
            record = artifact_store.add_artifact(base, artifact, "planning", clock=frozen_clock)

            removed = artifact_store.remove_artifact(base, record["id"])

            self.assertEqual(removed["path"], "PRD.md")
            self.assertEqual(artifact.read_text(encoding="utf-8"), "content")
            self.assertEqual(artifact_store.list_artifacts(base), [])

    def test_find_artifact_returns_one_record(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            artifact = base / "PRD.md"
            artifact.write_text("content", encoding="utf-8")
            record = artifact_store.add_artifact(base, artifact, "planning", clock=frozen_clock)

            self.assertEqual(artifact_store.find_artifact(base, record["id"]), record)
            self.assertIsNone(artifact_store.find_artifact(base, "missing"))

    def test_json_output_is_deterministic_and_ordered(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            zed = base / "z.md"
            alpha = base / "alpha.md"
            zed.write_text("z", encoding="utf-8")
            alpha.write_text("a", encoding="utf-8")
            artifact_store.add_artifact(base, zed, "planning", clock=frozen_clock)
            artifact_store.add_artifact(base, alpha, "planning", clock=frozen_clock)

            first = artifact_store.dumps_inventory(base)
            second = artifact_store.dumps_inventory(base)
            payload = json.loads(first)

            self.assertEqual(first, second)
            self.assertEqual([item["path"] for item in payload["artifacts"]], ["alpha.md", "z.md"])
            self.assertEqual(list(payload.keys()), ["artifacts"])
            self.assertTrue(first.endswith("\n"))

    def test_sha256_correctness(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "binary.bin"
            path.write_bytes(b"\x00abc\xff")
            self.assertEqual(
                artifact_store.sha256_file(path),
                hashlib.sha256(b"\x00abc\xff").hexdigest(),
            )

    def test_stable_ids_are_derived_from_relative_path(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            artifact = base / "Product Docs" / "PRD v1.md"
            artifact.parent.mkdir()
            artifact.write_text("content", encoding="utf-8")

            first = artifact_store.add_artifact(base, artifact, "planning", clock=frozen_clock)
            second = artifact_store.add_artifact(base, artifact, "execution", clock=frozen_clock)

            self.assertEqual(first["id"], "product-docs-prd-v1-md")
            self.assertEqual(second["id"], "product-docs-prd-v1-md")


if __name__ == "__main__":
    unittest.main()
