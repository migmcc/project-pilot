# Workflow

ProjectPilot orchestrates and **enforces** a project's lifecycle; it never executes the work itself.
It stops at every human gate and records deterministic state in `.project-pilot/status.json`.

## Lifecycle phases (D5)

```text
idea → validation → brief → setup-advice → planning → execution → final-validation → done
```

Transitions follow a strict policy:

- Commands that only **record** information do not advance the phase (`pp decision set`).
- `pp advance brief` is an explicit gated transition (requires an `APPROVED` decision).
- Commands that **complete** a phase's gate may advance the phase (`pp brief import`,
  `pp advise-setup`, `pp execution approve`, `pp done approve`).

## Per-phase commands

| Phase | Typical command(s) | Gate to advance |
| --- | --- | --- |
| `idea` | `pp validate` | emits the validation prompt; enters `validation` |
| `validation` | `pp decision set APPROVED --reason "…"`, then `pp advance brief` | an `APPROVED` decision |
| `brief` | `pp brief import <PROJECT_BRIEF.md>` | an imported brief |
| `setup-advice` | `pp advise-setup` | setup advice prepared |
| `planning` | `pp execution approve --reason "…" [--override]` | readiness check (`pp check-ateam`) or explicit override |
| `execution` | do the work with your execution toolkit, then `pp final-validation prepare` | execution complete + reviewed |
| `final-validation` | complete the checklist, then `pp done approve --reason "…"` | final validation signed off |
| `done` | — | lifecycle complete |

`pp start --idea <path>` (initialize + run the autopilot to the first human gate) and `pp continue`
(resume after a gate is cleared) drive the safe, deterministic steps automatically.

## Orchestration commands (advice only)

These read the recorded state and help you decide what to do next. They **never** execute a skill,
call a model, or modify project files.

- **`pp next`** — the Workflow Advisor: justified, prioritised recommendations for the current state
  (`--json`, `--verbose`).
- **`pp dashboard`** — one aggregated overview: phase, completion %, top recommendation, artifacts,
  recommended skills (`--json`, `--verbose`).
- **`pp phase check`** — which artifacts the current phase expects, completion %, and readiness
  (`--json`, `--verbose`).

## Skills and evidence

ProjectPilot can point at external libraries of skills and turn them into reusable prompts, and it can
track the evidence agents produce — always as metadata, never by executing or reading contents.

- **Discover / use skills:** `pp skill sources | list | info <id> | run <id> | recommend | use [<id>]`.
- **Track evidence:** `pp artifact add <file> | list | show <id> | remove <id>`. Registering a file
  records only its metadata (path, size, SHA-256, type, phase); the file itself is never copied,
  modified, or read into prompts.

A typical loop in the `planning` phase:

```bash
pp phase check                 # what does planning require? (e.g. PRD, roadmap)
pp skill use create-prd        # build a prompt to hand to your agent of choice
# … run the prompt in Claude Code / Codex / ChatGPT, produce docs/PRD.md …
pp artifact add docs/PRD.md    # register the evidence (metadata only)
pp next                        # advisor updates: PRD satisfied, roadmap still missing
```

See [architecture.md](architecture.md) for how these subsystems fit together and
[extending.md](extending.md) for how to customise them.
