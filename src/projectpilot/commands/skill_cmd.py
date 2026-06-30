"""``pp skill`` -- discover and use external libraries of skills.

Four read-mostly subcommands:

* ``pp skill sources`` -- show the configured external skill paths;
* ``pp skill list`` -- list skills discovered across those paths;
* ``pp skill info <id>`` -- show one skill's details;
* ``pp skill run <id>`` -- prepare a skill as reusable context (no LLM).

PM Skills provides the knowledge; ProjectPilot keeps control of the project.
None of these commands call an LLM. ``run`` only renders the skill into a
consolidated document and, by default, writes it under ``projectpilot_outputs``.
"""
from __future__ import annotations

from pathlib import Path

from .. import skills
from ..config import EXTERNAL_SKILL_PATHS_KEY, config_path

#: Where ``pp skill run`` writes rendered skills by default.
OUTPUT_SUBDIR = Path("projectpilot_outputs") / "skills"


def run_skill_sources(args) -> int:
    base = Path(args.dir)
    sources = skills.resolve_sources(base)

    lines = ["ProjectPilot external skill sources", ""]
    if not sources:
        lines.append("No external skill paths configured.")
        lines.append("")
        lines.append(f"Add an `{EXTERNAL_SKILL_PATHS_KEY}` list to:")
        lines.append(f"  {config_path(base)}")
        lines.append("")
        lines.append("Example:")
        lines.append(f"  {EXTERNAL_SKILL_PATHS_KEY}:")
        lines.append("    - ../pm-skills")
        print("\n".join(lines))
        return 0

    for source in sources:
        status = "ok" if source.exists else "missing"
        lines.append(f"- {source.raw}  [{status}]")
        lines.append(f"    -> {source.path}")
    print("\n".join(lines))
    return 0


def run_skill_list(args) -> int:
    base = Path(args.dir)
    sources = skills.resolve_sources(base)
    found = skills.scan_skills(base)

    lines = ["ProjectPilot skills", ""]
    if not sources:
        lines.append("No external skill paths configured.")
        lines.append("Run `pp skill sources` for how to configure them.")
        print("\n".join(lines))
        return 0

    missing = [s for s in sources if not s.exists]
    if missing:
        lines.append("Warning: some configured sources do not exist:")
        for source in missing:
            lines.append(f"- {source.raw} -> {source.path}")
        lines.append("")

    if not found:
        lines.append("No skills found in the configured sources.")
        print("\n".join(lines))
        return 0

    lines.append(f"Found {len(found)} skill(s):")
    width = max(len(skill.skill_id) for skill in found)
    for skill in found:
        lines.append(f"- {skill.skill_id.ljust(width)}  {skill.name}")
    lines.append("")
    lines.append("Use `pp skill info <id>` for details or `pp skill run <id>` to prepare it.")
    print("\n".join(lines))
    return 0


def run_skill_info(args) -> int:
    base = Path(args.dir)
    skill = skills.find_skill(base, args.skill_id)
    if skill is None:
        print(f"No skill found with id '{args.skill_id}'.")
        print("Run `pp skill list` to see available skills.")
        return 1

    lines = [
        f"Skill: {skill.name}",
        "",
        f"- Id: {skill.skill_id}",
        f"- Description: {skill.description}",
        f"- Kind: {skill.kind}",
        f"- Source: {skill.source}",
        f"- Path: {skill.path}",
    ]
    print("\n".join(lines))
    return 0


def run_skill_run(args) -> int:
    base = Path(args.dir)
    skill = skills.find_skill(base, args.skill_id)
    if skill is None:
        print(f"No skill found with id '{args.skill_id}'.")
        print("Run `pp skill list` to see available skills.")
        return 1

    rendered = skills.render_skill(skill)

    if getattr(args, "print", False):
        print(rendered, end="" if rendered.endswith("\n") else "\n")
        return 0

    out_dir = base / OUTPUT_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{skill.skill_id}.md"
    out_path.write_text(rendered, encoding="utf-8")

    print(f"Prepared skill '{skill.skill_id}' as reusable context (no LLM called).")
    print(f"Wrote {out_path}")
    return 0
