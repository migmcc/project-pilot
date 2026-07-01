"""Deterministic ``pp`` command-line interface.

Transition policy (see README): commands that only *record* information do not
advance the phase (``decision set``); ``advance brief`` is an explicit gated
transition; commands that *complete* a phase's gate may advance the phase
(``brief import``, ``advise-setup``, ``execution approve``).
"""
from __future__ import annotations

import argparse
import sys
from typing import Sequence

from .commands.advance_cmd import run_advance
from .commands.analyze_cmd import run_analyze
from .commands.approve_cmd import run_approve
from .commands.artifact_cmd import run_artifact
from .commands.brief_cmd import run_brief_import
from .commands.continue_cmd import run_continue
from .commands.check_ateam_cmd import run_check_ateam
from .commands.dashboard_cmd import run_dashboard
from .commands.decision_cmd import run_decision_set
from .commands.doctor_cmd import run_doctor
from .commands.done_cmd import run_done_approve
from .commands.execution_cmd import run_execution_approve
from .commands.final_validation_cmd import run_final_validation_prepare
from .commands.init_cmd import run_init
from .commands.next_cmd import run_next
from .commands.phase_cmd import run_phase_check
from .commands.setup_advice_cmd import run_advise_setup
from .commands.setup_cmd import run_setup_ateam
from .commands.skill_cmd import (
    run_skill_info,
    run_skill_list,
    run_skill_recommend,
    run_skill_run,
    run_skill_sources,
    run_skill_use,
)
from .commands.start_cmd import run_start
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

    p_next = subparsers.add_parser(
        "next", help="Workflow advisor: suggest the next logical step (advice only)."
    )
    p_next.add_argument("--dir", default=".", help="Project directory (default: current).")
    p_next.add_argument("--json", action="store_true", help="Emit deterministic JSON.")
    p_next.add_argument(
        "--verbose", action="store_true", help="Include each recommendation's dependencies."
    )

    p_dashboard = subparsers.add_parser(
        "dashboard", help="Aggregated project overview (read-only)."
    )
    p_dashboard.add_argument("--dir", default=".", help="Project directory (default: current).")
    p_dashboard.add_argument("--json", action="store_true", help="Emit deterministic JSON.")
    p_dashboard.add_argument(
        "--verbose",
        action="store_true",
        help="Include requirements, advisor reasoning, and artifact metadata.",
    )

    p_artifact = subparsers.add_parser(
        "artifact", help="Register externally produced workflow evidence."
    )
    artifact_subparsers = p_artifact.add_subparsers(
        dest="artifact_command", required=True
    )
    p_artifact_add = artifact_subparsers.add_parser(
        "add", help="Register artifact metadata without copying the file."
    )
    p_artifact_add.add_argument("file", help="Artifact file to register.")
    p_artifact_add.add_argument(
        "--dir", default=".", help="Project directory (default: current)."
    )

    p_artifact_list = artifact_subparsers.add_parser(
        "list", help="List registered artifacts."
    )
    p_artifact_list.add_argument("--json", action="store_true", help="Emit deterministic JSON.")
    p_artifact_list.add_argument(
        "--dir", default=".", help="Project directory (default: current)."
    )

    p_artifact_show = artifact_subparsers.add_parser(
        "show", help="Show full metadata for one artifact."
    )
    p_artifact_show.add_argument("id", help="Artifact id.")
    p_artifact_show.add_argument(
        "--dir", default=".", help="Project directory (default: current)."
    )

    p_artifact_remove = artifact_subparsers.add_parser(
        "remove", help="Remove an artifact inventory entry only."
    )
    p_artifact_remove.add_argument("id", help="Artifact id.")
    p_artifact_remove.add_argument(
        "--dir", default=".", help="Project directory (default: current)."
    )

    p_phase = subparsers.add_parser(
        "phase", help="Inspect phase artifact requirements and completion (read-only)."
    )
    phase_subparsers = p_phase.add_subparsers(dest="phase_command", required=True)
    p_phase_check = phase_subparsers.add_parser(
        "check", help="Report satisfied/missing requirements for the current phase."
    )
    p_phase_check.add_argument("--dir", default=".", help="Project directory (default: current).")
    p_phase_check.add_argument("--json", action="store_true", help="Emit deterministic JSON.")
    p_phase_check.add_argument(
        "--verbose", action="store_true", help="Also list optional requirements."
    )

    p_start = subparsers.add_parser(
        "start", help="Read an idea file, initialize state, and run the autopilot."
    )
    p_start.add_argument("--idea", required=True, help="Path to the idea file (e.g. idea.md).")
    p_start.add_argument("--name", default=None, help="Human-readable project name.")
    p_start.add_argument("--dir", default=".", help="Project directory (default: current).")
    p_start.add_argument(
        "--force", action="store_true", help="Re-initialize state from the idea file."
    )

    p_continue = subparsers.add_parser(
        "continue", help="Run the autopilot from the current state to the next human gate."
    )
    p_continue.add_argument("--dir", default=".", help="Project directory (default: current).")

    p_doctor = subparsers.add_parser(
        "doctor", help="Report on the local environment (read-only; changes nothing)."
    )
    p_doctor.add_argument("--dir", default=".", help="Project directory (default: current).")
    p_doctor.add_argument("--home", default=None, help=argparse.SUPPRESS)

    p_analyze = subparsers.add_parser(
        "analyze", help="Inspect the project stack/state and suggest the next action."
    )
    p_analyze.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Project directory (positional alias for --dir; default: current).",
    )
    p_analyze.add_argument(
        "--dir",
        default=None,
        help="Project directory (default: current). Cannot be combined with the positional path.",
    )

    p_setup = subparsers.add_parser(
        "setup", help="A-team setup: diagnose (default) or install (--apply)."
    )
    setup_subparsers = p_setup.add_subparsers(dest="setup_command", required=True)
    p_setup_ateam = setup_subparsers.add_parser(
        "ateam",
        help="Diagnose A-team setup (dry-run); use --apply to install into ~/.claude.",
    )
    p_setup_ateam.add_argument(
        "--apply",
        action="store_true",
        help="Install into ~/.claude (additive; backs up first; never overwrites).",
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

    p_approve = subparsers.add_parser(
        "approve", help="Friendly approval aliases (record/advance human gates)."
    )
    approve_subparsers = p_approve.add_subparsers(dest="approve_command", required=True)

    a_decision = approve_subparsers.add_parser(
        "decision", help="Alias for `decision set` (records only; does not advance)."
    )
    a_decision.add_argument("decision", choices=("APPROVED", "NEEDS_REWORK", "REJECTED"))
    a_decision.add_argument("--reason", required=True, help="Decision rationale.")
    a_decision.add_argument("--dir", default=".", help="Project directory (default: current).")

    a_execution = approve_subparsers.add_parser(
        "execution", help="Alias for `execution approve` (advances planning -> execution)."
    )
    a_execution.add_argument("--reason", required=True, help="Approval reason.")
    a_execution.add_argument(
        "--override",
        action="store_true",
        help="Approve even when A-team readiness is not complete.",
    )
    a_execution.add_argument("--dir", default=".", help="Project directory (default: current).")

    a_done = approve_subparsers.add_parser(
        "done", help="Alias for `done approve` (advances final-validation -> done)."
    )
    a_done.add_argument("--reason", required=True, help="Closure reason.")
    a_done.add_argument("--dir", default=".", help="Project directory (default: current).")

    p_skill = subparsers.add_parser(
        "skill", help="Discover and use external libraries of skills (read-only)."
    )
    skill_subparsers = p_skill.add_subparsers(dest="skill_command", required=True)

    s_sources = skill_subparsers.add_parser(
        "sources", help="Show the configured external skill paths."
    )
    s_sources.add_argument("--dir", default=".", help="Project directory (default: current).")

    s_list = skill_subparsers.add_parser(
        "list", help="List skills discovered in the configured sources."
    )
    s_list.add_argument("--dir", default=".", help="Project directory (default: current).")

    s_info = skill_subparsers.add_parser(
        "info", help="Show details for one skill."
    )
    s_info.add_argument("skill_id", help="The skill id (see `pp skill list`).")
    s_info.add_argument("--dir", default=".", help="Project directory (default: current).")

    s_run = skill_subparsers.add_parser(
        "run", help="Prepare a skill as reusable context (no LLM is called)."
    )
    s_run.add_argument("skill_id", help="The skill id (see `pp skill list`).")
    s_run.add_argument(
        "--print",
        action="store_true",
        help="Print the rendered skill to stdout instead of writing a file.",
    )
    s_run.add_argument("--dir", default=".", help="Project directory (default: current).")

    s_recommend = skill_subparsers.add_parser(
        "recommend",
        help="Suggest skills relevant to the current lifecycle phase (no LLM).",
    )
    s_recommend.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of recommendations to show (default: 10; 0 for all).",
    )
    s_recommend.add_argument("--dir", default=".", help="Project directory (default: current).")

    s_use = skill_subparsers.add_parser(
        "use",
        help="Wizard: pick a skill and build a consolidated prompt (no LLM, no execution).",
    )
    s_use.add_argument(
        "skill_id",
        nargs="?",
        default=None,
        help="Skill id to use; omit to choose from the current phase's recommendations.",
    )
    s_use.add_argument(
        "--output",
        default=None,
        help="Write the prompt to this path instead of projectpilot_outputs/prompts/.",
    )
    s_use.add_argument(
        "--print",
        action="store_true",
        help="Print the prompt to stdout instead of writing a file.",
    )
    s_use.add_argument("--dir", default=".", help="Project directory (default: current).")

    return parser


