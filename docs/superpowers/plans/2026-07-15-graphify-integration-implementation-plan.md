# Graphify Context Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in, advisory-only Graphify context integration that steers agents toward small graph queries while preserving ProjectPilot's deterministic, zero-dependency, no-execution charter.

**Architecture:** A new pure `graph_context.py` module parses the three Graphify configuration keys, validates paths and budgets, detects output readiness, and renders a compact query directive. Existing prompt, advisor, dashboard, and doctor layers consume that public API; none imports Graphify, parses its graph, starts a process, or accesses the network.

**Tech Stack:** Python 3.12+, standard library only, `unittest`, existing tolerant YAML-subset configuration, deterministic text/JSON APIs.

## Global Constraints

- Preserve zero runtime dependencies; do not change `[project].dependencies = []`.
- Do not spawn a process, access a network, call an LLM, install a tool, or weaken `tests/test_no_automation.py`.
- Graphify remains optional and disabled by default; unconfigured projects retain byte-identical text and JSON.
- ProjectPilot detects only configuration, safe paths, regular output files, and `PATH` availability; it never parses `graph.json` or decides that a graph is fresh.
- The graph is retrieval guidance only. Source code, tests, and human approvals remain authoritative.
- Do not automatically write, rebuild, register, stage, commit, or delete any Graphify output.
- Keep JSON changes additive and preserve stable key order.
- Use `unittest`, not pytest. Run tests with `.venv\Scripts\python.exe -B -m unittest`.
- Update `CHANGELOG.md` `[Unreleased]` for the behavioural addition; do not change version `1.0.0` in this increment.
- Commit messages are single-line conventional commits in English with no attribution trailers.
- Every commit step below requires Miguel's explicit authorization for commits during implementation. Without that authorization, skip the commit command and do not stage files.

---

## File structure

### New files

- `src/projectpilot/graph_context.py` — configuration parsing, safe path resolution, readiness classification, and compact query-directive rendering.
- `tests/test_graph_context.py` — isolated unit tests for every public state and validation boundary.
- `docs/graphify-integration.md` — operator workflow, privacy boundary, freshness fallback, and A/B pilot protocol.

### Modified runtime files

- `src/projectpilot/prompt_builder.py:20-178` — collect graph context and render it only for planning, execution, and final-validation skill prompts.
- `src/projectpilot/advisor.py:25-459` — add a non-blocking Medium Graphify preparation/repair recommendation.
- `src/projectpilot/dashboard.py:20-137` — aggregate optional graph context and add an optional additive JSON block.
- `src/projectpilot/commands/dashboard_cmd.py:26-94` — render the optional Knowledge context text section.
- `src/projectpilot/commands/doctor_cmd.py:1-81` — report configuration, executable availability, outputs, budget, and diagnostics without running Graphify.

### Modified tests

- `tests/test_prompt_builder.py:1-168`
- `tests/test_advisor.py:1-339`
- `tests/test_dashboard.py:1-162`
- `tests/test_cli_dashboard.py:1-130`
- `tests/test_cli_doctor.py:1-100`

### Modified documentation

- `README.md:61-94` and `README.md:310-500`
- `docs/architecture.md:12-98`
- `docs/extending.md:7-88`
- `CHANGELOG.md:9-13`
- `docs/superpowers/specs/2026-07-15-graphify-integration-design.md` — already approved; include it in the documentation commit without altering the decision.
- `docs/superpowers/plans/2026-07-15-graphify-integration-implementation-plan.md` — this plan.

---

### Task 1: Pure Graphify context boundary

**Files:**
- Create: `tests/test_graph_context.py`
- Create: `src/projectpilot/graph_context.py`

**Interfaces:**
- Consumes: `projectpilot.config.load_mapping(base: Path) -> dict[str, object]`
- Produces: `GraphContextStatus`, `inspect_graph_context(base: Path) -> GraphContextStatus`, and `render_query_directive(status: GraphContextStatus, skill_name: str) -> str`
- Produces constants: `STATE_DISABLED`, `STATE_MISSING`, `STATE_PARTIAL`, `STATE_READY`, `DEFAULT_OUTPUT_DIR`, and `DEFAULT_QUERY_BUDGET`

- [ ] **Step 1: Write the failing core tests**

Create `tests/test_graph_context.py` with this complete content:

