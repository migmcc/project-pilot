"""``pp doctor`` -- report on the local environment (read-only, changes nothing)."""
from __future__ import annotations

from pathlib import Path

from .. import ateam, detectors


def _mark(ok: bool) -> str:
    return "OK" if ok else "MISSING"


def run_doctor(args) -> int:
    base = Path(args.dir)
    home = Path(args.home) if getattr(args, "home", None) else Path.home()

    lines: list[str] = ["ProjectPilot doctor (read-only diagnostic)", ""]

    # Toolchain
    py = detectors.python_info()
    lines.append("Toolchain:")
    lines.append(f"- Python: OK ({py['version']})")
    lines.append(f"- Git: {_mark(detectors.git_available())}")
    repo_root = detectors.find_git_root(base)
    if repo_root is not None:
        lines.append(f"- Git repository: OK ({repo_root})")
    else:
        lines.append("- Git repository: not inside a git repository")

    # Global Claude / A-team environment
    env = ateam.inspect_env(home)
    lines.append("")
    lines.append(f"Claude home ({env.root}):")
    lines.append(f"- ~/.claude: {_mark(env.root_exists)}")
    for category in ateam.ATEAM_CATEGORIES:
        lines.append(f"- ~/.claude/{category}: {_mark(env.categories[category])}")
    lines.append(f"- ~/.claude/settings.json: {_mark(env.settings_json)}")
    signal = f" (signal: {ateam.ATEAM_SIGNAL_SKILL})" if env.ateam_signal else ""
    lines.append(f"- A-team install (likely): {'yes' if env.ateam_likely else 'no'}{signal}")

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
