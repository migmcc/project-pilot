"""``pp skill`` -- discover and use external libraries of skills.

Read-mostly subcommands:

* ``pp skill sources`` -- show the configured external skill paths;
* ``pp skill list`` -- list skills discovered across those paths;
* ``pp skill info <id>`` -- show one skill's details;
* ``pp skill run <id>`` -- prepare a skill as reusable context (no LLM);
* ``pp skill recommend`` -- suggest skills for the current lifecycle phase;
* ``pp skill use [id]`` -- wizard: pick a skill and build a consolidated prompt.

PM Skills provides the knowledge; ProjectPilot keeps control of the project.
None of these commands call an LLM. ``run`` only renders the skill into a
consolidated document and, by default, writes it under ``projectpilot_outputs``;
``recommend`` only ranks discovered skills and prints suggestions; ``use`` only
assembles a prompt -- it never runs a model or executes the skill.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .. import console, prompt_builder
from .. import recommend as recommend_mod
from .. import skills
from ..config import EXTERNAL_SKILL_PATHS_KEY, config_path
from ..errors import StateNotFoundError
from ..phases import phase_label
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


def _star_marks() -> tuple[str, str]:
    """Star glyphs the console can encode (``★``/``☆``), else ASCII ``*``/``.``."""
    return console.glyphs(("★", "☆"), ("*", "."))


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
    print(f"Current phase: {phase_label(phase)}")
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


def _select_skill_interactively(base, phase, found):
    """Show phase recommendations and let the user pick one.

    Used only when no skill id was given. Returns ``(skill, rc)``: when ``skill``
    is non-None the caller proceeds to build the prompt; otherwise ``rc`` is the
    exit code to use. Informational/cancelled outcomes use ``rc=0``; an invalid
    selection uses ``rc=1``. On a non-interactive stdin it never blocks -- it
    prints the recommendations and asks the user to pass an id explicitly.
    """
    keywords = recommend_mod.keywords_for_phase(base, phase)
    ranked = recommend_mod.rank(found, keywords)
    if not ranked:
        print(f"No skill recommendations for phase '{phase.value}'.")
        print("Pick any skill explicitly with `pp skill use <id>` (see `pp skill list`).")
        return None, 0

    filled, empty = _star_marks()
    width = max(len(rec.skill.skill_id) for rec in ranked)
    print("Recommended skills for this phase:")
    print("")
    for index, rec in enumerate(ranked, start=1):
        stars = recommend_mod.stars_string(rec.stars, filled=filled, empty=empty)
        origin = Path(rec.skill.source).name
        print(f"  {index}. {stars} {rec.skill.skill_id.ljust(width)}  [{origin}]")
    print("")

    if not sys.stdin.isatty():
        print("Re-run with `pp skill use <id>` to select one (non-interactive input).")
        return None, 0

    try:
        raw = input(f"Select a skill [1-{len(ranked)}] (or 'q' to cancel): ").strip()
    except EOFError:
        return None, 0
    if raw.lower() in ("", "q", "quit"):
        print("Cancelled.")
        return None, 0
    if not raw.isdigit() or not (1 <= int(raw) <= len(ranked)):
        print(f"'{raw}' is not a valid choice.")
        return None, 1
    return ranked[int(raw) - 1].skill, 0


def run_skill_use(args) -> int:
    base = Path(args.dir)

    try:
        state = load_state(base)
    except StateNotFoundError:
        print('No ProjectPilot state found. Run `pp init "<idea>"` first.')
        return 1

    skill_id = getattr(args, "skill_id", None)
    if skill_id:
        skill = skills.find_skill(base, skill_id)
        if skill is None:
            print(f"No skill found with id '{skill_id}'.")
            print("Run `pp skill list` to see available skills.")
            return 1
    else:
        sources = skills.resolve_sources(base)
        if not sources:
            print("No external skill paths configured.")
            print("Run `pp skill sources` for how to configure them.")
            return 1
        found = skills.scan_skills(base)
        if not found:
            print("No skills found in the configured sources.")
            return 1
        print(f"Current phase: {phase_label(state.current_phase)}")
        print("")
        skill, rc = _select_skill_interactively(base, state.current_phase, found)
        if skill is None:
            return rc
        print("")

    context = prompt_builder.collect_context(state, base)
    document = prompt_builder.build_prompt(
        context,
        skill_id=skill.skill_id,
        skill_name=skill.name,
        skill_description=skill.description,
        skill_body=skills.skill_body(skill),
    )

    if getattr(args, "print", False):
        print(document, end="" if document.endswith("\n") else "\n")
        return 0

    output = getattr(args, "output", None)
    if output:
        out_path = Path(output)
        if not out_path.is_absolute():
            out_path = base / out_path
    else:
        out_path = base / prompt_builder.OUTPUT_SUBDIR / f"{skill.skill_id}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(document, encoding="utf-8")

    print(f"Prepared a prompt for skill '{skill.skill_id}' (no LLM called, nothing executed).")
    print(f"Wrote {out_path}")
    return 0
