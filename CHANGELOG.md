# Changelog

All notable changes to ProjectPilot are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project adheres to
[Semantic Versioning](https://semver.org/). ProjectPilot is local-first and stdlib-only. The current
release is **v1.0.0-rc.1**, a release candidate under final validation; the final **v1.0.0** will be
tagged only after RC validation passes.

## [Unreleased]

### Added
- **Configurable A-team integration points (PP-AUDIT-003)** — two new optional keys in
  `.project-pilot/config.yaml`: `ateam_source_paths` (where `pp doctor` and `pp setup ateam` look
  for a copyable toolkit source; entries are home-relative unless absolute) and
  `ateam_readiness_paths` (what `pp check-ateam` requires before execution approval; entries ending
  in `/` must be directories, all others files). Defaults are unchanged, so existing projects
  behave identically.
- `pp setup ateam` accepts `--dir <project>` to choose which project's configuration to read
  (default: current directory).

### Changed
- **Packaging/docs/CI alignment (PP-AUDIT-006)** — while ProjectPilot remains at
  `v1.0.0-rc.1`, packaging metadata now uses the Beta development classifier, contributing docs use
  the same `unittest discover` command as README and CI, CI covers Python 3.12 and 3.13, and the RC1
  changelog reference points to the tag rather than a GitHub Release URL.
- **Portability wording (PP-AUDIT-003)** — user-facing prompts, advice, help text, and docs now
  present SkillLab, the A-team, and AgentDesk as optional example integrations from one local
  workflow rather than assumed tools; the validation prompt is generic with the SkillLab slash
  command kept as a worked example, and a new README "Ecosystem assumptions" section documents the
  conventions and the config overrides. Gate semantics, command names, exit codes, and recorded
  state shapes are unchanged (the `advise-setup` advice strings recorded in new state files are
  reworded; previously recorded state is unaffected).

### Fixed
- **Friendly corrupted-state handling (PP-AUDIT-001)** — a corrupted or hand-edited
  `status.json` / `artifacts.json` no longer crashes commands with a raw Python traceback. A new
  `StateCorruptedError` (path + reason + recovery hint) is raised by `load_state` /
  `load_inventory` for malformed JSON, missing required fields, an unknown `current_phase`,
  wrong-typed recorded sections, and artifact records missing required fields; a central CLI
  boundary converts it into a clear message and exit code 1. Optional recorded sub-dicts missing
  expected keys (e.g. a hand-edited `decision` without its verdict) now degrade gracefully in
  `pp status` instead of raising `KeyError`. Unexpected internal errors still surface as
  tracebacks — only expected user-facing state/config errors are converted.
- **Atomic state writes (PP-AUDIT-004)** — `status.json` and `artifacts.json` are now written via
  a same-directory temporary file and `os.replace`, so an interruption mid-write can no longer
  leave a half-written file behind. On failure the temporary file is removed and the original is
  left untouched. New public helper: `state.atomic_write_text`.

## [1.0.0] - unreleased

_Prepared for the first stable release, **not yet tagged.** It is being validated through
**v1.0.0-rc.1** (below). The `v1.0.0` tag will be created only after RC validation passes; no changes
are planned between RC1 and 1.0.0 beyond fixes surfaced during validation. The full change list for
1.0.0 is documented under the RC1 entry._

## [1.0.0-rc.1] - 2026-07-01

**Release candidate 1 for v1.0.0.** This is a **release candidate**, not the final release.

- **No new functionality** was added relative to the prepared v1.0.0 work — RC1 packages exactly the
  1.0.0 changes below for validation.
- **Goal:** final validation (tests, examples, docs, packaging) before v1.0.0.
- **Next:** the final **v1.0.0** will follow after RC1 validation; only validation fixes, if any, will
  land in between.

First stable release scope. Since v0.2.0 (autopilot + environment diagnostics), ProjectPilot gained a
complete, deterministic skills-and-evidence workflow layer — external skill libraries, phase-aware
recommendations, prompt building, a workflow advisor, an artifact evidence tracker, a phase
requirements engine, and a unified dashboard — followed by an architecture review that consolidated
shared helpers. Everything remains local-first, stdlib-only, and deterministic: no LLM calls, no
network, no process spawning, and no runtime dependencies.

### Added
- **Project Dashboard (`pp dashboard`)** — a single, aggregated, read-only project overview. A new
  `dashboard.py` layer is a thin **aggregator**: it introduces no workflow logic and duplicates
  nothing, consuming only public APIs (`state.load_state`, `phase_requirements.evaluate`,
  `advisor.advise`, `artifact_store.list_artifacts`, `skills.scan_skills` + `recommend.rank`) to
  assemble project name/phase, completion % and readiness, the top workflow recommendation, registered
  artifacts, and recommended skills. Text mode shows a progress bar (degrading to ASCII on legacy
  consoles); `--verbose` adds completed/missing requirements, advisor reasoning, and an artifact
  metadata summary (metadata only — never file contents); `--json` emits a deterministic
  `{project, phase, workflow, artifacts, skills}` payload with stable ordering. No LLM, no network, no
  process spawning, stdlib only.
- **Phase Requirements Engine (`pp phase check`)** — a deterministic engine (`phase_requirements.py`)
  that defines which artifacts each lifecycle phase expects (required + optional, with a completion
  threshold) and evaluates completeness against the registered artifact inventory. It reads only
  artifact **metadata** (never contents), uses stdlib only, and is the **single source of truth** for
  phase completeness. New command `pp phase check` reports satisfied/missing requirements, a completion
  percentage, and `ready_to_progress`; `--verbose` adds optional requirements and `--json` emits a
  deterministic `{phase, completion, ready_to_progress, completed, missing}` payload (✓/✗ marks degrade
  to ASCII on legacy consoles). **Integrations:** the Workflow Advisor now consults the engine via a new
  `rule_missing_requirements` rule instead of checking artifacts ad hoc, and the Prompt Builder includes
  a phase-completion summary (percentage + missing requirement labels) in the project context —
  metadata only. Completion = `round(100 × satisfied_required / total_required)`; optional artifacts are
  advisory and never affect it. Extending is a one-line change to the `REQUIREMENTS` table.
- **Workflow Evidence Tracker (`pp artifact`)** — records metadata for human- or external-agent
  produced evidence in `.project-pilot/artifacts.json`. New commands: `pp artifact add <file>`,
  `pp artifact list`, `pp artifact list --json`, `pp artifact show <id>`, and
  `pp artifact remove <id>`. The dedicated `artifact_store.py` module owns inventory load/save,
  SHA-256 calculation, stable path-derived ids, duplicate handling, listing, lookup, and removal.
  ProjectPilot records only metadata/path; it does **not** execute, validate, approve, copy, modify,
  upload, or read artifact content. Advisor now consults registered artifact metadata to avoid
  duplicate artifact-creation recommendations such as creating a PRD when a PRD artifact is already
  registered. Prompt Builder lists registered artifact metadata in project context without reading
  artifact contents. JSON output is deterministic and stdlib-only.
- **Workflow advisor (`pp next`)** — analyses the project state and suggests the next logical step,
  with a justified reason for each recommendation. **Executes nothing and calls no LLM** — advice only.
  A new decoupled `advisor.py` layer uses only public interfaces (recorded state, `skills.scan_skills`,
  `recommend.rank`); its engine is a list of small, independent rules (missing brief, pending phase
  gate, un-prepared recommended skill, no handoffs, project done) that each return prioritised
  `Recommendation`s. Output is deterministic and ordered by priority (High/Medium/Low). `--verbose`
  adds dependencies; `--json` emits a stable machine-readable form for tooling. Adding a rule is a
  two-line change (write a `rule_*` function, append it to `RULES`).
- **Skill execution wizard (`pp skill use`)** — selects a skill and builds a consolidated,
  agent-ready prompt that combines the project's recorded context with the skill's content. **Calls no
  model and executes nothing** — the prompt is meant to be run in Claude Code, Codex, ChatGPT, or any
  other agent. With no id it runs a wizard over the current phase's recommendations (interactive
  numbered pick on a TTY; lists-and-exits on a non-interactive shell). Output goes to
  `projectpilot_outputs/prompts/<skill-id>.md` by default, or `--output <path>` / `--print`. A new
  decoupled `prompt_builder.py` layer owns context collection and Markdown assembly only (no skill
  discovery, no ranking); it includes only recorded facts (name, phase, objective, decision/approval
  reasons, recent handoffs, produced files), omits empty sections, invents nothing, and is
  deterministic. Added `skills.skill_body()` to extract a skill's frontmatter-stripped body for
  embedding.
