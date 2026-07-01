# ProjectPilot

A local, deterministic CLI that orchestrates and **enforces** a project's lifecycle across the
existing tooling ecosystem. It does not execute technically and never reimplements the A-Team or
AgentDesk — it is a process conductor with explicit approval gates.

> **Status:** **v1.0.0-rc.1 — release candidate** under final validation before the stable v1.0.0.
> Full lifecycle (`idea → done`), Python 3.12+, stdlib-only, zero runtime dependencies, deterministic
> output. **Local-first:** designed for a local/private repository; ProjectPilot never publishes,
> pushes, tags, releases, or installs anything itself. Licensed under the [MIT License](LICENSE) but
> not distributed on PyPI.

<!-- Public-release TODO: add a short demo GIF or screenshot of `pp dashboard` / `pp next` here. -->

## Why ProjectPilot?

AI agents (Claude Code, Codex, ChatGPT, …) are great at *doing the work* — writing a PRD, drafting an
architecture, generating tests. What they don't do is **hold the shape of a project over time**: which
phase you're in, which gates you've passed, which artifacts actually exist, and what the next logical
step is. That coordination usually lives in someone's head, a Notion board, or a chat scrollback.

ProjectPilot is the missing **conductor**. It keeps a small, deterministic record of your project's
lifecycle and tells you what to do next — but it **orchestrates, never executes**. It never runs an
agent, calls an LLM, edits your files, or approves its own work. You (and the tools you already use)
stay in control; ProjectPilot keeps everyone honest about the process.

**In practice it lets you:**

- track exactly which lifecycle phase a project is in, with explicit human approval gates;
- discover skills from external libraries and turn them into ready-to-paste prompts for any agent;
- record the evidence agents produce (a PRD, a roadmap, a review) as metadata — never touching the files;
- check, at any moment, what a phase still requires and what the next step should be;
- see it all in one deterministic dashboard.

Everything is **local-first**, **stdlib-only** (zero runtime dependencies), and **deterministic** —
the same state always produces the same output, so it is safe to diff, script, and trust.

## How it compares

ProjectPilot is deliberately narrow: it is the process layer *around* your existing tools, not a
replacement for any of them.

| Tool | What it is great at | What ProjectPilot adds |
| --- | --- | --- |
| **Generic task managers** (Jira, Trello, Linear) | Tasks, boards, tickets | A deterministic *lifecycle* with enforced phase gates and artifact requirements — not just a to-do list |
| **Notion / docs** | Free-form notes and wikis | Machine-checked project state and next-step advice you can script (`--json`), not prose you must read |
| **PM Skills & other skill libraries** | The *knowledge* (how to write a PRD, run a pre-mortem) | Applies that knowledge in context and tracks whether the resulting artifact exists |
| **Claude Code / Codex / ChatGPT** | *Executing* the work | The surrounding process — which phase, which gate, which artifact, what's next; it prepares the prompt but never runs the agent |

In one line: **skill libraries and agents provide the knowledge and the execution; ProjectPilot keeps
control of the project.**

## Charter

ProjectPilot orchestrates and enforces the lifecycle; it never executes technically. It does **not
replace** SkillLab (which owns idea validation), the A-Team (the primary execution engine), or
AgentDesk (optional/complementary), and it never reimplements them. No automation of commits, push,
release, or tool installation; no GitHub API.

## Canonical lifecycle phases (D5)

```text
idea → validation → brief → setup-advice → planning → execution → final-validation → done
```

## Architecture

ProjectPilot is a set of small, single-responsibility modules. Each subsystem exposes a clear public
API; higher layers consume those APIs and never reach into another module's internals. The CLI
(`cli.py`) only parses arguments and dispatches to a thin command module per command; all logic lives
in the subsystems below.

