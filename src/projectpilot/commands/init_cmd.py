"""``pp init`` — create the initial project lifecycle state."""
from __future__ import annotations

import re
from pathlib import Path

from ..phases import Phase
from ..state import Clock, ProjectState, save_state, state_exists, state_path


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "project"


def run_init(args, *, clock: Clock) -> int:
    base = Path(args.dir)
    if state_exists(base) and not args.force:
        print(f"State already exists at {state_path(base)}. Use --force to overwrite.")
        return 1

    name = args.name or "Untitled project"
    slug = args.slug or slugify(name)
    now = clock()
    state = ProjectState(
        name=name,
        slug=slug,
        idea=args.idea,
        created_at=now,
        updated_at=now,
        current_phase=Phase.IDEA,
        decision=None,
        history=[{"event": "init", "phase": Phase.IDEA.value, "timestamp": now}],
    )
    path = save_state(base, state)
    print(f"Initialized ProjectPilot project '{name}' ({slug}).")
    print(f"State: {path}")
    print(f"Current phase: {Phase.IDEA.value}")
    return 0
