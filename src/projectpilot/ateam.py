"""Inspection and (opt-in) installation of the local A-team environment.

This module powers ``pp doctor`` and ``pp setup ateam``.

The inspection/planning half (:func:`inspect_env`, :func:`discover_sources`,
:func:`plan_install`) is fully read-only: it discovers where an A-team
installation lives (or could be installed from) and describes what a future
install would involve, touching nothing.

The apply half (:func:`backup_existing`, :func:`apply_ateam`) is reached only
via ``pp setup ateam --apply``. It is *additive and non-destructive*: it always
takes a timestamped backup first, only ever creates directories or copies files
in, never deletes anything, never overwrites differing content (it writes a
sidecar and flags a conflict instead), and never modifies an existing
``settings.json``. It writes only under the target ``<home>/.claude`` and never
touches the source (e.g. ``00_Base``).
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .config import load_mapping

#: Sub-directories an A-team install populates under ``~/.claude``.
ATEAM_CATEGORIES = ("skills", "agents", "commands")

#: Strongest deterministic signal that the A-team is installed: the meta-skill.
ATEAM_SIGNAL_SKILL = "using-a-team"

#: Superpowers is a valid global skills set, but it is not the same thing as a
#: complete A-team install.
SUPERPOWERS_SIGNAL_SKILL = "using-superpowers"

#: Config key (in ``.project-pilot/config.yaml``): a list of source locations
#: that replaces :data:`DEFAULT_SOURCE_CANDIDATES`. Entries are resolved
#: against ``home`` unless absolute.
SOURCE_PATHS_KEY = "ateam_source_paths"

#: Where a copyable A-team source might live, expressed relative to ``$HOME``.
#: These defaults reflect one example layout (a ``00_Base`` template folder);
#: point :data:`SOURCE_PATHS_KEY` at your own locations to override them. The
#: ``.claude`` directly under home is the *target*, not a source, and is
#: handled separately by inspect_env.
DEFAULT_SOURCE_CANDIDATES = (
    Path("00_Base") / ".claude",
    Path("Desktop") / "Projetos" / "00_Base" / ".claude",
    Path("Projetos") / "00_Base" / ".claude",
)


def source_candidates(base: Path) -> tuple[Path, ...]:
    """Return the source search locations configured for the project at ``base``.

    Reads the :data:`SOURCE_PATHS_KEY` list from ``.project-pilot/config.yaml``;
    when the key is absent or empty, :data:`DEFAULT_SOURCE_CANDIDATES` applies.
    Entries may be absolute or ``home``-relative (resolution against home
    happens in :func:`discover_sources`). Read-only.
    """
    raw = load_mapping(Path(base)).get(SOURCE_PATHS_KEY)
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return DEFAULT_SOURCE_CANDIDATES
    configured = tuple(Path(item) for item in raw if str(item).strip())
    return configured or DEFAULT_SOURCE_CANDIDATES


def claude_home(home: Path) -> Path:
    return Path(home) / ".claude"


def _nonempty_dir(path: Path) -> bool:
    return path.is_dir() and any(path.iterdir())


def _count_entries(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for _ in path.iterdir())


def _category_status(path: Path) -> str:
    if not path.is_dir():
        return "missing"
    if _count_entries(path) == 0:
        return "empty"
    return "present"


def _detect_skill(skills_dir: Path, name: str) -> bool:
    if not skills_dir.is_dir():
        return False
    if (skills_dir / name).exists():
        return True
    for marker in (skills_dir / "SKILL.md", skills_dir / name / "SKILL.md"):
        if not marker.is_file():
            continue
        try:
            if name in marker.read_text(encoding="utf-8"):
                return True
        except OSError:
            continue
    return False


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
    category_counts: dict[str, int]
    category_status: dict[str, str]  # category -> missing|empty|present
    global_skills_count: int
    settings_json: bool
    ateam_signal: bool            # the using-a-team skill is present
    superpowers_detected: bool    # the using-superpowers skill/content is present
    ateam_full_install: bool      # every A-team category has content
    install_status: str           # not installed|partial|complete
    missing_categories: list[str]
    ateam_likely: bool            # legacy alias for ateam_full_install


def inspect_env(home: Path) -> ClaudeEnv:
    """Inspect ``<home>/.claude`` without modifying anything."""
    home = Path(home)
    root = claude_home(home)
    categories = {c: (root / c).is_dir() for c in ATEAM_CATEGORIES}
    category_counts = {c: _count_entries(root / c) for c in ATEAM_CATEGORIES}
    category_status = {c: _category_status(root / c) for c in ATEAM_CATEGORIES}
    signal = _detect_skill(root / "skills", ATEAM_SIGNAL_SKILL)
    superpowers = _detect_skill(root / "skills", SUPERPOWERS_SIGNAL_SKILL)
    populated = all(category_status[c] == "present" for c in ATEAM_CATEGORIES)
    present = [c for c in ATEAM_CATEGORIES if category_status[c] == "present"]
    if populated:
        install_status = "complete"
    elif present:
        install_status = "partial"
    else:
        install_status = "not installed"
    missing_categories = [c for c in ATEAM_CATEGORIES if category_status[c] != "present"]
    return ClaudeEnv(
        home=home,
        root=root,
        root_exists=root.exists(),
        categories=categories,
        category_counts=category_counts,
        category_status=category_status,
        global_skills_count=category_counts["skills"],
        settings_json=(root / "settings.json").is_file(),
        ateam_signal=signal,
        superpowers_detected=superpowers,
        ateam_full_install=populated,
        install_status=install_status,
        missing_categories=missing_categories,
        ateam_likely=populated,
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


# --------------------------------------------------------------------------- #
# Apply (opt-in via ``--apply``): additive, non-destructive installation.
# --------------------------------------------------------------------------- #

#: Suffix appended when an incoming entry differs from an existing one. The
#: existing entry is always preserved; the incoming copy lands beside it.
CONFLICT_SUFFIX = ".projectpilot-new"


def compact_stamp(iso_timestamp: str) -> str:
    """Turn an ISO clock string into a filesystem-safe stamp.

    ``"2026-06-26T10:00:00Z"`` -> ``"20260626-100000"``. Derives the stamp from
    the same injectable clock the rest of the CLI uses, so backup directory
    names are deterministic under test.
    """
    digits = "".join(ch for ch in iso_timestamp if ch.isdigit())
    date = (digits[:8] or "00000000").ljust(8, "0")
    time = (digits[8:14] or "000000").ljust(6, "0")
    return f"{date}-{time}"


def _same_content(a: Path, b: Path) -> bool:
    """True if ``a`` and ``b`` are byte-identical files or identical trees."""
    if a.is_file() and b.is_file():
        return a.read_bytes() == b.read_bytes()
    if a.is_dir() and b.is_dir():
        a_names = sorted(p.name for p in a.iterdir())
        b_names = sorted(p.name for p in b.iterdir())
        if a_names != b_names:
            return False
        return all(_same_content(a / name, b / name) for name in a_names)
    return False  # type mismatch (file vs dir) -> treat as different


def _copy_entry(src: Path, dst: Path) -> None:
    """Copy a file or a directory tree. Never deletes; never follows into dst."""
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def backup_existing(home: Path, stamp: str) -> tuple[Path | None, list[str]]:
    """Snapshot existing A-team content under ``<home>/.claude`` before any write.

    Copies whichever of ``skills`` / ``agents`` / ``commands`` / ``settings.json``
    exist into ``<home>/.claude/backups/projectpilot-ateam-<stamp>/``. Returns
    ``(backup_dir, backed_up_names)``; if there was nothing to back up, returns
    ``(None, [])`` and creates nothing.
    """
    target = claude_home(home)
    categories = [c for c in ATEAM_CATEGORIES if (target / c).is_dir()]
    has_settings = (target / "settings.json").is_file()
    if not categories and not has_settings:
        return None, []

    backup_dir = target / "backups" / f"projectpilot-ateam-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backed_up: list[str] = []
    for category in categories:
        shutil.copytree(target / category, backup_dir / category)
        backed_up.append(category)
    if has_settings:
        shutil.copy2(target / "settings.json", backup_dir / "settings.json")
        backed_up.append("settings.json")
    return backup_dir, backed_up


@dataclass
class ApplyItem:
    category: str
    name: str
    status: str          # "copied" | "unchanged" | "conflict"
    detail: str = ""


@dataclass
class ApplyResult:
    source: Path
    target: Path
    backup_dir: Path | None
    backed_up: list[str]
    created_dirs: list[str]
    items: list[ApplyItem] = field(default_factory=list)
    settings_status: str = "absent-in-source"  # copied|unchanged|preserved|absent-in-source

    @property
    def copied(self) -> list[ApplyItem]:
        return [i for i in self.items if i.status == "copied"]

    @property
    def unchanged(self) -> list[ApplyItem]:
        return [i for i in self.items if i.status == "unchanged"]

    @property
    def conflicts(self) -> list[ApplyItem]:
        return [i for i in self.items if i.status == "conflict"]


def apply_ateam(source: Path, home: Path, *, stamp: str) -> ApplyResult:
    """Install recognized A-team content from ``source`` into ``<home>/.claude``.

    Additive and non-destructive: backs up first, creates missing directories,
    copies new entries, leaves identical entries untouched (``unchanged``), and
    for differing entries preserves the existing one while writing a sidecar
    copy (``conflict``). An existing ``settings.json`` is never modified.
    """
    source = Path(source)
    target = claude_home(home)

    backup_dir, backed_up = backup_existing(home, stamp)

    created_dirs: list[str] = []
    if not target.exists():
        created_dirs.append(".claude")
    target.mkdir(parents=True, exist_ok=True)
    for category in ATEAM_CATEGORIES:
        cat_dir = target / category
        if not cat_dir.exists():
            created_dirs.append(f".claude/{category}")
        cat_dir.mkdir(parents=True, exist_ok=True)

    result = ApplyResult(
        source=source,
        target=target,
        backup_dir=backup_dir,
        backed_up=backed_up,
        created_dirs=created_dirs,
    )

    for category in ATEAM_CATEGORIES:
        src_cat = source / category
        if not src_cat.is_dir():
            continue
        for entry in sorted(src_cat.iterdir(), key=lambda p: p.name):
            dst = target / category / entry.name
            if not dst.exists():
                _copy_entry(entry, dst)
                result.items.append(ApplyItem(category, entry.name, "copied"))
            elif _same_content(entry, dst):
                result.items.append(ApplyItem(category, entry.name, "unchanged"))
            else:
                sidecar = target / category / f"{entry.name}{CONFLICT_SUFFIX}"
                if sidecar.exists():
                    sidecar = target / category / f"{entry.name}{CONFLICT_SUFFIX}-{stamp}"
                _copy_entry(entry, sidecar)
                result.items.append(
                    ApplyItem(
                        category,
                        entry.name,
                        "conflict",
                        f"kept existing; wrote {sidecar.name}",
                    )
                )

    src_settings = source / "settings.json"
    dst_settings = target / "settings.json"
    if not src_settings.is_file():
        result.settings_status = "absent-in-source"
    elif not dst_settings.is_file():
        shutil.copy2(src_settings, dst_settings)
        result.settings_status = "copied"
    elif _same_content(src_settings, dst_settings):
        result.settings_status = "unchanged"
    else:
        # Conservative: an existing, differing settings.json is left untouched.
        result.settings_status = "preserved"

    return result
