"""External skill discovery: read knowledge from outside libraries of skills.

PM Skills (and similar repositories) provide the *knowledge*; ProjectPilot keeps
the *control of the project*. This module is the read-only adaptation layer that
lets ProjectPilot point at one or more external skill repositories, discover the
skills inside them, and render a skill as reusable context.

It is deliberately generic -- nothing here is hardcoded to PM Skills. The layers
the design calls for live here:

* **source resolution** -- turn configured paths into concrete, existing roots
  (:func:`resolve_sources`);
* **markdown scanner** -- walk a repository for skill files
  (:func:`scan_skills`);
* **tolerant parser** -- read optional YAML frontmatter, falling back to the
  first heading / paragraph / filename when there is no manifest
  (:func:`parse_skill_file`);
* **rendering** -- consolidate a skill into a single prompt-ready document
  (:func:`render_skill`).

Read-only and stdlib-only: no process is spawned, no network touched, and the
only writes happen when a command explicitly asks to render output elsewhere.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import load_config

#: Manifest filename that marks a directory as a single skill (case-insensitive).
SKILL_MANIFEST = "SKILL.md"

#: Skills whose frontmatter/manifest gave us a name are "manifest"; skills we had
#: to infer from a bare markdown file are "markdown".
KIND_MANIFEST = "manifest"
KIND_MARKDOWN = "markdown"


@dataclass
class SkillSource:
    """A configured external skill repository.

    ``raw`` is the path exactly as configured; ``path`` is it resolved against
    the project directory; ``exists`` reports whether it is a real directory.
    """

    raw: str
    path: Path
    exists: bool


@dataclass
class Skill:
    """A single discovered skill.

    ``skill_id`` is the stable handle used by ``pp skill info/run``. ``name`` and
    ``description`` come from the manifest when present, else are inferred.
    ``path`` is the markdown file the skill was read from, ``source`` is the
    repository root it belongs to, and ``kind`` is :data:`KIND_MANIFEST` or
    :data:`KIND_MARKDOWN`.
    """

    skill_id: str
    name: str
    description: str
    path: Path
    source: Path
    kind: str


def _slugify(value: str) -> str:
    """Reduce a name to a lowercase, hyphenated, filesystem-friendly id."""
    cleaned = []
    for char in value.strip().lower():
        if char.isalnum():
            cleaned.append(char)
        elif char in " _-/\\.":
            cleaned.append("-")
        # drop anything else
    slug = "".join(cleaned)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def resolve_sources(base: Path) -> list[SkillSource]:
    """Resolve configured ``external_skill_paths`` into :class:`SkillSource` objects.

    Relative paths are resolved against the project directory ``base``. Order and
    duplicates are preserved as configured -- this only reports, it does not
    deduplicate or reorder.
    """
    base = Path(base)
    config = load_config(base)
    sources: list[SkillSource] = []
    for raw in config.external_skill_paths:
        candidate = Path(raw)
        resolved = candidate if candidate.is_absolute() else (base / candidate)
        resolved = resolved.resolve()
        sources.append(SkillSource(raw=raw, path=resolved, exists=resolved.is_dir()))
    return sources


def _unquote_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split optional leading ``---`` YAML frontmatter from the body.

    Returns ``(metadata, body)``. When there is no frontmatter (or it is never
    closed) the metadata is empty and the body is the original text.

    Tolerant of the common frontmatter shapes skill libraries use: plain
    ``key: value`` scalars (with optional quotes), and YAML block scalars --
    ``key: |`` (literal, newlines kept) and ``key: >`` (folded, joined with
    spaces) -- whose continuation lines are indented beneath the key. This is
    deliberately small and generic; it is not a full YAML engine and is not
    specific to any one library.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    # Locate the closing delimiter; an unterminated block is treated as body.
    close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if close is None:
        return {}, text

    meta: dict[str, str] = {}
    index = 1
    while index < close:
        line = lines[index]
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or ":" not in line:
            index += 1
            continue

        key_indent = _indent_of(line)
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()

        if value and value[0] in "|>":
            # Block scalar: gather more-indented continuation lines.
            folded = value[0] == ">"
            collected: list[str] = []
            index += 1
            while index < close:
                cont = lines[index]
                if cont.strip() and _indent_of(cont) <= key_indent:
                    break
                collected.append(cont.strip())
                index += 1
            joined = " ".join(c for c in collected if c) if folded else "\n".join(collected)
            meta[key] = joined.strip()
            continue

        meta[key] = _unquote_scalar(value)
        index += 1

    body = "\n".join(lines[close + 1 :])
    return meta, body.lstrip("\n")


def _first_heading(body: str) -> str | None:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or None
    return None


def _first_paragraph(body: str) -> str | None:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return stripped
    return None


def _humanize(stem: str) -> str:
    return stem.replace("-", " ").replace("_", " ").strip().title()


def _default_id(path: Path, source: Path) -> str:
    """Derive a skill id from where the file lives within its source.

    A manifest (``SKILL.md``) is named after its containing directory; a bare
    markdown file is named after the file itself. Falls back to the source name.
    """
    if path.name.lower() == SKILL_MANIFEST.lower():
        parent = path.parent
        stem = parent.name if parent != source else source.name
    else:
        stem = path.stem
    return _slugify(stem) or _slugify(source.name) or "skill"


def parse_skill_file(path: Path, source: Path) -> Skill:
    """Parse a single markdown file into a :class:`Skill` (tolerant; never raises).

    Resolution order for ``name`` and ``description``: YAML frontmatter first,
    then the first ``# heading`` / first paragraph, then a humanised filename.
    The skill is :data:`KIND_MANIFEST` when frontmatter supplied a name or the
    file is a ``SKILL.md`` manifest, otherwise :data:`KIND_MARKDOWN`.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""

    meta, body = _split_frontmatter(text)
    is_manifest_file = path.name.lower() == SKILL_MANIFEST.lower()

    name = meta.get("name") or _first_heading(body) or _humanize(path.stem)
    description = (
        meta.get("description")
        or _first_paragraph(body)
        or "(no description available)"
    )

    skill_id = _slugify(meta["id"]) if meta.get("id") else _default_id(path, source)
    kind = KIND_MANIFEST if (meta.get("name") or is_manifest_file) else KIND_MARKDOWN

    return Skill(
        skill_id=skill_id,
        name=name,
        description=description,
        path=path,
        source=source,
        kind=kind,
    )


