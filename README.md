# ProjectPilot

A local, deterministic CLI that orchestrates and **enforces** a project's lifecycle across the
existing tooling ecosystem. It does not execute technically and never reimplements the A-Team or
AgentDesk — it is a process conductor with explicit approval gates.

> **Status: Run A (foundation).** Only `init` and `status` exist. Python 3.12+, stdlib-only.

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

## Commands (Run A)

```bash
# Initialize project state (.project-pilot/status.json) in the current directory
python -m projectpilot init "my project idea" --name "My Project"

# Show the current phase, next phase, active gate, and next action (read-only)
python -m projectpilot status
```

State is stored in `.project-pilot/status.json` with a `schema_version` field.

## Tests

Standard-library `unittest` only:

```bash
python -m unittest discover -s tests -t .
```

The suite includes a cross-restart persistence proof (two separate subprocesses) and a static
no-automation guard that fails if the runtime references process spawning, networking, the GitHub
API, or VCS/release/install automation.
