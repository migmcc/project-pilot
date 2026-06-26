"""Read-only inspection of the local A-team environment.

This module powers ``pp doctor`` and ``pp setup ateam``. Everything here is
diagnostic: it discovers where an A-team installation lives (or could be
installed from) and describes what a future install would involve. It never
copies, writes, or deletes anything, and it never touches ``~/.claude``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: Sub-directories an A-team install populates under ``~/.claude``.
ATEAM_CATEGORIES = ("skills", "agents", "commands")

#: Strongest deterministic signal that the A-team is installed: the meta-skill.
ATEAM_SIGNAL_SKILL = "using-a-team"

#: Where a copyable A-team source might live, expressed relative to ``$HOME``.
#: ``00_Base`` is the user's known base template. The ``.claude`` directly under
#: home is the *target*, not a source, and is handled separately by inspect_env.
DEFAULT_SOURCE_CANDIDATES = (
    Path("00_Base") / ".claude",
    Path("Desktop") / "Projetos" / "00_Base" / ".claude",
    Path("Projetos") / "00_Base" / ".claude",
)


def claude_home(home: Path) -> Path:
    return Path(home) / ".claude"


def _nonempty_dir(path: Path) -> bool:
    return path.is_dir() and any(path.iterdir())


def _count_entries(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for _ in path.iterdir())


def looks_like_claude_dir(path: Path) -> bool:
    """True if ``path`` has at least one A-team category sub-directory."""
    path = Path(path)
    return any((path / category).is_dir() for category in ATEAM_CATEGORIES)


@dataclass
class ClaudeEnv:
    home: Path
    root: Path
    root_exists: bool
    categories: dict[str, bool]   # category -> directory present
    settings_json: bool
    ateam_signal: bool            # the using-a-team skill is present
    ateam_likely: bool            # signal, or every category is populated


def inspect_env(home: Path) -> ClaudeEnv:
    """Inspect ``<home>/.claude`` without modifying anything."""
    home = Path(home)
    root = claude_home(home)
    categories = {c: (root / c).is_dir() for c in ATEAM_CATEGORIES}
    signal = (root / "skills" / ATEAM_SIGNAL_SKILL).exists()
    populated = all(_nonempty_dir(root / c) for c in ATEAM_CATEGORIES)
    return ClaudeEnv(
        home=home,
        root=root,
        root_exists=root.exists(),
        categories=categories,
        settings_json=(root / "settings.json").is_file(),
        ateam_signal=signal,
        ateam_likely=signal or populated,
    )


def discover_sources(home: Path, candidates=DEFAULT_SOURCE_CANDIDATES) -> list[Path]:
    """Return existing candidate source directories that look like a ``.claude``."""
    home = Path(home)
    found: list[Path] = []
    for rel in candidates:
        path = home / rel
        if looks_like_claude_dir(path):
            found.append(path)
    return found


@dataclass
class CategoryPlan:
    category: str
    source_count: int        # entries available in the source
    target_present: bool     # target already has non-empty content
    conflict: bool           # installing would overwrite existing content


@dataclass
class InstallPlan:
    source: Path
    target: Path
    categories: list[CategoryPlan]
    source_settings: bool
    target_settings: bool
    settings_conflict: bool

    @property
    def conflicts(self) -> list[str]:
        items = [c.category for c in self.categories if c.conflict]
        if self.settings_conflict:
            items.append("settings.json")
        return items


def plan_install(source: Path, home: Path) -> InstallPlan:
    """Describe what installing ``source`` into ``<home>/.claude`` would require.

    This computes counts and conflicts only; it performs no copy.
    """
    source = Path(source)
    target = claude_home(home)
    categories: list[CategoryPlan] = []
    for category in ATEAM_CATEGORIES:
        source_count = _count_entries(source / category)
        target_present = _nonempty_dir(target / category)
        categories.append(
            CategoryPlan(
                category=category,
                source_count=source_count,
                target_present=target_present,
                conflict=source_count > 0 and target_present,
            )
        )
    source_settings = (source / "settings.json").is_file()
    target_settings = (target / "settings.json").is_file()
    return InstallPlan(
        source=source,
        target=target,
        categories=categories,
        source_settings=source_settings,
        target_settings=target_settings,
        settings_conflict=source_settings and target_settings,
    )
