"""``pp doctor`` -- report on the local environment (read-only, changes nothing)."""
from __future__ import annotations

from pathlib import Path

from .. import ateam, detectors


def _mark(ok: bool) -> str:
    return "OK" if ok else "MISSING"


def _yes_no(ok: bool) -> str:
    return "yes" if ok else "no"


def run_doctor(args) -> int:
    base = Path(args.dir)
    home = Path(args.home) if getattr(args, "home", None) else Path.home()

    lines: list[str] = ["ProjectPilot doctor (read-only diagnostic)", ""]

    # Toolchain
    py = detectors.python_info()
    lines.append("Toolchain:")
    lines.append(f"- Python: OK ({py['version']})")
    lines.append(f"- Git: {_mark(detectors.git_available())}")
    git = detectors.git_repo_status(base)
    if git.status == detectors.GIT_OK:
        lines.append(f"- Git repository: OK ({git.root})")
    elif git.status == detectors.GIT_INVALID:
        lines.append(f"- Git repository: invalid ({git.detail})")
    else:
        lines.append("- Git repository: missing (not inside a git repository)")

    # Global Claude / A-team environment
    env = ateam.inspect_env(home)
    lines.append("")
    lines.append(f"Claude home ({env.root}):")
    lines.append(f"- ~/.claude: {_mark(env.root_exists)}")
    lines.append(f"- Claude global directory: {_yes_no(env.root_exists)}")
    lines.append(f"- Claude global skills: {_yes_no(env.category_status['skills'] == 'present')}")
    lines.append(f"- Global skills count: {env.global_skills_count}")
    for category in ateam.ATEAM_CATEGORIES:
        count = env.category_counts[category]
        detail = f" ({count} item(s))" if count else ""
        lines.append(f"- ~/.claude/{category}: {env.category_status[category]}{detail}")
    lines.append(f"- ~/.claude/settings.json: {_mark(env.settings_json)}")
    lines.append(f"- Superpowers skills detected: {_yes_no(env.superpowers_detected)}")
    lines.append(f"- A-team signal ({ateam.ATEAM_SIGNAL_SKILL}): {_yes_no(env.ateam_signal)}")
    lines.append(f"- A-team full install: {_yes_no(env.ateam_full_install)}")
    lines.append(f"- A-team install status: {env.install_status}")
    missing = ", ".join(env.missing_categories) if env.missing_categories else "none"
    lines.append(f"- Missing categories: {missing}")

    # Ambiguity signals
    sources = ateam.discover_sources(home)
    local_claude = (base / ".claude").is_dir()
    lines.append("")
    lines.append("Ambiguity signals:")
    if sources:
        lines.append("- Possible alternate A-team source(s) found:")
        for src in sources:
            lines.append(f"  - {src}")
        if env.root_exists:
            lines.append(
                "  (both a global ~/.claude and a 00_Base-style source exist -- "
                "future installs could disagree about the source of truth)"
            )
    else:
        lines.append("- No alternate 00_Base-style A-team source found.")
    if local_claude:
        lines.append(
            f"- A project-local .claude exists at {base / '.claude'} "
            "(may shadow the global one)."
        )

    lines.append("")
    lines.append("doctor changed nothing.")
    print("\n".join(lines))
    return 0