| Subsystem | Module | Responsibility | Key public API |
| --- | --- | --- | --- |
| Lifecycle | `phases.py` | Canonical phases, ordering, labels | `Phase`, `PHASE_ORDER`, `next_phase`, `phase_label` |
| State | `state.py` | Load/save `.project-pilot/status.json` | `ProjectState`, `load_state`, `save_state` |
| Skills (scanner) | `skills.py` | Discover external skills | `scan_skills`, `find_skill`, `render_skill` |
| Recommendations | `recommend.py` | Rank skills for a phase | `rank`, `keywords_for_phase` |
| Prompt builder | `prompt_builder.py` | Assemble an agent-ready prompt | `collect_context`, `build_prompt` |
| Artifact store | `artifact_store.py` | Evidence inventory (metadata only) | `add_artifact`, `list_artifacts`, `find_artifact`, `remove_artifact` |
| Phase requirements | `phase_requirements.py` | Which artifacts a phase expects | `evaluate`, `requirements_for` |
| Workflow advisor | `advisor.py` | Suggest the next step | `advise` |
| Dashboard | `dashboard.py` | Aggregate the above into one view | `collect` |

Two shared helpers keep the surface consistent: `phases.phase_label(phase)` is the single source of a
phase's display name, and `console.py` centralises terminal-output capability (`glyphs` for
Unicode/ASCII fallback of stars, marks, and the progress bar; `make_output_resilient` so arbitrary
Unicode never crashes a legacy console). The advisor, prompt builder, and dashboard consult the
**phase requirements engine** as the single source of truth for completeness rather than re-deriving
it. Everything is deterministic, stdlib-only, and never calls an LLM, spawns a process, or touches the
network.

For a deeper dive, see the docs:

- [docs/architecture.md](docs/architecture.md) — the module map (with a Mermaid diagram) and every
  subsystem's public API.
- [docs/workflow.md](docs/workflow.md) — the lifecycle, per-phase commands, and the skills/evidence loop.
- [docs/extending.md](docs/extending.md) — the supported extension points (skill libraries,
  recommendation rules, phase requirements, advisor rules).

## Quick start

ProjectPilot has **no runtime dependencies** — Python 3.12+ is all you need. Run it straight from the
source tree:

```bash
python -m projectpilot --help
```

Optionally expose the shorter `pp` command with an editable install (a manual developer step):

```bash
pip install -e .
pp --help
```

A 30-second first run:

```bash
pp init "a local code review assistant" --name "Review Assistant"   # start tracking a project
pp status                                                           # where am I?
pp next                                                             # what should I do next?
pp dashboard                                                        # the whole picture, at a glance
```

`pp init` creates a small `.project-pilot/status.json` in the current directory; nothing else on your
machine is touched.

## End-to-end example

A realistic slice: you are in the **planning** phase and want a PRD, using a skill library and an agent
of your choice. ProjectPilot never runs the agent — it prepares the prompt and tracks the result.

```bash
# 1. Point ProjectPilot at a skill library (any markdown skill repo works).
#    In .project-pilot/config.yaml:
#      external_skill_paths:
#        - ../pm-skills

# 2. Ask what the current phase needs, and what to do next.
pp phase check            # e.g. Planning requires: PRD, Roadmap  (0% complete)
pp next                   # advisor: "Prepare the recommended skill 'create-prd'"

# 3. Build a ready-to-paste prompt for the recommended skill.
pp skill use create-prd   # writes projectpilot_outputs/prompts/create-prd.md

# 4. Paste that prompt into Claude Code / Codex / ChatGPT and produce docs/PRD.md yourself.
#    (ProjectPilot did not call any model.)

# 5. Register the evidence — metadata only; the file is never copied or read.
pp artifact add docs/PRD.md

# 6. Watch the project move forward.
pp phase check            # Planning: PRD ✓, Roadmap ✗  (50% complete)
pp next                   # advisor now points at the missing Roadmap
pp dashboard              # one overview: phase, completion, top recommendation, artifacts, skills
```

At no point did ProjectPilot execute a skill, call an LLM, edit a file, or approve a result — it kept
the process on track while you (and your agent of choice) did the work. See
[docs/workflow.md](docs/workflow.md) for the full lifecycle and per-phase commands.

## Commands