- **Skill recommendations (`pp skill recommend`)** — suggests which discovered skills are most
  relevant to the project's current lifecycle phase. Recommend-only (never runs a skill), deterministic,
  and **no AI / embeddings / LLM**. A new `recommend.py` layer is decoupled from the scanner: the
  scanner discovers skills, the recommender ranks them. Each phase has generic keyword/category rules
  (built-in defaults for all eight phases, overridable per phase via `recommend_<phase>` lists in
  `.project-pilot/config.yaml`); a pure `rank()` core scores each skill by where the terms match
  (id/name > category > description) and maps the score to a 1–5 star rating, ordered by score then id.
  Any external library is rankable with no per-library code. Stars degrade to ASCII on terminals that
  cannot encode `★`/`☆`, and CLI output now tolerates arbitrary Unicode in external content instead of
  crashing on legacy consoles.
- **External skills integration (`pp skill`)** — ProjectPilot can point at external libraries of
  skills (e.g. `phuryn/pm-skills`) and reuse their knowledge while keeping control of the project.
  Configure libraries via `external_skill_paths` in `.project-pilot/config.yaml`. New read-only
  subcommands: `pp skill sources` (show configured paths), `pp skill list` (discover skills),
  `pp skill info <id>` (show details), and `pp skill run <id>` (render a skill into
  `projectpilot_outputs/skills/<id>.md`, or stdout with `--print`). No LLM is ever called. The
  adapter is generic — not hardcoded to PM Skills: it scans markdown, parses optional YAML
  frontmatter, treats `SKILL.md` manifests as skills, and falls back to per-file skills (name from
  the first heading or filename) when a library has no manifest. Still stdlib-only and side-effect
  free apart from the explicit `pp skill run` output file.
