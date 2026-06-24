# ProjectPilot

A local, deterministic CLI that orchestrates and **enforces** a project's lifecycle across the
existing tooling ecosystem. It does not execute technically and never reimplements the A-Team or
AgentDesk — it is a process conductor with explicit approval gates.

> **Status:** lifecycle implemented through the `execution` phase. Python 3.12+, stdlib-only.

## Charter

ProjectPilot orchestrates and enforces the lifecycle; it never executes technically nor reimplements
the A-Team (the primary execution engine) or AgentDesk (optional/complementary). No automation of
commits, push, release, or tool installation; no GitHub API.

## Canonical lifecycle phases (D5)

```
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

# Validation gate (SkillLab owns the decision)
python -m projectpilot validate                     # emits the /skilllab-start-project prompt
python -m projectpilot decision set APPROVED --reason "..."   # records only; does NOT advance
python -m projectpilot advance brief                # explicit gated transition (requires APPROVED)

# Brief intake, setup advice, A-team readiness, execution gate
python -m projectpilot brief import path/to/PROJECT_BRIEF.md  # copies an external brief
python -m projectpilot advise-setup                 # deterministic manual advice (no install)
python -m projectpilot check-ateam                  # read-only readiness check
python -m projectpilot execution approve --reason "..." [--override]
```

State is stored in `.project-pilot/status.json`.

## Transition policy

The lifecycle distinguishes *recording* from *advancing*:

- Commands that only **record** information do **not** advance the phase — e.g. `decision set`.
- `advance brief` is an **explicit, gated** transition (requires an `APPROVED` decision).
- Commands that **complete** a phase's gate **may** advance the phase as part of their action —
  `brief import` (→ `setup-advice`), `advise-setup` (→ `planning`), and `execution approve`
  (→ `execution`).

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