```bash
# Foundation
python -m projectpilot init "my project idea" --name "My Project"
python -m projectpilot status                       # read-only
python -m projectpilot dashboard                     # one aggregated project overview
python -m projectpilot dashboard --json              # deterministic machine-readable overview
python -m projectpilot next                          # workflow advisor: suggest the next step
python -m projectpilot next --json                   # deterministic machine-readable advice

# Workflow evidence tracker (metadata only; does not copy/read content)
python -m projectpilot artifact add path/to/PRD.md
python -m projectpilot artifact list
python -m projectpilot artifact list --json
python -m projectpilot artifact show <artifact-id>
python -m projectpilot artifact remove <artifact-id>

# Phase requirements (which artifacts a phase expects; completion %)
python -m projectpilot phase check
python -m projectpilot phase check --verbose        # also list optional requirements
python -m projectpilot phase check --json           # deterministic JSON

# Environment diagnostics (read-only / dry-run; change nothing)
python -m projectpilot doctor                        # Python/Git/repo + ~/.claude install status
python -m projectpilot analyze                       # detect stack/state, suggest next action
python -m projectpilot analyze path/to/project       # positional path (alias for --dir)
python -m projectpilot setup ateam                   # dry-run plan for installing the A-team
python -m projectpilot setup ateam --apply           # install into ~/.claude (backs up first)

# Validation gate (SkillLab owns the decision)
python -m projectpilot validate                     # emits the /skilllab-start-project prompt
python -m projectpilot decision set APPROVED --reason "..."   # records only; does NOT advance
python -m projectpilot advance brief                # explicit gated transition (requires APPROVED)

# Brief intake, setup advice, A-team readiness, execution gate
python -m projectpilot brief import path/to/PROJECT_BRIEF.md  # copies an external brief
python -m projectpilot advise-setup                 # deterministic manual advice (no install)
python -m projectpilot check-ateam                  # read-only readiness check
python -m projectpilot execution approve --reason "..." [--override]

# Final-validation gate (manual checklist; ProjectPilot runs nothing)
python -m projectpilot final-validation prepare

# Done gate (manual closure; no release, tag, or push)
python -m projectpilot done approve --reason "..."

# External skills (read-only; no LLM is ever called)
python -m projectpilot skill sources                 # show configured skill paths
python -m projectpilot skill list                    # list skills found in those paths
python -m projectpilot skill info <skill-id>         # show one skill's details
python -m projectpilot skill run <skill-id>          # prepare a skill as reusable context
python -m projectpilot skill run <skill-id> --print  # print it instead of writing a file
python -m projectpilot skill recommend               # suggest skills for the current phase
python -m projectpilot skill use <skill-id>          # build a consolidated prompt for a skill
python -m projectpilot skill use                     # wizard: choose from phase recommendations
```

State is stored in `.project-pilot/status.json`.

## Workflow evidence tracker (`pp artifact`)

ProjectPilot can record evidence produced by humans, external agents, or adjacent tools while
remaining the workflow orchestrator. Artifact tracking is an inventory of metadata only: ProjectPilot
does **not** execute the file, validate it, approve it, copy it, modify it, upload it, or read its
content into prompts.

The inventory is stored at:

```text
.project-pilot/artifacts.json
```

Examples:

```bash
pp artifact add docs/PRD.md
# Registered artifact: docs-prd-md

pp artifact list
pp artifact list --json
pp artifact show docs-prd-md
pp artifact remove docs-prd-md
```

Each record stores deterministic metadata:

```json
{
  "id": "docs-prd-md",
  "path": "docs/PRD.md",
  "name": "PRD.md",
  "type": "md",
  "phase": "planning",
  "registered_at": "2026-07-01T12:00:00Z",
  "size": 1234,
  "sha256": "...",
  "origin": "manual",
  "status": "registered"
}
```

IDs are stable slugs derived from the artifact's relative path (`docs/PRD.md` →
`docs-prd-md`). Adding the same path again updates that inventory entry with the current size and
SHA-256; it still does not alter the original file. `remove` deletes only the inventory entry and
leaves the artifact file in place.

The tracker is how external agents fit into ProjectPilot: they can produce evidence in their own
tools, and you can register the resulting file so ProjectPilot knows it exists. Advisor and prompt
commands then use only the recorded metadata/path. For example, when a PRD artifact is registered,
`pp next` will avoid recommending a skill whose purpose is to create a PRD again; generated prompts
will list the registered artifact metadata but not include the artifact content.

## Using external skill libraries (`pp skill`)