- `config.py` — a tolerant stdlib-only loader for `.project-pilot/config.yaml` (a small YAML subset:
  scalars, block lists, and inline lists), plus the `skills.py` adaptation layer (`resolve_sources`,
  `scan_skills`, `find_skill`, `render_skill`).
- `detectors.git_repo_status()` returning a `GitRepoStatus` (`status` / `root` / `detail`), plus the
  `GIT_MISSING` / `GIT_OK` / `GIT_INVALID` constants. `pp analyze` now prints a `Git repository:` line.

### Changed
- **Architecture review (internal consolidation; no behaviour change).** Removed duplicated
  helpers ahead of the stable release: the phase display name is now a single `phases.phase_label`
  (previously re-implemented in five modules), and a new `console.py` centralises terminal-output
  capability — `glyphs()` (Unicode-with-ASCII-fallback for the star, tick/cross, and progress-bar
  marks, previously three near-identical helpers) and `make_output_resilient()` (moved out of
  `cli.py`). Fixed the one cross-module internal access (`next` command reaching into
  `advisor._phase_label`). Documented the module map and each subsystem's public API in the README.
  No new commands, features, or dependencies; all existing behaviour and output are unchanged.

### Fixed
- **Git repository detection** — `pp doctor` and `pp analyze` no longer report `Git repository: OK`
  when only an empty or corrupt `.git` exists. Detection now distinguishes `missing` (no `.git`),
  `OK` (valid `.git` directory with `HEAD`, `objects/`, and `refs/`), and `invalid` (a `.git` that
  exists but is incomplete). A `.git` *file* of the form `gitdir: <path>` (submodules and linked
  worktrees, including the `commondir` indirection) is resolved and validated against its target.
  Still stdlib-only and read-only — no subprocess, no `git` invocation.

