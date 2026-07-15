import tempfile
import unittest
from pathlib import Path

from projectpilot import prompt_builder
from projectpilot import artifact_store
from projectpilot import graph_context
from projectpilot.phases import Phase
from projectpilot.state import ProjectState, save_state


def make_state(**overrides):
    base = dict(
        name="Demo Project",
        slug="demo-project",
        idea="Build a thing",
        created_at="2026-06-30T00:00:00Z",
        updated_at="2026-06-30T00:00:00Z",
        current_phase=Phase.PLANNING,
    )
    base.update(overrides)
    return ProjectState(**base)


def build(context, **over):
    kwargs = dict(
        skill_id="create-prd",
        skill_name="create-prd",
        skill_description="Write a PRD.",
        skill_body="# PRD\n\nDo the thing.",
    )
    kwargs.update(over)
    return prompt_builder.build_prompt(context, **kwargs)


class BuildPromptTests(unittest.TestCase):
    def test_headers_and_sections_present(self):
        ctx = prompt_builder.PromptContext(
            project_name="Demo Project",
            phase_value="planning",
            phase_label="Planning",
            objective="Build a thing",
        )
        doc = build(ctx)
        self.assertIn("Project: Demo Project", doc)
        self.assertIn("Current phase:\nPlanning", doc)
        self.assertIn("Selected skill:\ncreate-prd", doc)
        self.assertIn("Project context", doc)
        self.assertIn("Objective:", doc)
        self.assertIn("Skill", doc)
        self.assertIn("Do the thing.", doc)
        self.assertIn("Instructions", doc)
        self.assertIn("does not call any model", doc)

    def test_empty_sections_are_omitted(self):
        ctx = prompt_builder.PromptContext(
            project_name=None,
            phase_value="idea",
            phase_label="Idea",
            objective=None,
        )
        doc = build(ctx)
        self.assertNotIn("Project:", doc)
        self.assertNotIn("Project context", doc)  # nothing grounded to show
        self.assertNotIn("Recent handoffs", doc)
        self.assertNotIn("Notes:", doc)
        # Skill + Instructions always present
        self.assertIn("Skill", doc)
        self.assertIn("Instructions", doc)

    def test_handoffs_notes_files_render_when_present(self):
        ctx = prompt_builder.PromptContext(
            project_name="P",
            phase_label="Planning",
            objective="obj",
            handoffs=["t1 validated (phase: validation)"],
            notes=["Decision APPROVED: good fit"],
            produced_files=[".project-pilot/status.json", "PROJECT_BRIEF.md"],
        )
        doc = build(ctx)
        self.assertIn("Recent handoffs:", doc)
        self.assertIn("- t1 validated (phase: validation)", doc)
        self.assertIn("Notes:", doc)
        self.assertIn("- Decision APPROVED: good fit", doc)
        self.assertIn("Files produced by ProjectPilot:", doc)
        self.assertIn("- PROJECT_BRIEF.md", doc)

    def test_deterministic(self):
        ctx = prompt_builder.PromptContext(project_name="P", phase_label="Planning", objective="o")
        self.assertEqual(build(ctx), build(ctx))

    def test_missing_skill_body_has_placeholder(self):
        ctx = prompt_builder.PromptContext(phase_label="Idea")
        doc = build(ctx, skill_body="")
        self.assertIn("(skill body unavailable)", doc)

    def test_ready_graphify_context_renders_in_planning(self):
        status = graph_context.GraphContextStatus(
            enabled=True,
            state=graph_context.STATE_READY,
            graph_path="graphify-out/graph.json",
            report_path="graphify-out/GRAPH_REPORT.md",
            query_budget=1200,
        )
        ctx = prompt_builder.PromptContext(
            phase_value="planning",
            phase_label="Planning",
            graph_context_status=status,
        )
        doc = build(ctx, skill_name="Create PRD")
        self.assertIn("Context retrieval", doc)
        self.assertIn(
            'graphify query "What project context is relevant to Create PRD?" --budget 1200',
            doc,
        )

    def test_graphify_context_is_omitted_when_not_ready_or_outside_active_phase(self):
        partial = graph_context.GraphContextStatus(
            enabled=True,
            state=graph_context.STATE_PARTIAL,
            graph_path="graphify-out/graph.json",
            report_path="graphify-out/GRAPH_REPORT.md",
            query_budget=1200,
        )
        ready = graph_context.GraphContextStatus(
            enabled=True,
            state=graph_context.STATE_READY,
            graph_path="graphify-out/graph.json",
            report_path="graphify-out/GRAPH_REPORT.md",
            query_budget=1200,
        )
        partial_doc = build(
            prompt_builder.PromptContext(
                phase_value="planning",
                phase_label="Planning",
                graph_context_status=partial,
            )
        )
        idea_doc = build(
            prompt_builder.PromptContext(
                phase_value="idea",
                phase_label="Idea",
                graph_context_status=ready,
            )
        )
        self.assertNotIn("Context retrieval", partial_doc)
        self.assertNotIn("Context retrieval", idea_doc)

    def test_unconfigured_context_keeps_prompt_without_graphify_section(self):
        ctx = prompt_builder.PromptContext(
            phase_value="planning",
            phase_label="Planning",
        )
        self.assertNotIn("Context retrieval", build(ctx))