def _make_output_resilient() -> None:
    """Make stdout/stderr tolerate content the console encoding can't represent.

    External skill libraries may contain arbitrary Unicode (emoji, symbols) that a
    legacy console (e.g. Windows ``cp1252``) cannot encode, which would otherwise
    raise ``UnicodeEncodeError`` mid-print. Switching the error handler to
    ``replace`` keeps the console's own encoding but degrades unencodable
    characters instead of crashing. Guarded: streams without ``reconfigure``
    (such as the ``StringIO`` used in tests) are left untouched.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except (ValueError, OSError):  # pragma: no cover - stream already detached
            pass


def main(argv: Sequence[str] | None = None, *, clock: Clock = utc_now_iso) -> int:
    _make_output_resilient()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        return run_init(args, clock=clock)
    if args.command == "status":
        return run_status(args)
    if args.command == "next":
        return run_next(args)
    if args.command == "dashboard":
        return run_dashboard(args)
    if args.command == "artifact":
        return run_artifact(args, clock=clock)
    if args.command == "phase" and args.phase_command == "check":
        return run_phase_check(args)
    if args.command == "start":
        return run_start(args, clock=clock)
    if args.command == "continue":
        return run_continue(args, clock=clock)
    if args.command == "doctor":
        return run_doctor(args)
    if args.command == "analyze":
        return run_analyze(args)
    if args.command == "setup" and args.setup_command == "ateam":
        return run_setup_ateam(args, clock=clock)
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
    if args.command == "approve":
        return run_approve(args, clock=clock)
    if args.command == "skill":
        if args.skill_command == "sources":
            return run_skill_sources(args)
        if args.skill_command == "list":
            return run_skill_list(args)
        if args.skill_command == "info":
            return run_skill_info(args)
        if args.skill_command == "run":
            return run_skill_run(args)
        if args.skill_command == "recommend":
            return run_skill_recommend(args)
        if args.skill_command == "use":
            return run_skill_use(args)
    parser.error(f"unknown command: {args.command!r}")  # pragma: no cover
    return 2  # pragma: no cover
