"""``pp setup ateam`` -- diagnostic dry-run for A-team setup.

Safe by default: it inspects the global ``~/.claude`` target and any common
A-team source, reports what a future install would need and where it would
conflict, and recommends a backup. It installs nothing and never writes to
``~/.claude`` -- there is no flag in v0.1 that performs the install.
"""
from __future__ import annotations

from pathlib import Path

from .. import ateam


def run_setup_ateam(args) -> int:
    home = Path(args.home) if getattr(args, "home", None) else Path.home()
    env = ateam.inspect_env(home)

    lines = ["pp setup ateam (dry-run -- nothing will be installed or changed)", ""]
    lines.append(f"Target: {env.root}")
    lines.append(f"- exists: {'yes' if env.root_exists else 'no'}")
    for category in ateam.ATEAM_CATEGORIES:
        present = "present" if env.categories[category] else "absent"
        lines.append(f"- {category}: {present}")
    settings = "present" if env.settings_json else "absent"
    lines.append(f"- settings.json (hooks/settings): {settings}")
    lines.append(f"- A-team already installed (likely): {'yes' if env.ateam_likely else 'no'}")
    lines.append("")

    sources = ateam.discover_sources(home)
    if not sources:
        lines.append("No A-team source found in common locations. Nothing to plan.")
        lines.append("Common locations checked (relative to home):")
        lines.extend(f"- {rel}" for rel in ateam.DEFAULT_SOURCE_CANDIDATES)
        lines.append("")
        lines.append("setup ateam changed nothing.")
        print("\n".join(lines))
        return 0

    lines.append("Possible A-team source(s):")
    lines.extend(f"- {src}" for src in sources)

    chosen = sources[0]
    plan = ateam.plan_install(chosen, home)
    lines.append("")
    lines.append(f"Would install from: {chosen}")
    lines.append("What a future install would need to copy:")
    for cat in plan.categories:
        if cat.source_count:
            lines.append(f"- {cat.category}: {cat.source_count} item(s) available")
        else:
            lines.append(f"- {cat.category}: none available in source")
    settings_state = "available" if plan.source_settings else "none in source"
    lines.append(f"- settings.json (hooks/settings): {settings_state}")
    lines.append("")

    if plan.conflicts:
        lines.append("Likely conflicts (target already has content):")
        lines.extend(f"- {item}" for item in plan.conflicts)
        lines.append("")
        lines.append(
            "Recommendation: back up ~/.claude before any future install "
            "(e.g. copy it aside first)."
        )
    else:
        lines.append("No conflicts detected with the current target.")
        lines.append("Recommendation: still back up ~/.claude before any future write.")

    lines.append("")
    lines.append(
        "This is a dry-run. No flag in v0.1 performs the install; ~/.claude was not touched."
    )
    print("\n".join(lines))
    return 0
