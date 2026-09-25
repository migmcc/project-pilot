# Repository settings

These settings require repository-owner or administrator access and cannot be enforced from the
working tree. Apply them to the default branch (`main`) after the updated CI workflow has completed
successfully at least once.

## Main branch ruleset

- Require a pull request before merging, with at least one approval.
- Dismiss stale approvals and require review from Code Owners.
- Require all conversations to be resolved before merging.
- Require these status checks:
  - `Tests (Python 3.12)`
  - `Tests (Python 3.13)`
  - `Tests (Python 3.14)`
  - `Quality gates`
  - `Build and installed-package smoke test`
  - `Secret scan`
- Require branches to be up to date before merging.
- Block force pushes and branch deletion.
- Do not allow bypass for repository administrators.

Also enable automatic deletion of head branches after pull requests merge. Keep GitHub Actions'
default token permission read-only; grant write permissions only to a workflow step that explicitly
needs them.
