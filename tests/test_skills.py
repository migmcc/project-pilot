import tempfile
import unittest
from pathlib import Path

from projectpilot import skills
from projectpilot.config import (
    EXTERNAL_SKILL_PATHS_KEY,
    config_path,
    load_config,
    parse_config,
)


def write_config(base: Path, body: str) -> None:
    path = config_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def make_manifest_skill(root: Path, name: str, frontmatter: str, body: str = "Body text.") -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8")


class ConfigParseTests(unittest.TestCase):
    def test_block_list(self):
        cfg = parse_config("external_skill_paths:\n  - ../pm-skills\n  - /abs/x\n")
        self.assertEqual(cfg.external_skill_paths, ["../pm-skills", "/abs/x"])

    def test_inline_list(self):
        cfg = parse_config("external_skill_paths: [../a, ../b]\n")
        self.assertEqual(cfg.external_skill_paths, ["../a", "../b"])

    def test_comments_and_quotes_ignored(self):
        text = "# top comment\nexternal_skill_paths:\n  - '../pm-skills'  # inline note\n"
        cfg = parse_config(text)
        self.assertEqual(cfg.external_skill_paths, ["../pm-skills"])

    def test_missing_key_yields_empty(self):
        cfg = parse_config("other_key: value\n")
        self.assertEqual(cfg.external_skill_paths, [])

    def test_empty_text_is_tolerant(self):
        self.assertEqual(parse_config("").external_skill_paths, [])

    def test_key_constant(self):
        self.assertEqual(EXTERNAL_SKILL_PATHS_KEY, "external_skill_paths")

    def test_load_config_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(load_config(Path(d)).external_skill_paths, [])

    def test_load_config_reads_file(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            write_config(base, "external_skill_paths:\n  - ../pm-skills\n")
            self.assertEqual(load_config(base).external_skill_paths, ["../pm-skills"])


class ResolveSourcesTests(unittest.TestCase):
    def test_relative_resolved_against_base_and_existence_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            (Path(d) / "pm-skills").mkdir()
            write_config(base, "external_skill_paths:\n  - ../pm-skills\n  - ../nope\n")
            sources = skills.resolve_sources(base)
            self.assertEqual([s.raw for s in sources], ["../pm-skills", "../nope"])
            self.assertTrue(sources[0].exists)
            self.assertFalse(sources[1].exists)
            self.assertEqual(sources[0].path, (Path(d) / "pm-skills").resolve())

    def test_no_config_yields_no_sources(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(skills.resolve_sources(Path(d)), [])


class ScanManifestTests(unittest.TestCase):
    def test_manifest_skill_uses_frontmatter(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            lib = Path(d) / "pm-skills"
            make_manifest_skill(
                lib,
                "discovery",
                "name: Discovery Kickoff\ndescription: Start a discovery phase.",
            )
            # A stray README must NOT become a skill when manifests exist.
            (lib / "README.md").write_text("# pm-skills\n", encoding="utf-8")
            write_config(base, "external_skill_paths:\n  - ../pm-skills\n")

            found = skills.scan_skills(base)
            self.assertEqual(len(found), 1)
            skill = found[0]
            self.assertEqual(skill.skill_id, "discovery")
            self.assertEqual(skill.name, "Discovery Kickoff")
            self.assertEqual(skill.description, "Start a discovery phase.")
            self.assertEqual(skill.kind, skills.KIND_MANIFEST)

    def test_hidden_dirs_pruned(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            lib = Path(d) / "pm-skills"
            make_manifest_skill(lib, "alpha", "name: Alpha\ndescription: A.")
            git_dir = lib / ".git"
            git_dir.mkdir(parents=True)
            (git_dir / "SKILL.md").write_text("---\nname: Ghost\n---\n", encoding="utf-8")
            write_config(base, "external_skill_paths:\n  - ../pm-skills\n")

            ids = [s.skill_id for s in skills.scan_skills(base)]
            self.assertEqual(ids, ["alpha"])

    def test_duplicate_ids_made_unique(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            lib_a = Path(d) / "lib-a"
            lib_b = Path(d) / "lib-b"
            make_manifest_skill(lib_a, "discovery", "name: A\ndescription: a.")
            make_manifest_skill(lib_b, "discovery", "name: B\ndescription: b.")
            write_config(
                base,
                "external_skill_paths:\n  - ../lib-a\n  - ../lib-b\n",
            )
            ids = [s.skill_id for s in skills.scan_skills(base)]
            self.assertEqual(ids, ["discovery", "discovery-2"])


class ScanFallbackTests(unittest.TestCase):
    def test_flat_markdown_without_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            lib = Path(d) / "notes"
            lib.mkdir()
            (lib / "estimating.md").write_text(
                "# Estimating Work\n\nHow to estimate effort.\n", encoding="utf-8"
            )
            write_config(base, "external_skill_paths:\n  - ../notes\n")

            found = skills.scan_skills(base)
            self.assertEqual(len(found), 1)
            skill = found[0]
            self.assertEqual(skill.skill_id, "estimating")
            self.assertEqual(skill.name, "Estimating Work")
            self.assertEqual(skill.description, "How to estimate effort.")
            self.assertEqual(skill.kind, skills.KIND_MARKDOWN)

    def test_filename_fallback_when_no_heading(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            lib = Path(d) / "notes"
            lib.mkdir()
            (lib / "raw_notes.md").write_text("just text, no heading\n", encoding="utf-8")
            write_config(base, "external_skill_paths:\n  - ../notes\n")

            skill = skills.scan_skills(base)[0]
            self.assertEqual(skill.skill_id, "raw-notes")
            self.assertEqual(skill.name, "Raw Notes")
            self.assertEqual(skill.description, "just text, no heading")


class FrontmatterToleranceTests(unittest.TestCase):
    def test_block_scalar_folded_description(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            lib = Path(d) / "lib"
            skill_dir = lib / "folded"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: Folded Skill\n"
                "description: >\n"
                "  First line of a folded\n"
                "  description that wraps.\n"
                "---\n\n"
                "# Body\n",
                encoding="utf-8",
            )
            write_config(base, "external_skill_paths:\n  - ../lib\n")
            skill = skills.find_skill(base, "folded")
            self.assertEqual(skill.name, "Folded Skill")
            self.assertEqual(
                skill.description, "First line of a folded description that wraps."
            )
            self.assertEqual(skill.kind, skills.KIND_MANIFEST)

    def test_block_scalar_literal_description(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            lib = Path(d) / "lib"
            skill_dir = lib / "literal"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: Literal Skill\n"
                "description: |\n"
                "  line one\n"
                "  line two\n"
                "---\n\n"
                "Body.\n",
                encoding="utf-8",
            )
            write_config(base, "external_skill_paths:\n  - ../lib\n")
            skill = skills.find_skill(base, "literal")
            self.assertEqual(skill.description, "line one\nline two")

    def test_unterminated_frontmatter_is_treated_as_body(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            lib = Path(d) / "lib"
            lib.mkdir()
            (lib / "weird.md").write_text(
                "---\nname: Never Closed\n\n# Real Heading\n", encoding="utf-8"
            )
            write_config(base, "external_skill_paths:\n  - ../lib\n")
            skill = skills.find_skill(base, "weird")
            # No closing ---, so the heading (not the pseudo-frontmatter) wins.
            self.assertEqual(skill.name, "Real Heading")
            self.assertEqual(skill.kind, skills.KIND_MARKDOWN)


class FindAndRenderTests(unittest.TestCase):
    def _project_with_skill(self, d):
        base = Path(d) / "project"
        base.mkdir()
        lib = Path(d) / "pm-skills"
        make_manifest_skill(
            lib,
            "discovery",
            "name: Discovery\ndescription: Kick off discovery.",
            body="## Steps\n\n1. Ask questions.\n",
        )
        write_config(base, "external_skill_paths:\n  - ../pm-skills\n")
        return base

    def test_find_skill_case_insensitive(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project_with_skill(d)
            self.assertIsNotNone(skills.find_skill(base, "DISCOVERY"))
            self.assertIsNone(skills.find_skill(base, "missing"))

    def test_render_strips_frontmatter_and_adds_header(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project_with_skill(d)
            skill = skills.find_skill(base, "discovery")
            rendered = skills.render_skill(skill)
            self.assertIn("# Skill: Discovery", rendered)
            self.assertIn("- Id: discovery", rendered)
            self.assertIn("No LLM was called", rendered)
            self.assertIn("## Steps", rendered)
            # Frontmatter delimiters from the source must not leak into the body.
            self.assertNotIn("name: Discovery\ndescription", rendered)


if __name__ == "__main__":
    unittest.main()
