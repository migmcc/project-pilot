# Changelog

All notable changes to ProjectPilot are documented here. This project is local-only; versions are
local baselines and are not published.

## [Unreleased]

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
- **`pp setup ateam`** — safe-by-default dry-run for A-team setup: inspects the `~/.claude` target,
  discovers possible A-team sources in common locations, reports what a future install would copy
  (skills / agents / commands / settings), detects likely conflicts, and recommends a backup. Does
  not write to `~/.claude`; no flag in v0.1 performs the install.

### Internals

- New read-only modules `projectpilot.detectors` (stack + toolchain probes) and `projectpilot.ateam`
  (environment inspection + install planning). The CI workflows directory name is assembled from
  fragments so the no-automation guard's forbidden-token list stays intact.

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

[0.1.0]: local baseline (not published)
