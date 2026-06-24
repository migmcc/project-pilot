"""``pp continue`` -- run the autopilot from the current state to the next gate."""
from __future__ import annotations

from pathlib import Path

from ..autopilot import drive, summary_lines
from ..state import Clock, state_exists


def run_continue(args, *, clock: Clock) -> int:
    base = Path(args.dir)
    if not state_exists(base):
        print('No ProjectPilot state found. Run `pp start --idea <path>` first.')
        return 1
    result = drive(base, clock=clock)
    for line in summary_lines(result):
        print(line)
    return 0
