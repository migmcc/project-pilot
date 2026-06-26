"""Deterministic ``pp`` command-line interface.

Transition policy (see README): commands that only *record* information do not
advance the phase (``decision set``); ``advance brief`` is an explicit gated
transition; commands that *complete* a phase's gate may advance the phase
(``brief import``, ``advise-setup``, ``execution approve``).
"""
from __future__ import annotations

import argparse
from typing import Sequence

from .commands.advance_cmd import run_advance
from .commands.analyze_cmd import run_analyze
from .commands.brief_cmd import run_brief_import
from .commands.check_ateam_cmd import run_check_ateam
from .commands.decision_cmd import run_decision_set
from .commands.doctor_cmd import run_doctor
from .commands.done_cmd import run_done_approve
from .commands.execution_cmd import run_execution_approve
from .commands.final_validation_cmd import run_final_validation_prepare
from .commands.init_cmd import run_init
from .commands.setup_advice_cmd import run_advise_setup
from .commands.setup_cmd import run_setup_ateam
from .commands.status_cmd import run_status
from .commands.validate_cmd import run_validate
from .state import Clock, utc_now_iso


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pp",
        description="ProjectPilot lifecycle orchestrator",
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

    p_doctor = subparsers.add_parser(
        "doctor", help="Report on the local environment (read-only; changes nothing)."
    )
    p_doctor.add_argument("--dir", default=".", help="Project directory (default: current).")
    p_doctor.add_argument("--home", default=None, help=argparse.SUPPRESS)

    p_analyze = subparsers.add_parser(
        "analyze", help="Inspect the project stack/state and suggest the next action."
    )
    p_analyze.add_argument("--dir", default=".", help="Project directory (default: current).")

    p_setup = subparsers.add_parser(
        "setup", help="Diagnostic setup helpers (dry-run; changes nothing in v0.1)."
    )
    setup_subparsers = p_setup.add_subparsers(dest="setup_command", required=True)
    p_setup_ateam = setup_subparsers.add_parser(
        "ateam", help="Dry-run plan for installing the A-team into ~/.claude."
    )
    p_setup_ateam.add_argument("--home", default=None, help=argparse.SUPPRESS)

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

    p_advise_setup = subparsers.add_parser(
        "advise-setup", help="Prepare deterministic manual setup advice."
    )
    p_advise_setup.add_argument(
        "--dir", default=".", help="Project directory (default: current)."
    )

    p_check_ateam = subparsers.add_parser(
        "check-ateam", help="Check expected A-team files without changing them."
    )
    p_check_ateam.add_argument(
        "--dir", default=".", help="Project directory (default: current)."
    )

    p_execution = subparsers.add_parser(
        "execution", help="Manage the manual execution gate."
    )
    execution_subparsers = p_execution.add_subparsers(
        dest="execution_command", required=True
    )
    p_execution_approve = execution_subparsers.add_parser(
        "approve", help="Manually approve the move from planning to execution."
    )
    p_execution_approve.add_argument("--reason", required=True, help="Approval reason.")
    p_execution_approve.add_argument(
        "--override",
        action="store_true",
        help="Approve even when A-team readiness is not complete.",
    )
    p_execution_approve.add_argument(
        "--dir", default=".", help="Project directory (default: current)."
    )

    p_final_validation = subparsers.add_parser(
        "final-validation", help="Manage the final-validation gate."
    )
    final_validation_subparsers = p_final_validation.add_subparsers(
        dest="final_validation_command", required=True
    )
    p_final_validation_prepare = final_validation_subparsers.add_parser(
        "prepare", help="Prepare the manual final-validation checklist."
    )
    p_final_validation_prepare.add_argument(
        "--dir", default=".", help="Project directory (default: current)."
    )

    p_done = subparsers.add_parser("done", help="Manage the done gate.")
    done_subparsers = p_done.add_subparsers(dest="done_command", required=True)
    p_done_approve = done_subparsers.add_parser(
        "approve", help="Manually close the lifecycle (advance to 'done')."
    )
    p_done_approve.add_argument("--reason", required=True, help="Closure reason.")
    p_done_approve.add_argument(
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
    if args.command == "doctor":
        return run_doctor(args)
    if args.command == "analyze":
        return run_analyze(args)
    if args.command == "setup" and args.setup_command == "ateam":
        return run_setup_ateam(args)
    if args.command == "validate":
        return run_validate(args, clock=clock)
    if args.command == "decision" and args.decision_command == "set":
        return run_decision_set(args, clock=clock)
    if args.command == "advance":
        return run_advance(args, clock=clock)
    if args.command == "brief" and args.brief_command == "import":
        return run_brief_import(args, clock=clock)
    if args.command == "advise-setup":
        return run_advise_setup(args, clock=clock)
    if args.command == "check-ateam":
        return run_check_ateam(args, clock=clock)
    if args.command == "execution" and args.execution_command == "approve":
        return run_execution_approve(args, clock=clock)
    if args.command == "final-validation" and args.final_validation_command == "prepare":
        return run_final_validation_prepare(args, clock=clock)
    if args.command == "done" and args.done_command == "approve":
        return run_done_approve(args, clock=clock)
    parser.error(f"unknown command: {args.command!r}")  # pragma: no cover
    return 2  # pragma: no cover