```python
import tempfile
import unittest
from pathlib import Path

from projectpilot import graph_context


def write_config(base: Path, text: str) -> None:
    config_dir = base / ".project-pilot"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(text, encoding="utf-8")


def write_outputs(base: Path, *, graph: bool, report: bool, output_dir="graphify-out") -> None:
    out = base / output_dir
    out.mkdir(parents=True, exist_ok=True)
    if graph:
        (out / "graph.json").write_text("{}\n", encoding="utf-8")
    if report:
        (out / "GRAPH_REPORT.md").write_text("# Report\n", encoding="utf-8")


class InspectGraphContextTests(unittest.TestCase):
    def test_unconfigured_is_disabled_with_stable_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            status = graph_context.inspect_graph_context(Path(d))
            self.assertFalse(status.enabled)
            self.assertEqual(status.state, graph_context.STATE_DISABLED)
            self.assertEqual(status.graph_path, "graphify-out/graph.json")
            self.assertEqual(status.report_path, "graphify-out/GRAPH_REPORT.md")
            self.assertEqual(status.query_budget, 1200)
            self.assertEqual(status.diagnostics, ())

    def test_enabled_states_are_missing_partial_and_ready(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            write_config(base, "graphify_enabled: true\n")
            self.assertEqual(
                graph_context.inspect_graph_context(base).state,
                graph_context.STATE_MISSING,
            )
            write_outputs(base, graph=True, report=False)
            self.assertEqual(
                graph_context.inspect_graph_context(base).state,
                graph_context.STATE_PARTIAL,
            )
            write_outputs(base, graph=True, report=True)
            self.assertEqual(
                graph_context.inspect_graph_context(base).state,
                graph_context.STATE_READY,
            )

    def test_custom_safe_output_and_budget_are_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            write_config(
                base,
                "graphify_enabled: yes\n"
                "graphify_output_dir: .context/graphify\n"
                "graphify_query_budget: 2500\n",
            )
            write_outputs(base, graph=True, report=True, output_dir=".context/graphify")
            status = graph_context.inspect_graph_context(base)
            self.assertTrue(status.enabled)
            self.assertEqual(status.state, graph_context.STATE_READY)
            self.assertEqual(status.graph_path, ".context/graphify/graph.json")
            self.assertEqual(status.report_path, ".context/graphify/GRAPH_REPORT.md")
            self.assertEqual(status.query_budget, 2500)

    def test_escape_and_invalid_values_fall_back_with_diagnostics(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            write_config(
                base,
                "graphify_enabled: perhaps\n"
                "graphify_output_dir: ../outside\n"
                "graphify_query_budget: many\n",
            )
            status = graph_context.inspect_graph_context(base)
            self.assertFalse(status.enabled)
            self.assertEqual(status.state, graph_context.STATE_DISABLED)
            self.assertEqual(status.graph_path, "graphify-out/graph.json")
            self.assertEqual(status.query_budget, 1200)
            self.assertEqual(
                status.diagnostics,
                (
                    "graphify_enabled is invalid; using false.",
                    "graphify_output_dir must stay inside the project; using graphify-out.",
                    "graphify_query_budget must be an integer from 250 through 5000; using 1200.",
                ),
            )

    def test_budget_boundaries_are_inclusive(self):
        for budget in (250, 5000):
            with self.subTest(budget=budget), tempfile.TemporaryDirectory() as d:
                base = Path(d)
                write_config(
                    base,
                    f"graphify_enabled: true\ngraphify_query_budget: {budget}\n",
                )
                self.assertEqual(
                    graph_context.inspect_graph_context(base).query_budget,
                    budget,
                )


class RenderQueryDirectiveTests(unittest.TestCase):
    def ready_status(self) -> graph_context.GraphContextStatus:
        return graph_context.GraphContextStatus(
            enabled=True,
            state=graph_context.STATE_READY,
            graph_path="graphify-out/graph.json",
            report_path="graphify-out/GRAPH_REPORT.md",
            query_budget=1200,
        )

    def test_non_ready_status_renders_nothing(self):
        status = self.ready_status()
        status = graph_context.GraphContextStatus(
            enabled=status.enabled,
            state=graph_context.STATE_PARTIAL,
            graph_path=status.graph_path,
            report_path=status.report_path,
            query_budget=status.query_budget,
        )
        self.assertEqual(graph_context.render_query_directive(status, "Create PRD"), "")

    def test_ready_status_renders_budgeted_safe_compact_query(self):
        status = self.ready_status()
        first = graph_context.render_query_directive(
            status,
            'Create "PRD"\nwith `evidence`',
        )
        second = graph_context.render_query_directive(
            status,
            'Create "PRD"\nwith `evidence`',
        )
        self.assertEqual(first, second)
        self.assertIn(
            'graphify query "What project context is relevant to Create \'PRD\' with \'evidence\'?" --budget 1200',
            first,
        )
        self.assertIn("Treat INFERRED or AMBIGUOUS edges as hypotheses.", first)
        self.assertLess(len(first.split()), 100)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new tests and verify the expected failure**

Run:

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_graph_context -v
```

Expected: FAIL with `ImportError: cannot import name 'graph_context' from 'projectpilot'` because the module does not exist.

- [ ] **Step 3: Implement the pure context module**

Create `src/projectpilot/graph_context.py` with this complete content:

```python
"""Optional Graphify context discovery and prompt guidance.

This module never imports or executes Graphify. It reads ProjectPilot's small
configuration mapping, classifies the presence of expected local output files,
and renders deterministic advice for an external agent.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import load_mapping

__all__ = [
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_QUERY_BUDGET",
    "STATE_DISABLED",
    "STATE_MISSING",
    "STATE_PARTIAL",
    "STATE_READY",
    "GraphContextStatus",
    "inspect_graph_context",
    "render_query_directive",
]

DEFAULT_OUTPUT_DIR = "graphify-out"
DEFAULT_QUERY_BUDGET = 1200
MIN_QUERY_BUDGET = 250
MAX_QUERY_BUDGET = 5000

STATE_DISABLED = "disabled"
STATE_MISSING = "missing"
STATE_PARTIAL = "partial"
STATE_READY = "ready"

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})
_MISSING = object()


@dataclass(frozen=True)
class GraphContextStatus:
    """Deterministic snapshot of the optional external Graphify context."""

    enabled: bool
    state: str
    graph_path: str
    report_path: str
    query_budget: int
    diagnostics: tuple[str, ...] = ()


def _enabled(value: object, diagnostics: list[str]) -> bool:
    if value is _MISSING:
        return False
    normalized = str(value).strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    diagnostics.append("graphify_enabled is invalid; using false.")
    return False


def _query_budget(value: object, diagnostics: list[str]) -> int:
    if value is _MISSING:
        return DEFAULT_QUERY_BUDGET
    try:
        budget = int(str(value).strip())
    except (TypeError, ValueError):
        budget = -1
    if MIN_QUERY_BUDGET <= budget <= MAX_QUERY_BUDGET:
        return budget
    diagnostics.append(
        "graphify_query_budget must be an integer from 250 through 5000; using 1200."
    )
    return DEFAULT_QUERY_BUDGET


def _output_directory(
    base: Path,
    value: object,
    diagnostics: list[str],
) -> tuple[Path, str]:
    root = Path(base).resolve()
    raw = DEFAULT_OUTPUT_DIR if value is _MISSING else value
    if not isinstance(raw, str) or not raw.strip():
        diagnostics.append(
            "graphify_output_dir must be a non-empty path; using graphify-out."
        )
        raw = DEFAULT_OUTPUT_DIR
    candidate = Path(raw.strip())
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        diagnostics.append(
            "graphify_output_dir must stay inside the project; using graphify-out."
        )
        resolved = (root / DEFAULT_OUTPUT_DIR).resolve()
        relative = Path(DEFAULT_OUTPUT_DIR)
    return resolved, relative.as_posix()


def inspect_graph_context(base: Path) -> GraphContextStatus:
    """Inspect Graphify configuration and expected outputs without executing it."""
    base = Path(base)
    mapping = load_mapping(base)
    diagnostics: list[str] = []
    enabled = _enabled(mapping.get("graphify_enabled", _MISSING), diagnostics)
    output_dir, relative_dir = _output_directory(
        base,
        mapping.get("graphify_output_dir", _MISSING),
        diagnostics,
    )
    budget = _query_budget(mapping.get("graphify_query_budget", _MISSING), diagnostics)

    graph_file = output_dir / "graph.json"
    report_file = output_dir / "GRAPH_REPORT.md"
    graph_exists = graph_file.is_file()
    report_exists = report_file.is_file()

    if not enabled:
        state = STATE_DISABLED
    elif graph_exists and report_exists:
        state = STATE_READY
    elif graph_exists or report_exists:
        state = STATE_PARTIAL
    else:
        state = STATE_MISSING

    relative_root = Path(relative_dir)
    return GraphContextStatus(
        enabled=enabled,
        state=state,
        graph_path=(relative_root / "graph.json").as_posix(),
        report_path=(relative_root / "GRAPH_REPORT.md").as_posix(),
        query_budget=budget,
        diagnostics=tuple(diagnostics),
    )


def _question(skill_name: str) -> str:
    safe_name = " ".join(str(skill_name).split()).replace('"', "'").replace("`", "'")
    safe_name = safe_name or "the selected skill"
    question = f"What project context is relevant to {safe_name}?"
    if len(question) > 300:
        question = question[:299].rstrip() + "?"
    return question


