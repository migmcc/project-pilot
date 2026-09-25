# Security Policy

ProjectPilot is a **local, deterministic CLI**. By design it has **no runtime dependencies** and, in
production code, performs **no process spawning, no network access, no GitHub API calls, and no LLM
calls** — a static test (`tests/test_no_automation.py`) fails the build if `src/` ever introduces
these. Normal lifecycle state stays within the project directory (chiefly `.project-pilot/`). The
explicit `pp setup ateam --apply` command is the one exception: it backs up and writes A-Team files
under `~/.claude`. External skill text is read as prompt input; registered artifact bytes are read
only to calculate SHA-256 metadata and are never executed, parsed, or included in prompts.

This substantially limits the runtime attack surface, but responsible disclosure is still welcome.

## Supported versions

| Version | Supported |
| --- | --- |
| `1.0.x` | ✅ |
| `< 1.0` (including `1.0.0-rc.x`) | ❌ |

## Reporting a vulnerability

Please report suspected vulnerabilities **privately** — do not open a public issue for security
matters.

- Email: **migmcc@gmail.com** with a subject beginning `SECURITY:`.
- Include: affected version, a description, reproduction steps, and impact.

You can expect an acknowledgement within a reasonable time. Once a fix is available, the affected
versions and the resolution will be noted in [CHANGELOG.md](CHANGELOG.md).

## Scope

In scope: the ProjectPilot runtime under `src/`. Out of scope: external skill libraries you configure
(e.g. `pm-skills`), the agents you choose to run generated prompts in, and anything ProjectPilot
explicitly does not do (execute skills, call models, or reach the network).