ProjectPilot can point at external libraries of skills — repositories of reusable product-management
or engineering know-how — and surface them through the `pp skill` commands. **The library provides the
knowledge; ProjectPilot keeps control of the project.** The integration is read-only and **never calls
an LLM**.

> **PM Skills is just one example library, not a required dependency.** ProjectPilot does not bundle,
> vendor, or depend on [`phuryn/pm-skills`](https://github.com/phuryn/pm-skills) (or any other
> library). Point it at whatever library you like — or none. Nothing in the adapter is hardcoded to a
> particular repository.

### 1. Clone a library (example: PM Skills)

Clone any skill library next to your project. Using PM Skills as a worked example:

```bash
# from the parent directory of your project
git clone https://github.com/phuryn/pm-skills.git ../pm-skills
```

ProjectPilot never modifies the cloned library — it only reads from it.

### 2. Configure `external_skill_paths`

List one or more library paths in `.project-pilot/config.yaml`. Relative paths resolve against the
project directory; absolute paths work too. You can configure several libraries at once:

```yaml
external_skill_paths:
  - ../pm-skills
  - /absolute/path/to/another-skill-library
```

### 3. Discover and use skills

```bash
pp skill sources                 # show configured paths and whether each exists
pp skill list                    # discover skills across every configured library
pp skill info create-prd         # show a skill's name, description, kind, source, path
pp skill run create-prd          # render the skill to projectpilot_outputs/skills/create-prd.md
pp skill run create-prd --print  # print the rendered skill to stdout instead of writing a file
```

