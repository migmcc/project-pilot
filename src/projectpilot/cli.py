"""Deterministic ``pp`` command-line interface (Run A: ``init`` and ``status``)."""
from __future__ import annotations

import argparse
from typing import Sequence

from .commands.init_cmd import run_init
from .commands.status_cmd import run_status
from .state import Clock, utc_now_iso


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pp",
        description="ProjectPilot - local lifecycle orchestrator (Run A foundation).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_init = subparsers.add_parser("init", help="Initialize a new project state.")
    p_init.add_argument("idea", help="The project idea, in quotes.")
    p_init.add_argument("--name", default=None, help="Human-readable project name.")
    p_init.add_argument("--slug", default=None, help="Explicit slug (default: from name).")
    p_init.add_argument("--dir", default=".", help="Project directory (default: current).")
    p_init.add_argument(
        "--force", action="store_true", help="Overwrite existing state."
    )

    p_status = subparsers.add_parser(
        "status", help="Show the current phase and next action (read-only)."
    )
    p_status.add_argument("--dir", default=".", help="Project directory (default: current).")

    return parser


def main(argv: Sequence[str] | None = None, *, clock: Clock = utc_now_iso) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        return run_init(args, clock=clock)
    if args.command == "status":
        return run_status(args)
    parser.error(f"unknown command: {args.command!r}")  # pragma: no cover
    return 2  # pragma: no cover
