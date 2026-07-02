"""``pp check-ateam`` -- read-only execution-readiness check.

By default it checks the author's A-team convention (the paths below). Override
the convention per project with the ``ateam_readiness_paths`` list in
``.project-pilot/config.yaml``: entries ending in ``/`` must be directories,
all others must be files.
"""
from __future__ import annotations

from pathlib import Path

from ..config import load_mapping
from ..errors import StateNotFoundError
from ..phases import Phase
from ..state import Clock, load_state, save_state

#: Config key: replaces :data:`REQUIRED_PATHS` for the project.
READINESS_PATHS_KEY = "ateam_readiness_paths"

#: Default readiness convention (the A-team layout).
REQUIRED_PATHS = [
    "INIT.md",
    ".agent-sync",
    ".agent-sync/TEAM.md",
    ".agent-sync/ROUTING.md",
]


def readiness_paths(base: Path) -> list[str]:
    """Return the readiness paths configured for ``base``, or the defaults."""
    raw = load_mapping(Path(base)).get(READINESS_PATHS_KEY)
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return list(REQUIRED_PATHS)
    configured = [str(item).strip() for item in raw if str(item).strip()]
    return configured or list(REQUIRED_PATHS)


def _path_exists(base: Path, rel_path: str) -> bool:
    # A trailing slash marks a directory requirement; ``.agent-sync`` keeps its
    # historical directory semantics so existing recorded state stays identical.
    wants_dir = rel_path.endswith("/") or rel_path == ".agent-sync"
    path = base / rel_path.rstrip("/")
    return path.is_dir() if wants_dir else path.is_file()


def _render_paths(label: str, paths: list[str]) -> list[str]:
    if not paths:
        return [f"{label}: (none)"]
    return [f"{label}:", *[f"- {path}" for path in paths]]


def run_check_ateam(args, *, clock: Clock) -> int:
    base = Path(args.dir)
    try:
        state = load_state(base)
    except StateNotFoundError:
        print('No ProjectPilot state found. Run `pp init "<idea>"` first.')
        return 1

    if state.current_phase != Phase.PLANNING:
        print(
            "A-team readiness check is only available during the 'planning' phase; "
            f"current phase is '{state.current_phase.value}'."
        )
        return 1

    required = readiness_paths(base)
    present = [path for path in required if _path_exists(base, path)]
    missing = [path for path in required if path not in present]
    ready = not missing
    now = clock()

    state.ateam_check = {
        "checked_at": now,
        "required_paths": list(required),
        "present_paths": present,
        "missing_paths": missing,
        "ready": ready,
        "source": "read-only-filesystem",
    }
    state.updated_at = now
    state.history.append(
        {
            "event": "ateam_checked",
            "phase": Phase.PLANNING.value,
            "timestamp": now,
            "ready": ready,
        }
    )
    save_state(base, state)

    lines = [
        "A-team readiness check complete.",
        f"Ready: {'true' if ready else 'false'}",
        "",
        *_render_paths("Present paths", present),
        "",
        *_render_paths("Missing paths", missing),
    ]
    print("\n".join(lines))
    return 0