def render_query_directive(status: GraphContextStatus, skill_name: str) -> str:
    """Render a compact query-first contract for a ready Graphify index."""
    if not status.enabled or status.state != STATE_READY:
        return ""
    return (
        "An existing Graphify index is available. Query it before broad file search:\n"
        f'`graphify query "{_question(skill_name)}" --budget {status.query_budget}`\n\n'
        "Use returned source locations to open only the files needed for this task.\n"
        "Treat INFERRED or AMBIGUOUS edges as hypotheses. Verify critical behaviour in "
        "source and tests before making or approving a change."
    )
```

- [ ] **Step 4: Run the core tests and verify they pass**

Run:

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_graph_context -v
```

Expected: all `InspectGraphContextTests` and `RenderQueryDirectiveTests` pass; final output is `OK`.

- [ ] **Step 5: Run the static no-automation guard**

Run:

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_no_automation -v
```

Expected: 7 tests pass and final output is `OK`.

- [ ] **Step 6: Commit the independently tested boundary, if commits were explicitly authorized**

```powershell
git add src/projectpilot/graph_context.py tests/test_graph_context.py
git commit -m "feat: add Graphify context boundary"
```

Expected: one commit containing only the new module and its tests.

---

### Task 2: Query-first prompt integration

**Files:**
- Modify: `src/projectpilot/prompt_builder.py:20-178`
- Modify: `tests/test_prompt_builder.py:1-168`

**Interfaces:**
- Consumes: `graph_context.inspect_graph_context(base)` and `graph_context.render_query_directive(status, skill_name)` from Task 1
- Produces: `PromptContext.graph_context_status: GraphContextStatus | None`
- Preserves: `build_prompt(...) -> str` signature and all existing output when the feature is absent or disabled

- [ ] **Step 1: Add failing prompt tests**

Add this import to `tests/test_prompt_builder.py`:

```python
from projectpilot import graph_context
```

Add these tests to `BuildPromptTests`:

```python
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
```

Add this test to `CollectContextTests`:

```python
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
```

- [ ] **Step 2: Run prompt tests and verify the expected failure**

Run:

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_prompt_builder -v
```

Expected: FAIL because `PromptContext` does not accept `graph_context_status` and collected context lacks that attribute.

- [ ] **Step 3: Add the graph context field and active phases**

In `src/projectpilot/prompt_builder.py`, add the module import:

```python
from . import artifact_store, graph_context, phase_requirements
```

Add this constant below `_MAX_HANDOFFS`:

```python
_GRAPH_CONTEXT_PHASES = frozenset(
    {
        Phase.PLANNING.value,
        Phase.EXECUTION.value,
        Phase.FINAL_VALIDATION.value,
    }
)
```

Add this field at the end of `PromptContext`:

```python
    graph_context_status: graph_context.GraphContextStatus | None = None
```

Add this keyword to the `PromptContext(...)` returned by `collect_context`:

```python
        graph_context_status=graph_context.inspect_graph_context(base),
```

- [ ] **Step 4: Render the compact directive before the Skill section**

In `build_prompt`, immediately after the existing Project context block and before `skill_lines`, add:

```python
    status = context.graph_context_status
    if status is not None and context.phase_value in _GRAPH_CONTEXT_PHASES:
        directive = graph_context.render_query_directive(status, skill_name)
        if directive:
            out += _section("Context retrieval", directive.splitlines())
```

- [ ] **Step 5: Run prompt and guard tests**

Run:

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_prompt_builder tests.test_no_automation -v
```

Expected: all prompt-builder and guard tests pass; final output is `OK`.

- [ ] **Step 6: Commit the prompt integration, if commits were explicitly authorized**

```powershell
git add src/projectpilot/prompt_builder.py tests/test_prompt_builder.py
git commit -m "feat: add graph-first prompt guidance"
```

Expected: one commit containing only prompt collection/rendering and its tests.

---

### Task 3: Non-blocking advisor recommendation

**Files:**
- Modify: `src/projectpilot/advisor.py:25-459`
- Modify: `tests/test_advisor.py:1-339`

**Interfaces:**
- Consumes: `graph_context.inspect_graph_context(base) -> GraphContextStatus`
- Extends: `AdvisorContext.graph_context_status: GraphContextStatus`
- Produces: `rule_graphify_context(ctx) -> list[Recommendation]`
- Preserves: phase gates, completion, approval ordering, and existing recommendation shapes

- [ ] **Step 1: Add failing advisor tests**

Add this helper after `complete_planning_evidence` in `tests/test_advisor.py`:

```python
def enable_graphify(base: Path) -> None:
    path = config_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("graphify_enabled: true\n", encoding="utf-8")