`pp skill run` consolidates a skill into a single, prompt-ready markdown document (a provenance header
plus the skill's body with any frontmatter stripped). No LLM is called — it only prepares reusable
context you can hand to whatever agent or workflow you choose.

### How discovery works (generic, not PM-Skills-specific)

The adapter detects skill repositories, scans them for markdown, and parses optional YAML frontmatter.
It tolerates the common frontmatter shapes — quoted or unquoted scalars and `|`/`>` block scalars:

- A directory containing a `SKILL.md` manifest becomes a single skill, named after that directory; the
  display `name`/`description` come from the manifest frontmatter when present.
- A library with **no** manifests falls back to treating each markdown file as its own skill,
  inferring the name from the first `# heading` or the filename.
- Skill ids are stable (derived from directory/file names) and made unique across libraries (a
  collision gets a `-2`, `-3` … suffix). Hidden directories such as `.git` are ignored.

Validated against a real clone of `phuryn/pm-skills` (9 plugin categories, 68 `SKILL.md` skills): all
68 are discovered with stable, unique ids and no manual adaptation.

### Skill recommendations (`pp skill recommend`)

`pp skill recommend` suggests which discovered skills are most relevant to the project's **current
lifecycle phase**. It only recommends — it never runs a skill — and, like the rest of `pp skill`, it
**calls no LLM** and uses **no AI or embeddings**.

```text
$ pp skill recommend
Current phase: Planning

Recommended skills

★★★★★ sprint-plan             [pm-skills]  Plan a sprint with capacity estimation, story selection…
★★★★★ create-prd              [pm-skills]  Create a Product Requirements Document using an 8-section…
★★★★★ pre-mortem              [pm-skills]  Run a pre-mortem risk analysis on a PRD or launch plan…
★★★★☆ prioritize-features     [pm-skills]  Prioritize a backlog of feature ideas based on impact…
★★★☆☆ stakeholder-map         [pm-skills]  Build a stakeholder map using a power/interest grid…
```

Each line shows a star rating, the skill id, its origin library, and a short description. Use
`--limit N` to change how many are shown (default 10; `--limit 0` for all). On terminals that cannot
render `★`/`☆` (e.g. a legacy Windows console) the stars degrade to `*`/`.` automatically.

**How the ranking works.** The recommender is a separate layer from the scanner: the scanner only
*discovers* skills, the recommender *decides which to suggest*. Each lifecycle phase has a list of
keyword/category terms. A skill is scored by where those terms appear — in its id/name (strongest),
its category/library folder, or its description (weakest) — and the score maps to a 1–5 star rating.
Results are ordered by score, then by id, so the output is fully **deterministic** and stable.

**Adding or changing rules.** Built-in rules cover all eight phases with generic product/engineering
vocabulary (nothing is tied to a specific library). Override any phase's terms in
`.project-pilot/config.yaml` with a `recommend_<phase>` list — the phase name is its lifecycle value:

```yaml
recommend_planning:
  - prd
  - roadmap
  - risk
  - prioritization
recommend_execution:
  - architecture
  - review
  - testing
```

The phase values are `idea`, `validation`, `brief`, `setup-advice`, `planning`, `execution`,
`final-validation`, and `done`. A `recommend_<phase>` list replaces that phase's defaults; phases you
don't override keep theirs.

**Why other libraries benefit automatically.** Because the rules are plain keyword/category terms and
scoring runs against the generic `name` / `description` / category fields every skill already exposes,
any external library is rankable with no per-library code. Point `external_skill_paths` at a different
library and `pp skill recommend` works against it immediately. The ranking core (`recommend.rank`) is
a single pure function, so it can later be swapped for a smarter ranker without touching the scanner,
the commands, or the configuration.

### Skill execution wizard (`pp skill use`)

`pp skill use` is the bridge from "which skill?" to "a prompt I can run". It selects a skill and
assembles a **consolidated, agent-ready prompt** that combines the project's recorded context with the
skill's content. It **calls no model and executes nothing** — ProjectPilot stays the orchestrator; you
run the prompt in Claude Code, Codex, ChatGPT, or any other agent.

```bash
pp skill use create-prd                 # build a prompt for a specific skill
pp skill use                            # wizard: pick from the current phase's recommendations
pp skill use create-prd --print         # print the prompt instead of writing a file
pp skill use create-prd --output foo.md # write to a custom path
```

With no id, the wizard prints the phase's recommendations and (on an interactive terminal) lets you
pick one by number; on a non-interactive shell it lists them and asks you to pass an id explicitly, so
it never blocks in scripts. By default the prompt is written to
`projectpilot_outputs/prompts/<skill-id>.md`.

The generated document has a fixed, deterministic shape:

```text
Project: Local Review Assistant

Current phase:
Planning

Selected skill:
create-prd

Project context
---------------

Objective:
A local code review assistant

Current state:
Check readiness with `pp check-ateam`, then `pp execution approve`.

Recent handoffs:
- 2026-06-30T09:30:00Z validated (phase: validation)

Notes:
- Decision APPROVED: Strong fit; clear scope.

Files produced by ProjectPilot:
- .project-pilot/status.json

Registered artifacts:
- docs-prd-md | docs/PRD.md | md | planning | registered

Skill
-----
… the selected skill's content …

Instructions
------------
… deterministic guidance; reiterates that ProjectPilot runs no model …
```

**Only recorded facts are included, and empty sections are omitted** — nothing is invented. The
context is drawn from the project state (name, phase, objective/idea, decision & approval reasons,
recent history handoffs), the ProjectPilot-produced files that actually exist on disk, and registered
artifact metadata from `.project-pilot/artifacts.json`. Artifact content is never read. Given the same
state, skill, and inventory, the output is byte-for-byte identical.

**Architecture.** Prompt assembly lives in its own layer (`prompt_builder.py`) with a single job:
collect context, join the skill, emit Markdown. It contains **no skill discovery and no ranking** —
the scanner (`skills.py`) finds skills, the recommender (`recommend.py`) ranks them, and the builder
just assembles. That separation means the prompt format can evolve (templates, variables, multiple
skills) without touching discovery or ranking.

## Workflow advisor (`pp next`)

`pp next` is ProjectPilot as an **orchestrator**: it reads the current project state and registered
artifact metadata, spots gaps (pending gates, missing artifacts, un-prepared recommended skills), and
tells you the next logical step — with a reason for each. It **executes nothing and calls no LLM**; it
only advises.

```bash
pp next            # justified, prioritised recommendations for the current state
pp next --verbose  # also show each recommendation's dependencies
pp next --json     # deterministic JSON for tooling / integration
```

Example:

```text
Current phase: Planning

Recommended next action

1. Prepare the recommended skill 'sprint-plan'
   Priority: High
   Reason: 'sprint-plan' is the top recommended skill for the Planning phase, and no prompt has been prepared for it yet.
   Suggested command: pp skill use sprint-plan

2. Approve the move to execution
   Priority: Medium
   Reason: Planning must be signed off before execution begins.
   Suggested command: pp approve execution --reason "..."

After clearing the Planning gate, ProjectPilot advances to the Execution phase. Review the work before advancing.
```

Each recommendation carries a **priority** (High / Medium / Low), an **action**, a **reason**, an
optional **suggested command**, and (with `--verbose` or in JSON) its **dependencies**.
Recommendations are ordered by priority, and the whole output is **deterministic** — the same state
always produces the same advice, so `--json` is safe to consume from other tools.

**Architecture & rules.** The advisor is its own layer (`advisor.py`) that uses only public
interfaces — it reads recorded state and calls `skills.scan_skills` / `recommend.rank`, never touching
scanner or prompt-builder internals. Its engine is a list of small, independent rules; each is a
function that takes an `AdvisorContext` and returns zero or more recommendations. The current rules:

| Rule | Fires when | Suggests |
| --- | --- | --- |
| `rule_use_recommended_skill` | a top skill for the phase isn't prepared yet, unless registered evidence already covers that artifact | `pp skill use <id>` (High) |
| `rule_phase_gate` | always (per phase) | the phase's gate command (High, or Medium if a skill is pending) |
| `rule_missing_requirements` | the Phase Requirements Engine reports a required artifact missing | produce/register it (Medium) |
| `rule_missing_brief` | past the brief phase with no `PROJECT_BRIEF.md` or registered brief artifact | import a brief (Medium) |
| `rule_no_handoffs` | no lifecycle events recorded yet | `pp continue` (Low) |
| `rule_project_done` | phase is `done` | "Project complete" (Low) |

**Adding a rule** is a two-line change: write a `rule_*(ctx) -> list[Recommendation]` function and
append it to the `RULES` list in `advisor.py`. Because the engine sorts by priority with a stable
sort, a new rule slots into the existing order without disturbing the others.

## Phase requirements (`pp phase check`)

The **Phase Requirements Engine** (`phase_requirements.py`) defines which artifacts each lifecycle
phase expects and measures how complete the current phase is. It is the **single source of truth** for
phase completeness — the workflow advisor and the prompt builder both consult it rather than
re-deriving the rules. It reads only artifact **metadata** (never file contents), calls no LLM, and is
fully deterministic.

```bash
pp phase check            # required requirements, completion %, ready-to-progress
pp phase check --verbose  # also list optional requirements
pp phase check --json     # deterministic JSON for tooling
```

Example:

```text
Current phase: Planning

Requirements

✓ PRD
✗ Roadmap

Optional

✗ Risk Analysis
✗ Architecture

Completion

50%

Ready to progress

No
```

JSON:

```json
{
  "phase": "planning",
  "completion": 50,
  "ready_to_progress": false,
  "completed": ["prd"],
  "missing": ["roadmap"]
}
```

**Requirement model.** Each phase has a tuple of **required** requirements, a tuple of **optional**
ones, and a completion **threshold**. A requirement is a `(key, label, keywords)` triple; it is
*satisfied* when a registered artifact's id/path/name/type matches one of its keywords (whole-token,
case-insensitive). For example, Planning requires a PRD and a Roadmap and optionally a Risk Analysis
and an Architecture doc:

