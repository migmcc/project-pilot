"""``pp setup ateam`` -- inspect (default) or install (``--apply``) the A-team.

Default (no ``--apply``): a safe, read-only dry-run. It inspects the global
``~/.claude`` target and any common A-team source, reports what a future install
would copy and where it would conflict, and recommends a backup. It writes
nothing.

With ``--apply``: an additive, non-destructive install into ``~/.claude``. It
always takes a timestamped backup first, creates missing directories, copies new
content in, leaves identical content untouched, never overwrites differing
content (it writes a sidecar and flags a conflict), and never modifies an
existing ``settings.json``. The source (e.g. ``00_Base``) is never altered.
"""
from __future__ import annotations

from pathlib import Path

from .. import ateam
from ..state import Clock


def run_setup_ateam(args, *, clock: Clock) -> int:
    home = Path(args.home) if getattr(args, "home", None) else Path.home()
    base = Path(getattr(args, "dir", ".") or ".")
    candidates = ateam.source_candidates(base)
    if getattr(args, "apply", False):
        return _run_apply(home, clock, candidates)
    return _run_dry_run(home, candidates)


def _run_dry_run(home: Path, candidates) -> int:
    env = ateam.inspect_env(home)

    lines = ["pp setup ateam (dry-run -- nothing will be installed or changed)", ""]
    lines.append(f"Target: {env.root}")
    lines.append(f"- exists: {'yes' if env.root_exists else 'no'}")
    for category in ateam.ATEAM_CATEGORIES:
        count = env.category_counts[category]
        detail = f" ({count} item(s))" if count else ""
        lines.append(f"- {category}: {env.category_status[category]}{detail}")
    settings = "present" if env.settings_json else "absent"
    lines.append(f"- settings.json (hooks/settings): {settings}")
    lines.append(f"- Superpowers skills detected: {'yes' if env.superpowers_detected else 'no'}")
    lines.append(f"- A-team full install: {'yes' if env.ateam_full_install else 'no'}")
    lines.append(f"- A-team install status: {env.install_status}")
    missing = ", ".join(env.missing_categories) if env.missing_categories else "none"
    lines.append(f"- Missing categories: {missing}")
    lines.append("")

    sources = ateam.discover_sources(home, candidates)
    if not sources:
        lines.append("No A-team source found in the configured locations. Nothing to plan.")
        lines.append("Locations checked (relative to home unless absolute):")
        lines.extend(f"- {rel}" for rel in candidates)
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
    lines.append("This is a dry-run. ~/.claude was not touched.")
    lines.append(
        "Re-run with `--apply` to install (a timestamped backup is taken first; "
        "existing files are never overwritten)."
    )
    print("\n".join(lines))
    return 0


def _run_apply(home: Path, clock: Clock, candidates) -> int:
    sources = ateam.discover_sources(home, candidates)
    if not sources:
        lines = [
            "pp setup ateam --apply",
            "",
            "No valid A-team source found in the configured locations. Nothing was written.",
            "Locations checked (relative to home unless absolute):",
            *[f"- {rel}" for rel in candidates],
        ]
        print("\n".join(lines))
        return 1

    source = sources[0]
    stamp = ateam.compact_stamp(clock())
    result = ateam.apply_ateam(source, home, stamp=stamp)

    lines = ["pp setup ateam --apply", ""]
    lines.append(f"Source: {result.source}")
    lines.append(f"Target: {result.target}")
    lines.append("")

    if result.backup_dir is not None:
        lines.append(f"Backup: {result.backup_dir}")
        lines.append(f"- backed up: {', '.join(result.backed_up)}")
    else:
        lines.append("Backup: nothing existing to back up.")
    lines.append("")

    if result.created_dirs:
        lines.append("Created directories:")
        lines.extend(f"- {d}" for d in result.created_dirs)
        lines.append("")

    for category in ateam.ATEAM_CATEGORIES:
        cat_items = [i for i in result.items if i.category == category]
        lines.append(f"{category}:")
        if not cat_items:
            lines.append("- (nothing available in source)")
            continue
        for item in cat_items:
            suffix = f" -- {item.detail}" if item.detail else ""
            lines.append(f"- {item.name}: {item.status}{suffix}")
    lines.append("")

    lines.append(f"settings.json (hooks/settings): {result.settings_status}")
    if result.settings_status == "preserved":
        lines.append(
            "  An existing settings.json differs from the source and was left "
            "untouched. Merging hooks/settings is deferred to a future run."
        )
    lines.append("")

    lines.append(
        f"Summary: {len(result.copied)} copied, {len(result.unchanged)} unchanged, "
        f"{len(result.conflicts)} conflict(s)."
    )
    if result.conflicts:
        lines.append(
            "Conflicts were not overwritten; incoming copies were written beside "
            f"the originals with the `{ateam.CONFLICT_SUFFIX}` suffix. Review and "
            "reconcile them manually."
        )
    lines.append("Nothing was deleted; the source was not modified.")
    print("\n".join(lines))
    return 0
