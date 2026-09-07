# Contributing to ProjectPilot

Thanks for your interest. ProjectPilot is a **local-first, deterministic** CLI with a deliberately
small, stable surface. Contributions are welcome as long as they respect the project's charter.

## Non-negotiable charter

These are enforced (in part by `tests/test_no_automation.py`) and are not up for change in a normal
contribution:

- **Zero runtime dependencies.** The package uses the Python standard library only. Do not add
  anything to `dependencies` in `pyproject.toml`.
- **No automation in production code.** No process spawning, no network access, no GitHub API, no LLM
  calls, and no VCS/release/install automation in `src/`.
- **Deterministic output.** Given the same recorded state, text and `--json` output must be
  byte-identical. Use the injectable clock; never embed wall-clock time in comparable output.
- **Orchestrate, don't execute.** ProjectPilot conducts a lifecycle and prepares context; it never
  runs the work, validates content, or approves results automatically.

## Proposing a change

Open an **issue first** for anything beyond a small fix — a new command, a change to recorded
state or output format, a new configuration key, or anything that touches the charter above. A
short description of the problem and the approach you have in mind is enough. This is not
bureaucracy: the charter rules out a lot of otherwise reasonable ideas, and finding that out in
an issue costs you far less than finding it out after the code is written.

Small, self-contained changes go straight to a pull request: a typo, a documentation correction,
or a clear bug accompanied by a failing test.

Every pull request runs the full CI matrix (Python 3.12 and 3.13) automatically. A red run will
not be reviewed — fix it, or say in the pull request where you are stuck.

## Development setup

Python **3.12+** is required. No install is needed to run from source:

```bash
python -m projectpilot --help
```

Optionally expose the `pp` shortcut with an editable install:

```bash
pip install -e .
```

## Running the tests

Tests use the standard library **`unittest`** only (no pytest, no plugins):

```bash
python -m unittest discover -s tests -t .
```

All tests must pass before a change is proposed. Please also run:

```bash
git diff --check
```

## Guidelines

- **Keep changes surgical.** Scope each change to what it needs; avoid drive-by refactors and style
  churn.
- **Add tests.** New behaviour needs `unittest` coverage; do not reduce existing coverage.
- **Follow the existing style.** Match the surrounding code — docstrings, naming, and the
  single-responsibility module layout described in [docs/architecture.md](docs/architecture.md).
- **Use public interfaces.** Modules should consume each other's public APIs (see each module's
  `__all__`), not reach into internals.
- **Extending?** Most customisation is data-driven — see [docs/extending.md](docs/extending.md)
  (skill libraries, recommendation rules, phase requirements, advisor rules).
- **Update docs and the CHANGELOG** (`[Unreleased]`) for user-visible changes.

## Commit and review

- Make small, focused commits with clear messages.
- Ensure the working tree is clean and tests are green before requesting review.

By contributing, you agree that your contributions are licensed under the project's
[MIT License](LICENSE).
