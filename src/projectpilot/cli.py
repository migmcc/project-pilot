"""Deterministic ``pp`` command-line interface."""
from __future__ import annotations

import argparse
from typing import Sequence

from .commands.advance_cmd import run_advance
from .commands.brief_cmd import run_brief_import
from .commands.decision_cmd import run_decision_set
from .commands.init_cmd import run_init
from .commands.status_cmd import run_status
from .commands.validate_cmd import run_validate
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

    p_validate = subparsers.add_parser(
        "validate", help="Run internal pre-checks and emit the SkillLab prompt."
    )
    p_validate.add_argument("--dir", default=".", help="Project directory (default: current).")

    p_decision = subparsers.add_parser(
        "decision", help="Record a manual SkillLab decision."
    )
    decision_subparsers = p_decision.add_subparsers(dest="decision_command", required=True)
    p_decision_set = decision_subparsers.add_parser(
        "set", help="Record a manual decision without advancing the phase."
    )
    p_decision_set.add_argument(
        "decision", choices=("APPROVED", "NEEDS_REWORK", "REJECTED")
    )
    p_decision_set.add_argument("--reason", required=True, help="Decision rationale.")
    p_decision_set.add_argument(
        "--dir", default=".", help="Project directory (default: current)."
    )

    p_advance = subparsers.add_parser(
        "advance", help="Advance to the next phase when its gate is satisfied."
    )
    p_advance.add_argument("target", choices=("brief",))
    p_advance.add_argument("--dir", default=".", help="Project directory (default: current).")

    p_brief = subparsers.add_parser(
        "brief", help="Import an externally produced Project Brief."
    )
    brief_subparsers = p_brief.add_subparsers(dest="brief_command", required=True)
    p_brief_import = brief_subparsers.add_parser(
        "import", help="Copy an existing brief into the project."
    )
    p_brief_import.add_argument("path", help="Path to the brief produced outside ProjectPilot.")
    p_brief_import.add_argument(
        "--force", action="store_true", help="Replace an existing PROJECT_BRIEF.md."
    )
    p_brief_import.add_argument(
        "--dir", default=".", help="Project directory (default: current)."
    )

    return parser


def main(argv: Sequence[str] | None = None, *, clock: Clock = utc_now_iso) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        return run_init(args, clock=clock)
    if args.command == "status":
        return run_status(args)
    if args.command == "validate":
        return run_validate(args, clock=clock)
    if args.command == "decision" and args.decision_command == "set":
        return run_decision_set(args, clock=clock)
    if args.command == "advance":
        return run_advance(args, clock=clock)
    if args.command == "brief" and args.brief_command == "import":
        return run_brief_import(args, clock=clock)
    parser.error(f"unknown command: {args.command!r}")  # pragma: no cover
    return 2  # pragma: no cover
