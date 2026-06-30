import tempfile
import unittest
from pathlib import Path

from projectpilot import recommend
from projectpilot.phases import Phase
from projectpilot.skills import Skill


def make_skill(skill_id, name="", description="", source="/lib", path=None):
    src = Path(source)
    return Skill(
        skill_id=skill_id,
        name=name or skill_id,
        description=description,
        path=Path(path) if path else src / skill_id / "SKILL.md",
        source=src,
        kind="manifest",
    )


class RankAlgorithmTests(unittest.TestCase):
    def test_only_positive_scores_returned(self):
        skills = [
            make_skill("create-prd", description="Write a PRD."),
            make_skill("unrelated", description="Nothing to see."),
        ]
        ranked = recommend.rank(skills, ["prd"])
        self.assertEqual([r.skill.skill_id for r in ranked], ["create-prd"])

    def test_ordering_by_score_then_id(self):
        skills = [
            make_skill("roadmap", description="plan a roadmap"),      # name+desc
            make_skill("risk-analysis", description="risk planning"),  # name+desc
            make_skill("plan-notes", description="a plan"),            # name+desc
        ]
        # keywords chosen so scores differ and one tie is broken by id
        ranked = recommend.rank(skills, ["roadmap", "risk", "plan"])
        ids = [r.skill.skill_id for r in ranked]
        scores = [r.score for r in ranked]
        # scores must be non-increasing
        self.assertEqual(scores, sorted(scores, reverse=True))
        # within equal scores, ids must be ascending
        for i in range(len(ranked) - 1):
            if scores[i] == scores[i + 1]:
                self.assertLess(ids[i], ids[i + 1])

    def test_tie_break_is_alphabetical(self):
        skills = [
            make_skill("zebra", description="roadmap"),
            make_skill("alpha", description="roadmap"),
        ]
        ranked = recommend.rank(skills, ["roadmap"])
        self.assertEqual([r.skill.skill_id for r in ranked], ["alpha", "zebra"])

    def test_id_match_outranks_description_match(self):
        id_match = make_skill("roadmap-builder", description="something")
        desc_match = make_skill("aaa", description="a roadmap helper")
        ranked = recommend.rank([desc_match, id_match], ["roadmap"])
        self.assertEqual(ranked[0].skill.skill_id, "roadmap-builder")
        self.assertGreater(ranked[0].score, ranked[1].score)

    def test_category_contributes_to_score(self):
        skill = make_skill(
            "thing",
            description="nothing relevant",
            source="/lib",
            path="/lib/pm-execution/skills/thing/SKILL.md",
        )
        ranked = recommend.rank([skill], ["execution"])
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].score, recommend._WEIGHT_CATEGORY)

    def test_stars_buckets(self):
        self.assertEqual(recommend._stars(1), 1)
        self.assertEqual(recommend._stars(2), 2)
        self.assertEqual(recommend._stars(3), 3)
        self.assertEqual(recommend._stars(5), 4)
        self.assertEqual(recommend._stars(6), 5)

    def test_stars_string_unicode_and_ascii(self):
        self.assertEqual(recommend.stars_string(3), "★★★☆☆")
        self.assertEqual(recommend.stars_string(3, filled="*", empty="."), "***..")

    def test_determinism_same_input_same_output(self):
        skills = [make_skill(f"s{i}", description="roadmap plan") for i in range(20)]
        first = [(r.skill.skill_id, r.score, r.stars) for r in recommend.rank(skills, ["plan"])]
        second = [(r.skill.skill_id, r.score, r.stars) for r in recommend.rank(skills, ["plan"])]
        self.assertEqual(first, second)

    def test_empty_keywords_yield_no_recommendations(self):
        skills = [make_skill("create-prd", description="prd")]
        self.assertEqual(recommend.rank(skills, []), [])


class RuleLoadingTests(unittest.TestCase):
    def _write_config(self, base, body):
        from projectpilot.config import config_path

        path = config_path(base)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    def test_defaults_present_for_every_phase(self):
        with tempfile.TemporaryDirectory() as d:
            rules = recommend.load_rules(Path(d))
            for phase in Phase:
                self.assertIn(phase, rules)
                self.assertTrue(rules[phase])

    def test_config_override_replaces_phase_terms(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            self._write_config(base, "recommend_planning:\n  - widget\n  - gadget\n")
            rules = recommend.load_rules(base)
            self.assertEqual(rules[Phase.PLANNING], ["widget", "gadget"])
            # other phases keep their defaults
            self.assertEqual(rules[Phase.EXECUTION], recommend.DEFAULT_RULES[Phase.EXECUTION])

    def test_keywords_for_phase_uses_override(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            self._write_config(base, "recommend_done:\n  - party\n")
            self.assertEqual(recommend.keywords_for_phase(base, Phase.DONE), ["party"])


if __name__ == "__main__":
    unittest.main()