```

Add this test class before `OrderingAndStabilityTests`:

```python
class GraphifyContextRuleTests(unittest.TestCase):
    def test_missing_graph_is_medium_and_non_blocking_in_active_phase(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            make_state(base, current_phase=Phase.PLANNING)
            enable_graphify(base)
            advice = advisor.advise(base)
            rec = next(r for r in advice.recommendations if "Graphify" in r.action)
            self.assertEqual(rec.priority, advisor.PRIORITY_MEDIUM)
            self.assertEqual(rec.action, "Prepare the external Graphify knowledge graph")
            self.assertEqual(rec.command, "graphify . --no-viz")
            self.assertTrue(
                any("approve execution" in (r.command or "") for r in advice.recommendations)
            )

    def test_partial_graph_recommends_repair(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            make_state(base, current_phase=Phase.EXECUTION)
            enable_graphify(base)
            out = base / "graphify-out"
            out.mkdir()
            (out / "graph.json").write_text("{}\n", encoding="utf-8")
            advice = advisor.advise(base)
            self.assertIn("Repair the external Graphify knowledge graph", actions(advice))

    def test_ready_graph_has_no_preparation_recommendation(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            make_state(base, current_phase=Phase.FINAL_VALIDATION)
            enable_graphify(base)
            out = base / "graphify-out"
            out.mkdir()
            (out / "graph.json").write_text("{}\n", encoding="utf-8")
            (out / "GRAPH_REPORT.md").write_text("# Report\n", encoding="utf-8")
            advice = advisor.advise(base)
            self.assertFalse(any("Graphify" in action for action in actions(advice)))

    def test_inactive_phases_never_recommend_graphify(self):
        inactive = (Phase.IDEA, Phase.VALIDATION, Phase.BRIEF, Phase.SETUP_ADVICE, Phase.DONE)
        for phase in inactive:
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as d:
                base = Path(d)
                make_state(base, current_phase=phase)
                enable_graphify(base)
                advice = advisor.advise(base)
                self.assertFalse(any("Graphify" in action for action in actions(advice)))

    def test_required_evidence_stays_ahead_of_graphify_advice(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            make_state(base, current_phase=Phase.PLANNING)
            enable_graphify(base)
            advice = advisor.advise(base)
            ordered_actions = actions(advice)
            self.assertLess(
                ordered_actions.index("Produce the required 'PRD' artifact"),
                ordered_actions.index("Prepare the external Graphify knowledge graph"),
            )
            gate = next(r for r in advice.recommendations if "approve execution" in (r.command or ""))
            self.assertEqual(gate.priority, advisor.PRIORITY_LOW)
```

- [ ] **Step 2: Run advisor tests and verify the expected failure**

Run:

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_advisor.GraphifyContextRuleTests -v
```

Expected: FAIL because no Graphify recommendation is present.

- [ ] **Step 3: Extend `AdvisorContext` and populate it once**

Update the imports in `src/projectpilot/advisor.py`:

```python
from . import artifact_store, graph_context, phase_requirements
```

Add to `__all__`:

```python
    "rule_graphify_context",
```

Add this field to `AdvisorContext` after `evaluation`:

```python
    graph_context_status: graph_context.GraphContextStatus
```

Add this keyword to the `AdvisorContext(...)` built by `_build_context`:

```python
        graph_context_status=graph_context.inspect_graph_context(base),
```

- [ ] **Step 4: Add the focused advisor rule in the required order**

Add this constant near `_PAST_BRIEF`:

```python
_GRAPH_CONTEXT_PHASES = frozenset(
    {Phase.PLANNING, Phase.EXECUTION, Phase.FINAL_VALIDATION}
)
```

Add this rule immediately before `rule_no_handoffs`:

```python
def rule_graphify_context(ctx: AdvisorContext) -> list[Recommendation]:
    """Suggest external Graphify preparation without blocking a lifecycle gate."""
    status = ctx.graph_context_status
    if (
        ctx.phase not in _GRAPH_CONTEXT_PHASES
        or not status.enabled
        or status.state == graph_context.STATE_READY
    ):
        return []
    partial = status.state == graph_context.STATE_PARTIAL
    action = (
        "Repair the external Graphify knowledge graph"
        if partial
        else "Prepare the external Graphify knowledge graph"
    )
    reason = (
        "Graphify is enabled, but its expected outputs are incomplete. "
        "Prepare them outside ProjectPilot before relying on graph-first retrieval."
        if partial
        else "Graphify is enabled, but no complete graph output is available. "
        "Prepare it outside ProjectPilot to enable graph-first retrieval."
    )
    return [
        Recommendation(
            priority=PRIORITY_MEDIUM,
            action=action,
            reason=reason,
            command="graphify . --no-viz",
            depends_on=f"Current {phase_label(ctx.phase)} phase",
        )
    ]
```

Insert `rule_graphify_context` in `RULES` after `rule_missing_brief` and before `rule_no_handoffs`:

```python
    rule_missing_brief,
    rule_graphify_context,
    rule_no_handoffs,
```

- [ ] **Step 5: Run advisor ordering, stability, and guard tests**

Run:

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_advisor tests.test_no_automation -v
```

Expected: all tests pass; existing Planning ordering tests remain green and final output is `OK`.

- [ ] **Step 6: Commit the advisor integration, if commits were explicitly authorized**

```powershell
git add src/projectpilot/advisor.py tests/test_advisor.py
git commit -m "feat: advise external Graphify preparation"
```

Expected: one commit containing only the advisor context, rule, and tests.

---

### Task 4: Dashboard aggregation and rendering

**Files:**
- Modify: `src/projectpilot/dashboard.py:20-137`
- Modify: `src/projectpilot/commands/dashboard_cmd.py:26-94`
- Modify: `tests/test_dashboard.py:1-162`
- Modify: `tests/test_cli_dashboard.py:1-130`

**Interfaces:**
- Consumes: `graph_context.inspect_graph_context(base)`
- Extends: `Dashboard.graph_context_status: GraphContextStatus | None`
- Produces optional JSON key: `context` after `skills`, with stable subkey order `provider`, `status`, `query_budget`, `graph`, `report`
- Preserves: exact existing dashboard text and JSON when Graphify is disabled

- [ ] **Step 1: Add failing data-layer tests**

Add this import to `tests/test_dashboard.py`:

```python
from projectpilot import graph_context
```

Add this helper after `configure_lib`:

```python
def configure_graphify(base: Path, *, ready: bool) -> None:
    path = config_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("graphify_enabled: true\n", encoding="utf-8")
    if ready:
        out = base / "graphify-out"
        out.mkdir()
        (out / "graph.json").write_text("{}\n", encoding="utf-8")
        (out / "GRAPH_REPORT.md").write_text("# Report\n", encoding="utf-8")
```

Add these tests to `JsonModeTests`:

```python
    def test_enabled_context_is_additive_and_stably_ordered(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            configure_graphify(base, ready=True)
            payload = dashboard.collect(base).to_dict()
            self.assertEqual(
                list(payload.keys()),
                ["project", "phase", "workflow", "artifacts", "skills", "context"],
            )
            self.assertEqual(
                payload["context"],
                {
                    "provider": "graphify",
                    "status": graph_context.STATE_READY,
                    "query_budget": 1200,
                    "graph": "graphify-out/graph.json",
                    "report": "graphify-out/GRAPH_REPORT.md",
                },
            )

    def test_disabled_context_keeps_original_top_level_shape(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            payload = dashboard.collect(base).to_dict()
            self.assertEqual(
                list(payload.keys()),
                ["project", "phase", "workflow", "artifacts", "skills"],
            )
            self.assertNotIn("context", payload)
```

- [ ] **Step 2: Add failing CLI rendering tests**

Add this import to `tests/test_cli_dashboard.py`:

```python
from projectpilot.config import config_path
```

Add this helper after `register`:

```python
def configure_graphify(base: Path, *, ready: bool) -> None:
    path = config_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("graphify_enabled: true\n", encoding="utf-8")
    if ready:
        out = base / "graphify-out"
        out.mkdir()
        (out / "graph.json").write_text("{}\n", encoding="utf-8")
        (out / "GRAPH_REPORT.md").write_text("# Report\n", encoding="utf-8")
```

Add this test to `DashboardTextTests`:

```python
    def test_enabled_graphify_context_renders_status_and_budget(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            seed_state(base)
            configure_graphify(base, ready=True)
            rc, text = self._run(["dashboard", "--dir", d])
            self.assertEqual(rc, 0)
            self.assertIn("Knowledge context", text)
            self.assertIn("Provider: Graphify", text)
            self.assertIn("Status: Ready", text)
            self.assertIn("Query budget: 1200 tokens", text)
```

Add this test to `DashboardJsonTests`:

```python
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
```

- [ ] **Step 3: Run dashboard tests and verify the expected failures**

Run:

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_dashboard tests.test_cli_dashboard -v
```

Expected: FAIL because `Dashboard` has no context field, JSON has no `context`, and text has no Knowledge context section.

- [ ] **Step 4: Extend the dashboard data model and stable JSON**

Update the import in `src/projectpilot/dashboard.py`:

```python
from . import advisor, artifact_store, graph_context, phase_requirements, recommend, skills
```

Add this field at the end of `Dashboard`:

```python
    graph_context_status: graph_context.GraphContextStatus | None = None
```

Refactor the final return in `Dashboard.to_dict` to build `payload`, append context only when enabled, and then return it:

```python
        payload = {
            "project": {
                "name": self.project_name,
                "phase": self.phase.value if self.phase else None,
            },
            "phase": phase_block,
            "workflow": workflow_block,
            "artifacts": artifacts_block,
            "skills": {"recommended": list(self.recommended_skills)},
        }
        status = self.graph_context_status
        if status is not None and status.enabled:
            payload["context"] = {
                "provider": "graphify",
                "status": status.state,
                "query_budget": status.query_budget,
                "graph": status.graph_path,
                "report": status.report_path,
            }
        return payload
```

In `collect`, inspect once after `base = Path(base)`:

```python
    context_status = graph_context.inspect_graph_context(base)
```

Pass the same status in both `Dashboard(...)` return paths:

```python
            graph_context_status=context_status,
```

and:

```python
        graph_context_status=context_status,
```

- [ ] **Step 5: Render the optional text section**

Add this helper to `src/projectpilot/commands/dashboard_cmd.py` before `_render_text`:

```python
def _context_lines(dash: dashboard_mod.Dashboard) -> list[str]:
    status = dash.graph_context_status
    if status is None or not status.enabled:
        return []
    return [
        "",
        "Knowledge context",
        "",
        "Provider: Graphify",
        f"Status: {status.state.title()}",
        f"Query budget: {status.query_budget} tokens",
    ]
```

In the uninitialized branch, add the section before the recommendation:

```python
        lines += _context_lines(dash)
        lines += _recommendation_lines(dash, verbose=verbose)
```

In the initialized branch, add it immediately after Ready to progress:

```python
    lines += _context_lines(dash)
```

- [ ] **Step 6: Run dashboard, advisor, and guard tests**

Run:

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_dashboard tests.test_cli_dashboard tests.test_advisor tests.test_no_automation -v
```

Expected: all tests pass; final output is `OK`.

- [ ] **Step 7: Commit dashboard support, if commits were explicitly authorized**

```powershell
git add src/projectpilot/dashboard.py src/projectpilot/commands/dashboard_cmd.py tests/test_dashboard.py tests/test_cli_dashboard.py
git commit -m "feat: show Graphify context readiness"
```

Expected: one commit with dashboard data, rendering, and tests only.

---

### Task 5: Read-only doctor diagnostics

**Files:**
- Modify: `src/projectpilot/commands/doctor_cmd.py:1-81`
- Modify: `tests/test_cli_doctor.py:1-100`

**Interfaces:**
- Consumes: `graph_context.inspect_graph_context(base)`
- Uses: `shutil.which("graphify")` for a `PATH` lookup only
- Produces: deterministic Knowledge context diagnostic lines
- Preserves: doctor exit code 0 and read-only behaviour

- [ ] **Step 1: Add failing doctor tests**

Add these imports to `tests/test_cli_doctor.py`:

```python
from unittest import mock

from projectpilot.config import config_path
```

Add this helper before `DoctorTests`:

```python
def configure_graphify(base: Path, text="graphify_enabled: true\n") -> None:
    path = config_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
```

Add these tests to `DoctorTests`:

```python
    @mock.patch("projectpilot.commands.doctor_cmd.shutil.which", return_value=None)
    def test_doctor_distinguishes_enabled_but_unavailable(self, which):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            base = Path(d)
            configure_graphify(base)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["doctor", "--dir", d, "--home", home])
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("Knowledge context:", text)
            self.assertIn("Graphify integration: enabled", text)
            self.assertIn("Graphify command on PATH: no", text)
            self.assertIn("Graphify outputs: missing", text)
            which.assert_called_once_with("graphify")

    @mock.patch(
        "projectpilot.commands.doctor_cmd.shutil.which",
        return_value="C:/Tools/graphify.exe",
    )
    def test_doctor_reports_ready_outputs_without_reading_them(self, which):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            base = Path(d)
            configure_graphify(base)
            graph_dir = base / "graphify-out"
            graph_dir.mkdir()
            (graph_dir / "graph.json").write_text("SECRET GRAPH\n", encoding="utf-8")
            (graph_dir / "GRAPH_REPORT.md").write_text("SECRET REPORT\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = main(["doctor", "--dir", d, "--home", home])
            text = out.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("Graphify command on PATH: yes", text)
            self.assertIn("Graphify outputs: ready", text)
            self.assertIn("Query budget: 1200", text)
            self.assertNotIn("SECRET GRAPH", text)
            self.assertNotIn("SECRET REPORT", text)

    @mock.patch("projectpilot.commands.doctor_cmd.shutil.which", return_value=None)
    def test_doctor_surfaces_invalid_configuration_defaults(self, which):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as d:
            base = Path(d)
            configure_graphify(
                base,
                "graphify_enabled: perhaps\ngraphify_query_budget: huge\n",
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main(["doctor", "--dir", d, "--home", home])
            text = out.getvalue()
            self.assertIn("Graphify integration: disabled", text)
            self.assertIn("graphify_enabled is invalid; using false.", text)
            self.assertIn("using 1200", text)
```

- [ ] **Step 2: Run doctor tests and verify the expected failure**

Run:

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_cli_doctor -v
```

Expected: FAIL because `doctor_cmd` does not import `shutil` and emits no Knowledge context diagnostics.

- [ ] **Step 3: Add deterministic diagnostics without execution**

Update `src/projectpilot/commands/doctor_cmd.py` imports:

```python
import shutil
from pathlib import Path

from .. import ateam, detectors, graph_context
```

Immediately after the Git repository diagnostic block, insert:

```python
    context = graph_context.inspect_graph_context(base)
    lines.append("")
    lines.append("Knowledge context:")
    lines.append(
        f"- Graphify integration: {'enabled' if context.enabled else 'disabled'}"
    )
    if context.enabled:
        lines.append(
            f"- Graphify command on PATH: {_yes_no(shutil.which('graphify') is not None)}"
        )
        lines.append(f"- Graphify outputs: {context.state}")
        lines.append(f"- Graph path: {context.graph_path}")
        lines.append(f"- Report path: {context.report_path}")
        lines.append(f"- Query budget: {context.query_budget}")
    for diagnostic in context.diagnostics:
        lines.append(f"- Configuration: {diagnostic}")
```

Do not call `shutil.which` when the feature is disabled. This preserves the intended test assertion and avoids unnecessary environment inspection.

- [ ] **Step 4: Run doctor, context, and guard tests**

Run:

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_cli_doctor tests.test_graph_context tests.test_no_automation -v
```

Expected: all tests pass and final output is `OK`; `tests.test_no_automation` still reports 7 passing tests.

- [ ] **Step 5: Commit doctor diagnostics, if commits were explicitly authorized**

```powershell
git add src/projectpilot/commands/doctor_cmd.py tests/test_cli_doctor.py
git commit -m "feat: diagnose Graphify context availability"
```

Expected: one commit containing only doctor diagnostics and tests.

---

### Task 6: Operator documentation and changelog

**Files:**
- Create: `docs/graphify-integration.md`
- Modify: `README.md:61-94` and `README.md:310-500`
- Modify: `docs/architecture.md:12-98`
- Modify: `docs/extending.md:7-88`
- Modify: `CHANGELOG.md:9-13`
- Include: `docs/superpowers/specs/2026-07-15-graphify-integration-design.md`
- Include: `docs/superpowers/plans/2026-07-15-graphify-integration-implementation-plan.md`

**Interfaces:**
- Documents exact configuration keys and runtime boundaries from Tasks 1-5
- Defines the external operating flow and A/B acceptance threshold
- Preserves private/local release wording and version `1.0.0`

- [ ] **Step 1: Write the dedicated operator guide**

Create `docs/graphify-integration.md` with these sections and exact operational facts:

````markdown
# Optional Graphify context integration

ProjectPilot can detect an externally built Graphify knowledge graph and add a
small query-first instruction to agent prompts. ProjectPilot never installs,
starts, updates, or queries Graphify itself.

## Enable

Add to `.project-pilot/config.yaml`:

```yaml
graphify_enabled: true
graphify_output_dir: graphify-out
graphify_query_budget: 1200
```

The output directory must stay inside the project. The query budget accepts
250 through 5000 tokens. Invalid values fall back to safe defaults and appear
in `pp doctor`.

## Install and build externally

Install Graphify separately from the official `graphifyy` package. ProjectPilot
does not run this command:

```powershell
uv tool install graphifyy
```

See <https://github.com/Graphify-Labs/graphify> for upstream installation and
privacy details. From the project root, the advisor's suggested initial build
command is:

```powershell
graphify . --no-viz
```

For code files, Graphify's AST extraction is local and uses no LLM credits.
Semantic extraction of documents or media may use an externally configured
model and remains an explicit operator choice.

Expected outputs:

```text
graphify-out/graph.json
graphify-out/GRAPH_REPORT.md
```

## Query-first agent flow

When both outputs exist, ProjectPilot skill prompts in planning, execution, and
final validation include a compact command shaped like:

```powershell
graphify query "What project context is relevant to Create PRD?" --budget 1200
```

The agent uses returned source locations to open only necessary files. It must
verify consequential behaviour in source and tests. `INFERRED` and `AMBIGUOUS`
edges are hypotheses, not approval evidence.

## Freshness and fallback

`ready` means both files are present; it does not prove they are current. After
meaningful code changes, update Graphify externally before relying on it in a
later session. If Graphify is unavailable, stale, corrupt, or returns no useful
matches, fall back to targeted `rg` and source reads. No lifecycle gate is
blocked.

## Diagnostics

`pp doctor` reports whether the integration is enabled, whether `graphify` is
on `PATH`, output readiness, safe relative paths, the query budget, and invalid
configuration fallbacks. It runs no external command and changes nothing.

`pp dashboard` shows Knowledge context only when the integration is enabled.
Its JSON adds a final `context` object; disabled projects retain the original
shape.

## Privacy

ProjectPilot reads no Graphify credential and does not parse graph contents.
Generated graph files expose project structure and symbols, so apply the
repository's existing sensitivity and version-control policy. ProjectPilot does
not add these files to Git.

## Token-saving pilot

Before making a product claim, compare baseline and Graphify-assisted runs on a
small, medium, and large repository, with at least five identical tasks per
repository. Record actual model input/output tokens, correctness, files opened,
broad searches, duration, graph failures, and build amortization.

Promote the feature from experimental only when median input tokens fall by at
least 30%, correctness does not materially regress, no severe stale-graph
failure occurs, and ProjectPilot's charter remains intact.
````

- [ ] **Step 2: Add the concise README entry**

After `## Ecosystem assumptions`, add a short subsection named `### Optional Graphify context` containing:

```markdown
### Optional Graphify context

ProjectPilot can optionally detect Graphify outputs and tell agents to query a
small graph context before broad file search. The integration is advisory-only:
ProjectPilot never installs, runs, updates, or imports Graphify, and no lifecycle
gate depends on it. See [docs/graphify-integration.md](docs/graphify-integration.md)
for configuration, privacy, freshness, and the token-saving pilot.
```

In the `## Commands` doctor description, add one sentence stating that `pp doctor` reports optional Graphify readiness when configured. Do not add Graphify to mandatory quick-start steps.

- [ ] **Step 3: Update the architecture map and API table**

In `docs/architecture.md`:

1. Add `GRAPHCTX["graph_context.py<br/>optional Graphify readiness + directive"]` in a new `Context` subgraph.
2. Add arrows from `ADVISOR`, `PROMPT`, and `DASH` to `GRAPHCTX`.
3. Add this subsystem row:

```markdown
| Graph context | `graph_context.py` | Inspect optional Graphify outputs; render compact query guidance | `GraphContextStatus`, `inspect_graph_context`, `render_query_directive` |
```

4. Add this design-principle bullet:

```markdown
- **External context stays advisory.** ProjectPilot detects Graphify readiness and renders instructions, but never imports, executes, updates, or parses the external graph.
```

- [ ] **Step 4: Document the extension boundary**

In `docs/extending.md`, insert `## 5. Add an external context integration` before `## What not to add` with:

```markdown
## 5. Add an external context integration

Graphify is the worked example for context providers. Its adapter is deliberately
limited to safe configuration, local output presence, and deterministic prompt
text. A future provider must preserve the same boundary: no dependency, process,
network, credential access, graph parsing, gate blocking, or automatic artifact
registration. Do not generalize to a provider framework until a second measured
provider requires it.
```

- [ ] **Step 5: Add the unreleased changelog entry**

Under `## [Unreleased]` → `### Added`, append:

```markdown
- Added an experimental, opt-in Graphify context integration: safe output
  readiness detection, compact graph-first prompt guidance, non-blocking advisor
  advice, additive dashboard context, and read-only doctor diagnostics. Graphify
  remains external; ProjectPilot adds no dependency and executes nothing.
```

- [ ] **Step 6: Verify documentation consistency and absence of placeholders**

Run:

```powershell
rg -n "graphify_enabled|graphify_output_dir|graphify_query_budget|30%|advisory-only" README.md docs CHANGELOG.md
```

Expected: each configuration key appears in the operator guide; `30%` appears in the design, plan, and pilot guide; advisory-only wording appears in README/design documentation.

Run:

```powershell
rg -n -i "TB[D]|TO[D]O|FIXM[E]|implement late[r]|fill in detail[s]" docs/graphify-integration.md docs/superpowers/specs/2026-07-15-graphify-integration-design.md docs/superpowers/plans/2026-07-15-graphify-integration-implementation-plan.md
```

Expected: no matches and exit code 1.

- [ ] **Step 7: Commit documentation, spec, and plan, if commits were explicitly authorized**

```powershell
git add README.md CHANGELOG.md docs/architecture.md docs/extending.md docs/graphify-integration.md docs/superpowers/specs/2026-07-15-graphify-integration-design.md docs/superpowers/plans/2026-07-15-graphify-integration-implementation-plan.md
git commit -m "docs: document Graphify context integration"
```

Expected: one documentation-only commit; version files remain unchanged.

---

### Task 7: Full regression and experimental handoff

**Files:**
- Verify all files from Tasks 1-6
- Do not create or modify additional files unless a failing verification identifies a scoped defect

**Interfaces:**
- Validates the complete feature against ProjectPilot's charter and stable APIs
- Produces a clean implementation handoff and preserves the feature's experimental status pending the A/B pilot

- [ ] **Step 1: Run focused feature tests**

Run:

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_graph_context tests.test_prompt_builder tests.test_advisor tests.test_dashboard tests.test_cli_dashboard tests.test_cli_doctor -v
```

Expected: all focused tests pass and final output is `OK`.

- [ ] **Step 2: Run the full ProjectPilot suite**

Run:

```powershell
.venv\Scripts\python.exe -B -m unittest discover -s tests -t .
```

Expected: every test passes, zero failures/errors, final output is `OK`.

- [ ] **Step 3: Run the no-automation guard separately**

Run:

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_no_automation -v
```

Expected: 7 tests pass and final output is `OK`.

- [ ] **Step 4: Verify version consistency and dependency policy**

Run:

```powershell
.venv\Scripts\python.exe -B -m unittest tests.test_version -v
```

Expected: version consistency test passes and final output is `OK`.

Run:

```powershell
rg -n "^version =|^dependencies =|__version__" pyproject.toml src/projectpilot/__init__.py
```

Expected: both versions remain `1.0.0`; dependencies remain `[]`.

- [ ] **Step 5: Verify diff hygiene and intended scope**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors and exit code 0.

Run:

```powershell
git status --short
```

If commits were not authorized, expected intended paths are:

```text
M  CHANGELOG.md
M  README.md
M  docs/architecture.md
M  docs/extending.md
M  src/projectpilot/advisor.py
M  src/projectpilot/commands/dashboard_cmd.py
M  src/projectpilot/commands/doctor_cmd.py
M  src/projectpilot/dashboard.py
M  src/projectpilot/prompt_builder.py
M  tests/test_advisor.py
M  tests/test_cli_dashboard.py
M  tests/test_cli_doctor.py
M  tests/test_dashboard.py
M  tests/test_prompt_builder.py
?? docs/graphify-integration.md
?? docs/superpowers/plans/2026-07-15-graphify-integration-implementation-plan.md
?? docs/superpowers/specs/2026-07-15-graphify-integration-design.md
?? src/projectpilot/graph_context.py
?? tests/test_graph_context.py
```

Existing unrelated `.claude/` and `.superpowers/` entries may still appear; preserve them and never stage them.

If commits were explicitly authorized and every task commit succeeded, none of
the intended paths above should remain modified or untracked. In that case,
`git status --short` may show only the pre-existing unrelated `.claude/` and
`.superpowers/` entries; preserve them.

- [ ] **Step 6: Perform a deterministic smoke check in a temporary project**

Use a new temporary directory and run these operations through the existing test harness or an equivalent temporary fixture:

1. Initialize ProjectPilot and capture `pp dashboard --json` with no Graphify configuration; confirm no `context` key.
2. Add the three Graphify config keys and capture the dashboard again; confirm `context.status == "missing"`.
3. Create only `graphify-out/graph.json`; confirm `context.status == "partial"` and advisor action is Repair.
4. Create `GRAPH_REPORT.md`; confirm `context.status == "ready"`, the preparation recommendation disappears, and a planning skill prompt contains one budgeted query directive.
5. Delete neither output; ProjectPilot must only read them.

Expected: every transition matches disabled → missing → partial → ready, no graph content appears in output, and no lifecycle state or gate changes because of Graphify.

- [ ] **Step 7: Commit any final verification-only fixes, if required and explicitly authorized**

If verification required a scoped correction, rerun Steps 1-5 and then use an exact conventional commit describing that correction. If no correction was needed, do not create an empty commit.

- [ ] **Step 8: Hand off as experimental, not as a proven token claim**

Report:

- exact test commands and counts;
- changed files;
- Graphify remains external and optional;
- actual A/B token pilot has not yet run;
- promotion requires the 30% median input-token threshold and quality safeguards in the approved design.

Do not claim measured token savings until pilot evidence exists.

---

## Post-implementation hardening amendment — 2026-07-15

This dated amendment records the reviewed implementation contract and
supersedes the earlier illustrative resolver, `Path.is_file()`, and quoted-text
sanitizer snippets in this plan. Those snippets are historical TDD scaffolding,
not the accepted implementation.

- Both tolerant configuration loaders treat `UnicodeError` like an unreadable
  file and return their existing empty defaults. Invalid UTF-8 therefore
  disables optional integrations without breaking public commands.
- `inspect_graph_context()` parses only `graphify_enabled` before the normal
  disabled short-circuit. An absent key or recognized false value returns
  stable default relative paths and budget without resolving paths, validating
  related settings, or probing output metadata. An invalid boolean keeps its
  existing diagnostic and related validation, but still never probes graph or
  report files while disabled.
- Output entry inspection uses a private tri-state: safe present, genuinely
  absent, or unsafe. `lstat()` must describe a regular, non-reparse file, then
  strict resolution must remain inside both the project and accepted output
  directory. Only safe-present entries count toward partial/ready. Absent
  entries remain usable build destinations; reparse or symbolic links,
  non-regular entries, containment escapes, and metadata failures are unsafe.
  Graph/report contents are never read.
- `GraphContextStatus.output_path_usable: bool = True` is the final, defaulted
  public field. Inspection returns false for the normal disabled short-circuit
  and whenever no safe resolved output directory/root exists or either output
  entry is unsafe. It returns true only after containment succeeds and both
  entries are absent or safe-present. Its position and default preserve legacy
  positional and keyword constructors; the legacy `AdvisorContext` factory
  explicitly sets it false. Dashboard JSON serialization remains explicit and
  does not expose the field, so its schema is unchanged.
- The advisor may suggest `graphify . --no-viz` only for a usable output path.
  An enabled non-ready status with `output_path_usable == False` produces one
  Medium, commandless recommendation to repair output configuration.
- Query text uses a shell-neutral display allowlist: Unicode alphanumerics,
  whitespace, and `- _ . / '`. Every other character becomes a space before
  whitespace is collapsed and the bounded question is rendered. ProjectPilot
  never sends the result to a shell.

The hardening remains standard-library-only, read-only, advisory, deterministic,
and compatible with the existing no-automation and version/dependency
contracts.