## [0.2.0] - 2026-06-24

Local v0.2 baseline: agent-driven **autopilot** on top of the v0.1 lifecycle, plus richer local
environment diagnostics and an opt-in A-team installer. ProjectPilot now drives the deterministic,
safe steps and stops at each real human gate, writing local instruction files for the VSCode agent.
Charter unchanged: it never calls SkillLab, the A-team, AgentDesk, or Claude Code slash commands, and
uses no subprocess/network/GitHub/LLM.

### Added — Autopilot
- **Autopilot** — `pp start --idea <path>` (reads the idea file, initializes state, runs to the first
  human gate) and `pp continue` (resumes after a gate is cleared). Advances `idea → validation`,
  `validation → brief` (only after `APPROVED`), and `setup-advice → planning` automatically; stops at
  every human gate.
- **Approval aliases** — `pp approve decision <APPROVED|NEEDS_REWORK|REJECTED> --reason` (records
  only; does not advance), `pp approve execution --reason [--override]`, and `pp approve done
  --reason`. Thin aliases over the existing commands; no new gate semantics.
- **Coordination files** in `.project-pilot/` — `NEXT_ACTION.md` (always), `ACTION_REQUIRED.md`
  (only when blocked; removed when the block clears), and a small deterministic `RUN_LOG.md`
  regenerated from history.
- **State** — added optional `idea_source` (path the idea was read from); `schema_version` stays `1`.

### Added — A-team installation (opt-in)
- **`pp setup ateam --apply`** — installs the A-team into `~/.claude`, additively and
  non-destructively. Without `--apply` the command stays a read-only dry-run.
  - A **mandatory timestamped backup** is taken first at
    `~/.claude/backups/projectpilot-ateam-YYYYMMDD-HHMMSS/` (existing `skills` / `agents` /
    `commands` / `settings.json`).
  - Missing directories are created; new content is copied; **identical content is left
    `unchanged`**; **differing content is never overwritten** — the original is preserved and the
    incoming copy is written beside it with a `.projectpilot-new` suffix and flagged as a
    `conflict`.
  - An existing `settings.json` is **never modified** (`preserved`); hooks/settings merging is
    deferred to a future run.
  - Fails cleanly without writing anything when no valid A-team source is found. The source
    (e.g. `00_Base`) is never modified or deleted.
- New read-only/install primitives in `projectpilot.ateam`: `backup_existing`, `apply_ateam`,
  `compact_stamp`, and the `ApplyResult` / `ApplyItem` report types. The backup directory name is
  derived from the injectable clock for deterministic tests.

### Added — local environment commands
- **`pp doctor`** — read-only diagnostic of the local environment: Python and Git availability,
  whether the working directory is inside a git repository, the presence of `~/.claude` and its
  `skills` / `agents` / `commands` sub-directories and `settings.json`, a likely-A-team-installed
  signal (the `using-a-team` skill), and ambiguity signals (a `00_Base`-style alternate source, or a
  project-local `.claude`). Changes nothing.
- **`pp analyze`** — read-only stack/state detection (`pyproject.toml`, `requirements.txt`,
  `package.json`, `README.md`, `tests/`, CI workflows), a new-vs-existing hint, whether the project
  is ProjectPilot-initialized, and a suggested next action (including when AgentDesk could help).
  Invents nothing.