def _iter_markdown(root: Path):
    """Yield markdown files under ``root``, skipping hidden directories.

    Sorted for deterministic output. Hidden directories (``.git`` and friends)
    are pruned so repository plumbing never shows up as a skill.
    """
    for path in sorted(root.rglob("*.md")):
        if any(part.startswith(".") for part in path.relative_to(root).parts[:-1]):
            continue
        yield path


def _scan_source(root: Path) -> list[Skill]:
    """Discover skills inside a single existing repository root.

    Strategy: if the repository uses ``SKILL.md`` manifests, each manifest is a
    skill and other markdown is treated as supporting material. If there is no
    manifest anywhere, fall back to treating every markdown file as its own
    skill -- the tolerant, manifest-free path.
    """
    manifests = [p for p in _iter_markdown(root) if p.name.lower() == SKILL_MANIFEST.lower()]
    files = manifests if manifests else list(_iter_markdown(root))
    return [parse_skill_file(path, root) for path in files]


def scan_skills(base: Path) -> list[Skill]:
    """Discover all skills across every configured, existing source.

    Ids are made unique across sources: a collision gets a ``-2``, ``-3`` ...
    suffix so every returned skill has a distinct, addressable handle.
    """
    skills: list[Skill] = []
    used: set[str] = set()
    counts: dict[str, int] = {}
    for source in resolve_sources(base):
        if not source.exists:
            continue
        for skill in _scan_source(source.path):
            base_id = skill.skill_id
            count = counts.get(base_id, 0) + 1
            counts[base_id] = count
            unique = base_id if count == 1 else f"{base_id}-{count}"
            while unique in used:
                count += 1
                counts[base_id] = count
                unique = f"{base_id}-{count}"
            used.add(unique)
            skill.skill_id = unique
            skills.append(skill)
    return skills


def find_skill(base: Path, skill_id: str) -> Skill | None:
    """Return the skill whose id matches ``skill_id`` (case-insensitive), or None."""
    target = skill_id.strip().lower()
    for skill in scan_skills(base):
        if skill.skill_id.lower() == target:
            return skill
    return None


def render_skill(skill: Skill) -> str:
    """Render a skill into a single consolidated, prompt-ready markdown document.

    The header carries provenance (id, source, path, kind) so the rendered output
    is self-describing; the body is the skill's own content with any frontmatter
    stripped. No LLM is called -- this only prepares reusable context.
    """
    try:
        text = skill.path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    _, body = _split_frontmatter(text)

    header = [
        f"# Skill: {skill.name}",
        "",
        f"- Id: {skill.skill_id}",
        f"- Description: {skill.description}",
        f"- Source: {skill.source}",
        f"- Path: {skill.path}",
        f"- Kind: {skill.kind}",
        "",
        "> Prepared by ProjectPilot as reusable context. No LLM was called.",
        "",
        "---",
        "",
    ]
    return "\n".join(header) + body.strip() + "\n"
