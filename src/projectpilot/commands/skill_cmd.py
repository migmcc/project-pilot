"""``pp skill`` -- discover and use external libraries of skills.

Read-mostly subcommands:

* ``pp skill sources`` -- show the configured external skill paths;
* ``pp skill list`` -- list skills discovered across those paths;
* ``pp skill info <id>`` -- show one skill's details;
* ``pp skill run <id>`` -- prepare a skill as reusable context (no LLM);
* ``pp skill recommend`` -- suggest skills for the current lifecycle phase.

PM Skills provides the knowledge; ProjectPilot keeps control of the project.
None of these commands call an LLM. ``run`` only renders the skill into a
consolidated document and, by default, writes it under ``projectpilot_outputs``;
``recommend`` only ranks discovered skills and prints suggestions.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .. import recommend as recommend_mod
from .. import skills
from ..config import EXTERNAL_SKILL_PATHS_KEY, config_path
from ..errors import StateNotFoundError
from ..state import load_state

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


def _phase_label(phase) -> str:
    return phase.value.replace("-", " ").title()


def _star_marks() -> tuple[str, str]:
    """Pick star glyphs the current stdout can encode, falling back to ASCII.

    The Unicode stars (``★``/``☆``) are not encodable on every console (e.g. a
    Windows ``cp1252`` terminal), where printing them raises ``UnicodeEncodeError``.
    We probe the output encoding once and degrade to ``*``/``.`` when needed.
    """
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        "★☆".encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return "*", "."
    return "★", "☆"


def _truncate(text: str, width: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 3].rstrip() + "..."


def run_skill_recommend(args) -> int:
    base = Path(args.dir)

    try:
        state = load_state(base)
    except StateNotFoundError:
        print('No ProjectPilot state found. Run `pp init "<idea>"` first.')
        return 1

    phase = state.current_phase
    print(f"Current phase: {_phase_label(phase)}")
    print("")

    sources = skills.resolve_sources(base)
    if not sources:
        print("No external skill paths configured.")
        print("Run `pp skill sources` for how to configure them.")
        return 0

    found = skills.scan_skills(base)
    keywords = recommend_mod.keywords_for_phase(base, phase)
    ranked = recommend_mod.rank(found, keywords)

    limit = getattr(args, "limit", None)
    if limit is not None and limit > 0:
        ranked = ranked[:limit]

    if not ranked:
        if not found:
            print("No skills found in the configured sources.")
        else:
            print(f"No skill recommendations for phase '{phase.value}'.")
        return 0

    print("Recommended skills")
    print("")
    filled, empty = _star_marks()
    width = max(len(rec.skill.skill_id) for rec in ranked)
    for rec in ranked:
        stars = recommend_mod.stars_string(rec.stars, filled=filled, empty=empty)
        origin = Path(rec.skill.source).name
        desc = _truncate(rec.skill.description)
        print(f"{stars} {rec.skill.skill_id.ljust(width)}  [{origin}]  {desc}")
    return 0