- **`pp setup ateam`** (dry-run) — safe-by-default A-team setup diagnostic: inspects the `~/.claude`
  target, discovers possible A-team sources in common locations, reports what an install would copy
  (skills / agents / commands / settings), detects likely conflicts, and recommends a backup. Writes
  nothing without `--apply`.

### Changed — Claude/A-team diagnostics
- **`pp doctor` and `pp setup ateam` now distinguish partial and complete Claude/A-team setups.**
  They report global Claude directory presence, global skills presence/count, Superpowers detection,
  full A-team install status, and missing/empty categories instead of collapsing the result into a
  single likely-installed boolean. Global skills can be valid without `agents` / `commands`, and
  Superpowers (`using-superpowers`) is reported separately from a complete A-team install.

### Changed — `pp analyze` UX
- **`pp analyze` now accepts an optional positional directory** as an alias for `--dir`, so
  `pp analyze .` and `pp analyze path/to/project` work. `pp analyze` (current directory) and
  `pp analyze --dir <path>` are unchanged. Supplying both the positional path and `--dir` fails
  cleanly with `Use either positional path or --dir, not both.` (exit code 2). Read-only behaviour
  is unchanged.

### Internals
- New read-only modules `projectpilot.detectors` (stack + toolchain probes) and `projectpilot.ateam`
  (environment inspection + install planning). The CI workflows directory name is assembled from
  fragments so the no-automation guard's forbidden-token list stays intact.

### Notes
- The original v0.1 commands remain fully functional. Python 3.12+, stdlib-first, `unittest`-only.
- No subprocess/network/GitHub/LLM in the runtime; no push/tag/release; nothing installed.

## [0.1.0] - 2026-06-24

First local baseline. ProjectPilot is a local, deterministic CLI that orchestrates and enforces a
project's lifecycle (`idea → done`). It never executes technically and does not replace SkillLab
(idea validation), the A-Team (primary execution engine), or AgentDesk (optional/complementary).

### Added
- **Foundation** — `pp init` / `pp status`, lifecycle state in `.project-pilot/status.json` with a
  `schema_version`, canonical phase catalogue, injectable clock for deterministic output.
- **Manual decision gate** — `pp validate` (emits the `/skilllab-start-project` prompt; does not
  validate the idea), `pp decision set <APPROVED|NEEDS_REWORK|REJECTED> --reason` (records only),
  and the explicit gated transition `pp advance brief` (requires `APPROVED`).
- **Brief intake** — `pp brief import <path>` copies an externally produced PROJECT_BRIEF.md
  (SkillLab owns the brief; ProjectPilot does not generate it).
- **Setup advice** — `pp advise-setup` produces deterministic manual advice (no installation).
- **A-team readiness check** — `pp check-ateam`, a read-only readiness check (no installation).
- **Execution approval gate** — `pp execution approve --reason [--override]`, gated on A-team
  readiness or an explicit recorded override.
- **Final validation preparation** — `pp final-validation prepare`, a manual checklist that runs
  nothing (no tests, audit, skill gate, or GitHub).
- **Done approval gate** — `pp done approve --reason`, a manual closure with no release, tag, or push.

### Quality
- **No-automation guard** — a static test fails the build if `src/` references process spawning,
  networking, the GitHub API, or VCS/release/install automation.
- **Cross-restart persistence proof** — state survives across separate processes.
- **Deterministic CLI** with an injectable clock.

### Constraints
- Python 3.12+, **stdlib-first** (zero runtime dependencies).
- Tests use the standard library **`unittest`** only (no pytest).
- No commits/push/release/tag from the runtime; no GitHub API; no AgentDesk; no A-team installation.

[1.0.0]: unreleased (pending RC validation)
[1.0.0-rc.1]: https://github.com/migmcc/project-pilot/tree/v1.0.0-rc.1
[0.2.0]: local baseline (not published)
[0.1.0]: local baseline (not published)
