"""Project configuration: the optional ``.project-pilot/config.yaml`` file.

ProjectPilot is stdlib-only, so this module ships a *tolerant* parser for the
tiny YAML subset the configuration needs -- top-level scalar keys and simple
string lists. It is intentionally forgiving: unrecognised lines are ignored
rather than raising, so a malformed config degrades to "no external skills"
instead of breaking the CLI. Read-only: this module never writes.

Supported shapes::

    external_skill_paths:
      - ../pm-skills
      - /abs/path/to/skills

    # inline lists work too
    external_skill_paths: [../pm-skills, ../more-skills]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .state import STATE_DIRNAME

CONFIG_FILENAME = "config.yaml"

#: The configuration key that lists external skill repositories.
EXTERNAL_SKILL_PATHS_KEY = "external_skill_paths"


def config_path(base: Path) -> Path:
    """Return the expected config path: ``<base>/.project-pilot/config.yaml``."""
    return Path(base) / STATE_DIRNAME / CONFIG_FILENAME


@dataclass
class Config:
    """Parsed project configuration. Absent keys fall back to empty defaults."""

    external_skill_paths: list[str] = field(default_factory=list)


def _strip_inline_comment(value: str) -> str:
    """Drop an unquoted ``#`` comment tail.

    A quoted value keeps its quoted span (so a ``#`` inside quotes survives) and
    anything after the closing quote -- including a trailing comment -- is
    dropped.
    """
    value = value.strip()
    if not value:
        return value
    if value[0] in "'\"":
        end = value.find(value[0], 1)
        if end != -1:
            return value[: end + 1]
        return value
    hash_index = value.find("#")
    if hash_index == -1:
        return value
    return value[:hash_index]


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def _parse_inline_list(value: str) -> list[str]:
    """Parse a ``[a, b, c]`` inline list into stripped, unquoted strings."""
    inner = value.strip()[1:-1]
    return [_unquote(item) for item in inner.split(",") if item.strip()]


def _parse(text: str) -> dict[str, object]:
    """Parse the supported YAML subset into a plain dictionary.

    Recognises top-level ``key: value`` scalars, ``key:`` followed by indented
    ``- item`` block lists, and ``key: [a, b]`` inline lists. Anything else is
    ignored. This is deliberately small and tolerant -- not a YAML engine.
    """
    result: dict[str, object] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        stripped = line.lstrip()
        indented = line[0] in " \t"

        # A block-list item belonging to the key we are currently reading.
        if indented and stripped.startswith("-") and current_list is not None:
            item = _unquote(_strip_inline_comment(stripped[1:].strip()))
            if item:
                current_list.append(item)
            continue

        # Otherwise this should be a top-level ``key: value`` line.
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = _strip_inline_comment(value.strip()).strip()
        current_key = key
        current_list = None

        if not value:
            # ``key:`` introduces a block list; collect following ``- item`` lines.
            current_list = []
            result[key] = current_list
        elif value.startswith("[") and value.endswith("]"):
            result[key] = _parse_inline_list(value)
        else:
            result[key] = _unquote(value)

    return result


def parse_config(text: str) -> Config:
    """Parse raw config text into a :class:`Config` (tolerant; never raises)."""
    data = _parse(text)
    raw_paths = data.get(EXTERNAL_SKILL_PATHS_KEY, [])
    paths: list[str]
    if isinstance(raw_paths, list):
        paths = [str(p) for p in raw_paths if str(p).strip()]
    elif isinstance(raw_paths, str) and raw_paths.strip():
        paths = [raw_paths.strip()]
    else:
        paths = []
    return Config(external_skill_paths=paths)


def load_config(base: Path) -> Config:
    """Load configuration for the project at ``base``.

    Returns an empty :class:`Config` when no config file exists or it cannot be
    read, so callers can always rely on a usable object.
    """
    path = config_path(base)
    if not path.is_file():
        return Config()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return Config()
    return parse_config(text)


def load_mapping(base: Path) -> dict[str, object]:
    """Return the full parsed config as a plain dict (tolerant; never raises).

    This is the generic, key-agnostic view of the config file. It lets feature
    modules read their own keys without :class:`Config` having to know about
    them, keeping configuration decoupled from any particular feature. Returns an
    empty dict when the file is absent or unreadable.
    """
    path = config_path(base)
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    return _parse(text)