```python
Phase.PLANNING: PhaseRequirements(
    required=(_PRD, _ROADMAP),
    optional=(_RISK, _ARCHITECTURE),
)
```

**Completion algorithm.** Completion is the percentage of **required** artifacts registered —
`round(100 × satisfied_required / total_required)`, or `100%` when a phase has no required artifacts.
Optional requirements are reported for guidance but never change the percentage. A phase is
**ready to progress** when the satisfied fraction meets its `threshold` (default `1.0`, i.e. all
required artifacts present). On terminals that cannot render `✓`/`✗` (e.g. a legacy Windows console)
the marks degrade to `[x]`/`[ ]` automatically.

**Extending requirements.** Add or edit a `Requirement` in a phase's `required`/`optional` tuple in
`REQUIREMENTS` (in `phase_requirements.py`). Every consumer — `pp phase check`, the advisor's
`rule_missing_requirements`, and the prompt builder's completion summary — updates automatically,
because they all call `phase_requirements.evaluate(phase, artifacts)`.

## Project dashboard (`pp dashboard`)

`pp dashboard` is the **single entry point** for a project's status. It aggregates what the other
commands already expose — state, phase completion, the top workflow recommendation, registered
artifacts, and recommended skills — into one read-only overview. It introduces **no new logic**: it is
a thin aggregator over public APIs, calls no LLM, and is fully deterministic.

