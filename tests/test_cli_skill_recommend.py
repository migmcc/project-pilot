import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main
from projectpilot.config import config_path


def write_config(base: Path, body: str) -> None:
    path = config_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def make_skill(root: Path, dirname: str, name: str, description: str) -> None:
    skill_dir = root / dirname
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f'---\nname: {name}\ndescription: "{description}"\n---\n\nBody.\n',
        encoding="utf-8",
    )


class RecommendCliFixture(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = main(argv)
        return rc, out.getvalue()

    def _init(self, base: Path):
        with contextlib.redirect_stdout(io.StringIO()):
            main(["init", "an idea", "--dir", str(base), "--name", "Demo"])


class RecommendBasicTests(RecommendCliFixture):
    def test_no_state(self):
        with tempfile.TemporaryDirectory() as d:
            rc, text = self._run(["skill", "recommend", "--dir", d])
            self.assertEqual(rc, 1)
            self.assertIn("No ProjectPilot state", text)

    def test_no_sources_configured(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            self._init(base)
            rc, text = self._run(["skill", "recommend", "--dir", d])
            self.assertEqual(rc, 0)
            self.assertIn("Current phase: Idea", text)
            self.assertIn("No external skill paths configured", text)

    def test_phase_with_no_matching_recommendations(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            lib = Path(d) / "lib"
            make_skill(lib, "create-prd", "create-prd", "Write a PRD.")
            self._init(base)
            # Override idea-phase rules with a term nothing matches.
            write_config(
                base,
                "external_skill_paths:\n  - ../lib\nrecommend_idea:\n  - zzznomatch\n",
            )
            rc, text = self._run(["skill", "recommend", "--dir", str(base)])
            self.assertEqual(rc, 0)
            self.assertIn("No skill recommendations for phase 'idea'", text)


class RecommendRankingTests(RecommendCliFixture):
    def _project(self, d, *libs):
        base = Path(d) / "project"
        base.mkdir()
        config_lines = ["external_skill_paths:"]
        for lib_name in libs:
            (Path(d) / lib_name).mkdir(exist_ok=True)
            config_lines.append(f"  - ../{lib_name}")
        self._init(base)
        write_config(base, "\n".join(config_lines) + "\n")
        return base

    def test_recommends_matching_skills_with_origin(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project(d, "lib")
            make_skill(Path(d) / "lib", "market-research", "market-research", "Do market research.")
            rc, text = self._run(["skill", "recommend", "--dir", str(base)])
            self.assertEqual(rc, 0)
            self.assertIn("Recommended skills", text)
            self.assertIn("market-research", text)
            self.assertIn("[lib]", text)  # origin/library shown
            self.assertIn("★", text)  # StringIO encodes unicode, so stars render

    def test_multiple_libraries_are_merged(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project(d, "lib-a", "lib-b")
            make_skill(Path(d) / "lib-a", "customer-interview", "customer-interview", "Interview users.")
            make_skill(Path(d) / "lib-b", "problem-validation", "problem-validation", "Validate the problem.")
            rc, text = self._run(["skill", "recommend", "--dir", str(base)])
            self.assertEqual(rc, 0)
            self.assertIn("customer-interview", text)
            self.assertIn("problem-validation", text)
            self.assertIn("[lib-a]", text)
            self.assertIn("[lib-b]", text)

    def test_stronger_match_ranked_first(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "project"
            base.mkdir()
            lib = Path(d) / "lib"
            # id/name match (strong) vs description-only match (weak)
            make_skill(lib, "research-plan", "research-plan", "unrelated text")
            make_skill(lib, "aaa-weak", "aaa-weak", "mentions research once")
            self._init(base)
            write_config(base, "external_skill_paths:\n  - ../lib\nrecommend_idea:\n  - research\n")
            rc, text = self._run(["skill", "recommend", "--dir", str(base)])
            self.assertEqual(rc, 0)
            self.assertLess(text.index("research-plan"), text.index("aaa-weak"))

    def test_limit_caps_results(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project(d, "lib")
            for i in range(5):
                make_skill(Path(d) / "lib", f"research-{i}", f"research-{i}", "research topic")
            rc, text = self._run(["skill", "recommend", "--limit", "2", "--dir", str(base)])
            self.assertEqual(rc, 0)
            shown = [ln for ln in text.splitlines() if ln.strip().startswith(("★", "*"))]
            self.assertEqual(len(shown), 2)

    def test_output_is_stable_across_runs(self):
        with tempfile.TemporaryDirectory() as d:
            base = self._project(d, "lib")
            for i in range(6):
                make_skill(Path(d) / "lib", f"research-{i}", f"research-{i}", "market research")
            rc1, text1 = self._run(["skill", "recommend", "--dir", str(base)])
            rc2, text2 = self._run(["skill", "recommend", "--dir", str(base)])
            self.assertEqual((rc1, rc2), (0, 0))
            self.assertEqual(text1, text2)


if __name__ == "__main__":
    unittest.main()