class CollectContextTests(unittest.TestCase):
    def test_collects_grounded_fields(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            state = make_state(
                decision={"decision": "APPROVED", "reason": "clear scope"},
                history=[
                    {"event": "initialized", "phase": "idea", "timestamp": "t0"},
                    {"event": "validated", "phase": "validation", "timestamp": "t1"},
                ],
            )
            save_state(base, state)  # produces .project-pilot/status.json
            ctx = prompt_builder.collect_context(state, base)
            self.assertEqual(ctx.project_name, "Demo Project")
            self.assertEqual(ctx.phase_label, "Planning")
            self.assertEqual(ctx.objective, "Build a thing")
            self.assertTrue(ctx.current_state)  # phase next-action hint
            self.assertEqual(len(ctx.handoffs), 2)
            self.assertIn("Decision APPROVED: clear scope", ctx.notes)
            self.assertIn(".project-pilot/status.json", ctx.produced_files)

    def test_omits_absent_data(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            state = make_state(current_phase=Phase.IDEA)
            ctx = prompt_builder.collect_context(state, base)
            self.assertEqual(ctx.handoffs, [])
            self.assertEqual(ctx.notes, [])
            self.assertEqual(ctx.produced_files, [])  # nothing written to disk

    def test_handoffs_capped_to_last_five(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            history = [{"event": f"e{i}", "phase": "idea", "timestamp": f"t{i}"} for i in range(8)]
            state = make_state(history=history)
            ctx = prompt_builder.collect_context(state, base)
            self.assertEqual(len(ctx.handoffs), 5)
            self.assertIn("e7", ctx.handoffs[-1])  # most recent kept

    def test_lists_output_files(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            out = base / "projectpilot_outputs" / "skills"
            out.mkdir(parents=True)
            (out / "create-prd.md").write_text("x", encoding="utf-8")
            state = make_state()
            ctx = prompt_builder.collect_context(state, base)
            self.assertIn("projectpilot_outputs/skills/create-prd.md", ctx.produced_files)

    def test_lists_registered_artifact_metadata_without_reading_content(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            artifact = base / "docs" / "PRD.md"
            artifact.parent.mkdir()
            artifact.write_text("SECRET CONTENT", encoding="utf-8")
            artifact_store.add_artifact(
                base,
                artifact,
                "planning",
                clock=lambda: "2026-07-01T12:00:00Z",
            )

            ctx = prompt_builder.collect_context(make_state(), base)
            doc = build(ctx)

            self.assertIn("Registered artifacts:", doc)
            self.assertIn("- docs-prd-md | docs/PRD.md | md | planning | registered", doc)
            self.assertNotIn("SECRET CONTENT", doc)

    def test_collects_ready_graphify_status_without_reading_graph_contents(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            config_dir = base / ".project-pilot"
            config_dir.mkdir()
            (config_dir / "config.yaml").write_text(
                "graphify_enabled: true\n",
                encoding="utf-8",
            )
            out = base / "graphify-out"
            out.mkdir()
            (out / "graph.json").write_text("SECRET GRAPH\n", encoding="utf-8")
            (out / "GRAPH_REPORT.md").write_text("SECRET REPORT\n", encoding="utf-8")
            ctx = prompt_builder.collect_context(make_state(), base)
            self.assertEqual(ctx.graph_context_status.state, graph_context.STATE_READY)
            doc = build(ctx)
            self.assertNotIn("SECRET GRAPH", doc)
            self.assertNotIn("SECRET REPORT", doc)


if __name__ == "__main__":
    unittest.main()
