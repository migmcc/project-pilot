import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from projectpilot import advisor, artifact_store, prompt_builder
from projectpilot.phases import Phase
from projectpilot.state import ProjectState, load_state, save_state


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
    return base


def register(base: Path, rel: str, phase="planning"):
    path = base / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("content", encoding="utf-8")
    artifact_store.add_artifact(base, path, phase, clock=lambda: "2026-07-01T00:00:00Z")


def actions(advice):
    return [r.action for r in advice.recommendations]


class AdvisorIntegrationTests(unittest.TestCase):
    def test_missing_required_artifacts_are_recommended(self):
        with tempfile.TemporaryDirectory() as d:
            base = seed_state(Path(d))
            advice = advisor.advise(base)
            self.assertIn("Produce the required 'PRD' artifact", actions(advice))
            self.assertIn("Produce the required 'Roadmap' artifact", actions(advice))

    def test_registered_artifact_removes_its_requirement_recommendation(self):
        with tempfile.TemporaryDirectory() as d:
            base = seed_state(Path(d))
            register(base, "docs/PRD.md")
            advice = advisor.advise(base)
            self.assertNotIn("Produce the required 'PRD' artifact", actions(advice))
            # Roadmap still missing, so it is still recommended.
            self.assertIn("Produce the required 'Roadmap' artifact", actions(advice))

    def test_full_completion_no_requirement_recommendations(self):
        with tempfile.TemporaryDirectory() as d:
            base = seed_state(Path(d))
            register(base, "docs/PRD.md")
            register(base, "docs/roadmap.md")
            advice = advisor.advise(base)
            self.assertFalse(
                [a for a in actions(advice) if a.startswith("Produce the required")]
            )

    def test_advisor_uses_engine_single_source_of_truth(self):
        # The advisor context carries the engine evaluation directly.
        with tempfile.TemporaryDirectory() as d:
            base = seed_state(Path(d))
            register(base, "docs/PRD.md")
            ctx = advisor._build_context(base, load_state(base))
            self.assertEqual(ctx.evaluation.completion, 50)


class PromptBuilderIntegrationTests(unittest.TestCase):
    def test_prompt_includes_completion_and_missing(self):
        with tempfile.TemporaryDirectory() as d:
            base = seed_state(Path(d))
            register(base, "docs/PRD.md")
            state = load_state(base)
            ctx = prompt_builder.collect_context(state, base)
            self.assertEqual(ctx.completion, 50)
            self.assertIn("Roadmap", ctx.missing_requirements)
            doc = prompt_builder.build_prompt(
                ctx,
                skill_id="create-prd",
                skill_name="create-prd",
                skill_description="Write a PRD.",
                skill_body="body",
            )
            self.assertIn("Phase completion:", doc)
            self.assertIn("50%", doc)
            self.assertIn("Missing requirements:", doc)
            self.assertIn("- Roadmap", doc)

    def test_manual_context_without_completion_omits_section(self):
        # A PromptContext built by hand (completion=None) must not show the block.
        ctx = prompt_builder.PromptContext(phase_label="Planning", objective="obj")
        doc = prompt_builder.build_prompt(
            ctx,
            skill_id="s",
            skill_name="s",
            skill_description="",
            skill_body="body",
        )
        self.assertNotIn("Phase completion:", doc)


if __name__ == "__main__":
    unittest.main()