```bash
pp dashboard            # aggregated overview
pp dashboard --verbose  # + completed/missing requirements, advisor reasoning, artifact metadata
pp dashboard --json     # deterministic JSON for tooling
```

Example:

```text
Project Health: Local Review Assistant

Phase: Planning
█████░░░░░ 50%

Ready to progress:
No

Top recommendation

Prepare the recommended skill 'sprint-plan'

Suggested command

pp skill use sprint-plan

Artifacts (1)

docs/PRD.md

Recommended skills

sprint-plan
create-prd
pre-mortem
```

The JSON form has a stable top-level shape — `project`, `phase`, `workflow`, `artifacts`, `skills` —
so it is safe to consume from other tools:

```json
{
  "project": { "name": "Local Review Assistant", "phase": "planning" },
  "phase": { "completion": 50, "ready_to_progress": false },
  "workflow": { "priority": "High", "action": "…", "reason": "…", "command": "pp skill use sprint-plan" },
  "artifacts": { "total": 1, "items": ["docs/PRD.md"] },
  "skills": { "recommended": ["sprint-plan", "create-prd", "pre-mortem"] }
}
```

**Relationship with the other commands.** The dashboard is a convenience view — every value it shows
comes from a command you can also run on its own: `pp status` (state), `pp phase check` (completion /
readiness), `pp next` (workflow recommendation), `pp artifact list` (evidence), and
`pp skill recommend` (skills). On a legacy console that cannot render `█`/`░`, the progress bar
degrades to `#`/`-` automatically. Like the artifact tracker, the dashboard reads only artifact
**metadata** — never file contents.

## Installing the A-team (`pp setup ateam`)

`pp setup ateam` is the one command that can write *outside* the project, into the global
`~/.claude`. It is safe by default and only writes when you ask:

- **`pp setup ateam`** (no flag) — **diagnostic only**. Inspects `~/.claude` and any common A-team
  source, reports what an install would copy and where it would conflict, and writes nothing.
- **`pp setup ateam --apply`** — **installs into `~/.claude`**, additively and non-destructively:
  - a **timestamped backup is mandatory** and is taken first, at
    `~/.claude/backups/projectpilot-ateam-YYYYMMDD-HHMMSS/` (covering existing `skills`, `agents`,
    `commands`, and `settings.json`);
  - missing directories are created and new content is copied in;
  - identical content is left as `unchanged`;
  - **differing content is never overwritten** — the existing file is preserved and the incoming
    copy is written beside it with a `.projectpilot-new` suffix and flagged as a `conflict` for you
    to reconcile;
  - an existing `settings.json` is **never modified** (reported as `preserved`); merging
    hooks/settings is deferred to a future run;
  - the **source is never modified** and **`00_Base` is never deleted**.

The real A-team install therefore stays under your explicit control: nothing reaches `~/.claude`
without `--apply`, and nothing is ever deleted or overwritten.

`pp doctor` and the dry-run form of `pp setup ateam` distinguish a partial global Claude setup from
a complete A-team install. Global `skills` can be present and valid even when `agents` or `commands`
are missing or empty. Superpowers skills such as `using-superpowers` are reported explicitly, but
they are not treated as proof of a full A-team install.

## Autopilot (v0.2)

The autopilot drives the lifecycle through the deterministic, safe steps and stops at each real
human gate. It is **agent-driven**: ProjectPilot never calls SkillLab, the A-team, AgentDesk, or
Claude Code slash commands, and never uses subprocess/network/GitHub/LLM. It only writes local
instruction files that the VSCode agent (and you) act on.

