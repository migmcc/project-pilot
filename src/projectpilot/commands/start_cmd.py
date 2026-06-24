"""``pp start --idea <path>`` -- read an idea file, init state, run the autopilot."""
from __future__ import annotations

from pathlib import Path

from ..autopilot import drive, summary_lines
from ..phases import Phase
from ..state import Clock, ProjectState, load_state, save_state, state_exists
from .init_cmd import slugify


def run_start(args, *, clock: Clock) -> int:
    base = Path(args.dir)
    idea_path = Path(args.idea)
    if not idea_path.exists():
        print(f"Idea file not found: {idea_path}")
        return 1
    idea_text = idea_path.read_text(encoding="utf-8").strip()

    if state_exists(base) and not args.force:
        state = load_state(base)
        if not state.idea_source:
            state.idea_source = str(idea_path)
            state.updated_at = clock()
            save_state(base, state)
        print("Existing state found; continuing without overwriting.")
    else:
        now = clock()
        name = args.name or "Untitled project"
        slug = slugify(name)
        state = ProjectState(
            name=name,
            slug=slug,
            idea=idea_text,
            created_at=now,
            updated_at=now,
            idea_source=str(idea_path),
            current_phase=Phase.IDEA,
            history=[{"event": "start", "phase": Phase.IDEA.value, "timestamp": now}],
        )
        save_state(base, state)

    result = drive(base, clock=clock)
    for line in summary_lines(result):
        print(line)
    return 0
