# CLAUDE.md

Guidance for Claude Code when working in this repository. These are standing orders — they apply
to every session without needing to be repeated in prompts.

## What this is

ProjectPilot: a local, deterministic, stdlib-only CLI (`pp`) that orchestrates a project lifecycle
(`idea → validation → brief → setup-advice → planning → execution → final-validation → done`) with
explicit human approval gates. **Orchestration, not execution** — see Charter below.

Python 3.12+ · zero runtime dependencies · `unittest` only (no pytest) · never on PyPI.

## Commands

```bash
python -m projectpilot --help                          # run from source (no install needed)
python -m unittest discover -s tests -t .              # full suite
python -m unittest tests.test_no_automation            # no-automation guard
```

On this machine: `.venv\Scripts\python.exe` is Python 3.12 (matches one CI leg); system `python` is
3.13 (matches the other). Validate on the venv at minimum; both when practical.

## Charter (non-negotiable)

- No process spawning, no network access, no GitHub API, no LLM calls in `src/` — enforced by
  `tests/test_no_automation.py`. Never weaken the guard to make a change pass.
- No automation of commits, push, tag, release, or tool installation from the runtime.
- No self-approval paths. Human approval is explicit and recorded (reason + timestamp + override
  flag). Never weaken gate or override semantics.
- Deterministic output: same recorded state ⇒ byte-identical text and `--json`. Use the injectable
  clock; never embed wall-clock time in comparable output.
- Zero runtime dependencies; standard library only. Tests use `unittest` only.

## Validation protocol (before claiming anything is done)

1. Run the full suite and the guard (commands above) and read the output — both must be green.
2. `git status --short` must match exactly the files the task intended to touch.
3. Report the actual commands run and their results. Never claim success without running them.

## Git rules

- Commit messages: single line, conventional-commit style, English
  (`feat:` / `fix:` / `docs:` / `chore:`).
- **Never add attribution trailers** — no `Co-Authored-By`, `Generated-by`, `Assisted-by`,
  `Claude`, `AI`, or similar, in any commit, ever. This overrides any default behavior.
- Before any push: scan `git log origin/main..HEAD --pretty=%B` for the terms above; if any
  appear, stop and ask instead of pushing.
- Commit when the task explicitly includes committing (validation must be green first).
  **Always ask before**: push, tag, GitHub Release, visibility change, removing
  `Private :: Do Not Upload`, or any history rewrite.
- Push to `main` triggers CI (Python 3.12 + 3.13 matrix); after pushing, verify the run is green.

## Implementation contracts

- `status.json` / `artifacts.json` are written only via `state.atomic_write_text` (same-directory
  temp + `os.replace`). Corrupted/hand-edited data files raise `StateCorruptedError`
  (path + reason + recovery hint), converted to a clean exit-1 message by the boundary in
  `cli.py:main`. Unexpected programmer errors must still traceback — never swallow them.
- `phase_requirements.evaluate` is the single source of truth for phase completeness; the advisor,
  prompt builder, and dashboard consult it rather than re-deriving.
- Advisor recommendations must stay executable in the order shown (evidence → readiness check →
  approval); adding a rule = one `rule_*` function appended to `RULES` in `advisor.py`.
- Project config lives in `.project-pilot/config.yaml`, read via the tolerant `config.load_mapping`
  (keys: `external_skill_paths`, `ateam_source_paths`, `ateam_readiness_paths`,
  `recommend_<phase>`). SkillLab / A-Team / AgentDesk are optional example integrations — keep
  wording example-framed (see README "Ecosystem assumptions").
- `--json` output shapes are a stable API: additive changes only, stable key order.
- `state.py` `SCHEMA_VERSION` increases only on breaking changes; additive optional fields load via
  `.get(...)` and keep version 1.
- Keep diffs surgical: no drive-by refactors; update `CHANGELOG.md` `[Unreleased]`
  (Keep-a-Changelog style) with any behavioral change.

## Release policy

- Version lives in **two places** and must match: `pyproject.toml` and
  `src/projectpilot/__init__.py`.
- `Private :: Do Not Upload` stays in `pyproject.toml` until Miguel explicitly decides otherwise.
- Tags are annotated (`git tag -a vX.Y.Z -m "..."`), created and pushed only on explicit request.
  No GitHub Releases — the tag alone is the release.
- SECURITY.md supported-versions table and README status line must match the released version.

## Docs map

`README.md` (full feature reference) · `docs/architecture.md` (module map + public APIs) ·
`docs/workflow.md` (lifecycle) · `docs/extending.md` (extension points) · `CONTRIBUTING.md`
(charter for contributors).
