"""``pp approve ...`` -- friendly aliases over the existing approval commands.

Reuses the v0.1 command logic (no new gate semantics), then refreshes the
autopilot coordination files from the resulting state (without advancing).
"""
from __future__ import annotations

from pathlib import Path

from ..autopilot import refresh
from ..state import Clock, state_exists
from .decision_cmd import run_decision_set
from .done_cmd import run_done_approve
from .execution_cmd import run_execution_approve


def run_approve(args, *, clock: Clock) -> int:
    if args.approve_command == "decision":
        rc = run_decision_set(args, clock=clock)
    elif args.approve_command == "execution":
        rc = run_execution_approve(args, clock=clock)
    elif args.approve_command == "done":
        rc = run_done_approve(args, clock=clock)
    else:  # pragma: no cover - argparse enforces the choices
        return 2

    if rc == 0 and state_exists(Path(args.dir)):
        refresh(Path(args.dir), clock=clock)
    return rc
