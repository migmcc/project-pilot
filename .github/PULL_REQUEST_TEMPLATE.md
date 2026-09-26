## What changed

Describe the problem and the smallest change that solves it.

Closes #

## Verification

- [ ] `python -m unittest discover -s tests -t .`
- [ ] `python -m unittest tests.test_no_automation`
- [ ] `python -m ruff check src tests`
- [ ] `python -m coverage run -m unittest discover -s tests -t .`
- [ ] `python -m coverage report`
- [ ] User-visible changes are documented in `CHANGELOG.md`.
- [ ] The change preserves the orchestration-only, deterministic, zero-runtime-dependency charter.
