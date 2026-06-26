# ProjectPilot

A local, deterministic CLI that orchestrates and **enforces** a project's lifecycle across the
existing tooling ecosystem. It does not execute technically and never reimplements the A-Team or
AgentDesk — it is a process conductor with explicit approval gates.

> **Status:** full lifecycle implemented (`idea` → `done`). Python 3.12+, stdlib-only.
> **Local / private-first:** intended for a private repository (backup & continuity); not published
> and not publicly released.

## Charter

ProjectPilot orchestrates and enforces the lifecycle; it never executes technically. It does **not
replace** SkillLab (which owns idea validation), the A-Team (the primary execution engine), or
AgentDesk (optional/complementary), and it never reimplements them. No automation of commits, push,
release, or tool installation; no GitHub API.

## Canonical lifecycle phases (D5)

```text
idea → validation → brief → setup-advice → planning → execution → final-validation → done
```

## Install / run

No runtime dependencies. Canonical invocation:

```bash
python -m projectpilot --help
```

Optionally expose the `pp` shortcut with an editable install (a manual developer step):

```bash
pip install -e .
pp --help
```

## Commands

```bash
# Foundation
python -m projectpilot init "my project idea" --name "My Project"
python -m projectpilot status                       # read-only

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
```

State is stored in `.project-pilot/status.json`.

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
