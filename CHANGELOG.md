# Changelog

All notable changes to ProjectPilot are documented here. This project is local-only; versions are
local baselines and are not published.

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