```bash
# In a new project folder containing idea.md:
python -m projectpilot start --idea idea.md --name "My Project"
#   → auto-runs the safe steps, stops at the first human gate, writes the coordination files.

python -m projectpilot continue        # resume the autopilot after a human gate is cleared

# Friendly approval aliases (human gates):
python -m projectpilot approve decision APPROVED --reason "..."   # records only; does NOT advance
python -m projectpilot approve decision NEEDS_REWORK --reason "..."
python -m projectpilot approve decision REJECTED --reason "..."
python -m projectpilot approve execution --reason "..." [--override]   # advances → execution
python -m projectpilot approve done --reason "..."                     # advances → done
```

`approve decision` is an alias for `decision set` (records only); advancing after `APPROVED` is done
by `pp continue`. `approve execution` and `approve done` alias the existing gate-completing commands.
The original commands remain fully functional.

### Coordination files (in `.project-pilot/`)

- `NEXT_ACTION.md` — always written: current phase, what the autopilot just did, and the single next
  action (with safe instructions for the VSCode agent).
- `ACTION_REQUIRED.md` — written only when blocked on a human gate; **removed** when the block clears.
- `RUN_LOG.md` — a small, deterministic log regenerated from the recorded history.

### Intended VSCode flow

1. Open VSCode in the new project folder; create `idea.md`.
2. Run `pp start --idea idea.md`. ProjectPilot advances to the first human gate and writes
   `NEXT_ACTION.md` / `ACTION_REQUIRED.md`.
3. The agent/human performs the required human step (e.g. run `/skilllab-start-project`, then
   `pp approve decision ...`; or `pp brief import <path>`; or `pp approve execution ...`).
4. Run `pp continue` to advance to the next gate. Repeat until `done`.

ProjectPilot does **not** call SkillLab, the A-team, or AgentDesk automatically — it only prepares
local instructions and records your explicit approvals.

## Transition policy

The lifecycle distinguishes *recording* from *advancing*:

- Commands that only **record** information do **not** advance the phase — e.g. `decision set`.
- `advance brief` is an **explicit, gated** transition (requires an `APPROVED` decision).
- Commands that **complete** a phase's gate **may** advance the phase as part of their action —
  `brief import` (→ `setup-advice`), `advise-setup` (→ `planning`), `execution approve`
  (→ `execution`), `final-validation prepare` (→ `final-validation`), and `done approve` (→ `done`).

## State schema version

`status.json` carries a `schema_version` field, currently **`1`**. It only increases on
backward-incompatible changes or mandatory migrations; additive optional fields keep version `1`
(older state files load with the new fields defaulting to empty).

## Tests

Standard-library `unittest` only:

```bash
python -m unittest discover -s tests -t .
```

The suite includes a cross-restart persistence proof (two separate subprocesses) and a static
no-automation guard that fails if the runtime references process spawning, networking, the GitHub
API, or VCS/release/install automation.

## Continuous integration

A GitHub Actions workflow (`.github/workflows/ci.yml`) runs the unit tests and the no-automation
guard on Python 3.12, with no external dependencies and no pytest.

## Screenshots & GitHub presentation

> This section is prepared for a possible future public release. The repository is **private and
> local-first today** and is **not published to PyPI** (`Private :: Do Not Upload`). None of the assets
> below are required to use ProjectPilot.

Placeholders to fill in before making the repository public:

- **Demo GIF** — a short screen capture of `pp dashboard` and `pp next` on a real project.
  <!-- ![ProjectPilot dashboard demo](docs/assets/dashboard.gif) -->
- **Screenshots** — `pp phase check --verbose`, `pp skill recommend`, and a generated prompt from
  `pp skill use`.
  <!-- ![pp phase check](docs/assets/phase-check.png) -->
- **Suggested GitHub topics** — `cli`, `workflow`, `orchestration`, `lifecycle`, `project-management`,
  `deterministic`, `ai-agents`, `prompt-engineering`, `python`, `stdlib`.
- **GitHub Release notes** — draft per version lives in [CHANGELOG.md](CHANGELOG.md); the release-note
  text for a tag can be lifted from that version's section.

Everything shown in the examples above is real CLI output, so screenshots can be captured directly by
running the commands in a scratch project.
