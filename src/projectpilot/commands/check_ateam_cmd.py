"""``pp check-ateam`` -- read-only A-team readiness check."""
from __future__ import annotations

from pathlib import Path

from ..errors import StateNotFoundError
from ..phases import Phase
from ..state import Clock, load_state, save_state

REQUIRED_PATHS = [
    "INIT.md",
    ".agent-sync",
    ".agent-sync/TEAM.md",
    ".agent-sync/ROUTING.md",
]


def _path_exists(base: Path, rel_path: str) -> bool:
    path = base / rel_path
    if rel_path == ".agent-sync":
        return path.is_dir()
    return path.is_file()


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

    present = [path for path in REQUIRED_PATHS if _path_exists(base, path)]
    missing = [path for path in REQUIRED_PATHS if path not in present]
    ready = not missing
    now = clock()

    state.ateam_check = {
        "checked_at": now,
        "required_paths": list(REQUIRED_PATHS),
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
