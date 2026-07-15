"""Optional Graphify context discovery and prompt guidance.

This module never imports or executes Graphify. It reads ProjectPilot's small
configuration mapping, classifies the presence of expected local output files,
and renders deterministic advice for an external agent.
"""
from __future__ import annotations

import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .config import load_mapping

__all__ = [
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_QUERY_BUDGET",
    "STATE_DISABLED",
    "STATE_MISSING",
    "STATE_PARTIAL",
    "STATE_READY",
    "GraphContextStatus",
    "inspect_graph_context",
    "render_query_directive",
]

DEFAULT_OUTPUT_DIR = "graphify-out"
DEFAULT_QUERY_BUDGET = 1200
MIN_QUERY_BUDGET = 250
MAX_QUERY_BUDGET = 5000

STATE_DISABLED = "disabled"
STATE_MISSING = "missing"
STATE_PARTIAL = "partial"
STATE_READY = "ready"

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})
_MISSING = object()
_PATH_ERRORS = (ValueError, OSError, RuntimeError)
_SAFE_SKILL_PUNCTUATION = frozenset("-_./'")


class _OutputEntryState(Enum):
    ABSENT = "absent"
    SAFE_PRESENT = "safe-present"
    UNSAFE = "unsafe"


@dataclass(frozen=True)
class GraphContextStatus:
    """Deterministic snapshot of the optional external Graphify context."""

    enabled: bool
    state: str
    graph_path: str
    report_path: str
    query_budget: int
    diagnostics: tuple[str, ...] = ()
    output_path_usable: bool = True


def _enabled(value: object, diagnostics: list[str]) -> bool:
    if value is _MISSING:
        return False
    normalized = str(value).strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    diagnostics.append("graphify_enabled is invalid; using false.")
    return False


def _query_budget(value: object, diagnostics: list[str]) -> int:
    if value is _MISSING:
        return DEFAULT_QUERY_BUDGET
    try:
        budget = int(str(value).strip())
    except (TypeError, ValueError):
        budget = -1
    if MIN_QUERY_BUDGET <= budget <= MAX_QUERY_BUDGET:
        return budget
    diagnostics.append(
        "graphify_query_budget must be an integer from 250 through 5000; using 1200."
    )
    return DEFAULT_QUERY_BUDGET


def _output_directory(
    base: Path,
    value: object,
    diagnostics: list[str],
) -> tuple[Path | None, str, Path | None]:
    try:
        root = Path(base).resolve()
    except _PATH_ERRORS:
        diagnostics.append(
            "project directory cannot be resolved; Graphify outputs will not be inspected."
        )
        return None, DEFAULT_OUTPUT_DIR, None

    raw = DEFAULT_OUTPUT_DIR if value is _MISSING else value
    using_default = value is _MISSING
    if not isinstance(raw, str) or not raw.strip():
        diagnostics.append(
            "graphify_output_dir must be a non-empty path; using graphify-out."
        )
        raw = DEFAULT_OUTPUT_DIR
        using_default = True
    candidate = Path(raw.strip())
    unresolved = candidate if candidate.is_absolute() else root / candidate
    try:
        resolved = unresolved.resolve()
    except _PATH_ERRORS:
        if using_default:
            diagnostics.append(
                "default graphify-out directory cannot be resolved; "
                "outputs will not be inspected."
            )
            return None, DEFAULT_OUTPUT_DIR, root
        diagnostics.append(
            "graphify_output_dir cannot be resolved; using graphify-out."
        )
        return _fallback_output_directory(root, diagnostics)

    try:
        relative = resolved.relative_to(root)
    except ValueError:
        if using_default:
            diagnostics.append(
                "default graphify-out directory must stay inside the project; "
                "outputs will not be inspected."
            )
            return None, DEFAULT_OUTPUT_DIR, root
        diagnostics.append(
            "graphify_output_dir must stay inside the project; using graphify-out."
        )
        return _fallback_output_directory(root, diagnostics)
    return resolved, relative.as_posix(), root


def _fallback_output_directory(
    root: Path,
    diagnostics: list[str],
) -> tuple[Path | None, str, Path]:
    try:
        resolved = (root / DEFAULT_OUTPUT_DIR).resolve()
    except _PATH_ERRORS:
        diagnostics.append(
            "default graphify-out directory cannot be resolved; "
            "outputs will not be inspected."
        )
        return None, DEFAULT_OUTPUT_DIR, root
    try:
        resolved.relative_to(root)
    except ValueError:
        diagnostics.append(
            "default graphify-out directory must stay inside the project; "
            "outputs will not be inspected."
        )
        return None, DEFAULT_OUTPUT_DIR, root
    return resolved, DEFAULT_OUTPUT_DIR, root


def _inspect_output_entry(
    path: Path,
    *,
    label: str,
    root: Path,
    output_dir: Path,
    diagnostics: list[str],
) -> _OutputEntryState:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return _OutputEntryState.ABSENT
    except _PATH_ERRORS:
        diagnostics.append(
            f"Graphify {label} output could not be inspected; treating it as missing."
        )
        return _OutputEntryState.UNSAFE

    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    file_attributes = getattr(metadata, "st_file_attributes", 0)
    if not stat.S_ISREG(metadata.st_mode) or file_attributes & reparse_flag:
        diagnostics.append(
            f"Graphify {label} output is not a safe regular file; treating it as missing."
        )
        return _OutputEntryState.UNSAFE

    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
        resolved.relative_to(output_dir)
    except _PATH_ERRORS:
        diagnostics.append(
            f"Graphify {label} output could not be inspected; treating it as missing."
        )
        return _OutputEntryState.UNSAFE
    return _OutputEntryState.SAFE_PRESENT


def inspect_graph_context(base: Path) -> GraphContextStatus:
    """Inspect Graphify configuration and expected outputs without executing it."""
    base = Path(base)
    mapping = load_mapping(base)
    diagnostics: list[str] = []
    enabled = _enabled(mapping.get("graphify_enabled", _MISSING), diagnostics)
    if not enabled and not diagnostics:
        return GraphContextStatus(
            enabled=False,
            state=STATE_DISABLED,
            graph_path=f"{DEFAULT_OUTPUT_DIR}/graph.json",
            report_path=f"{DEFAULT_OUTPUT_DIR}/GRAPH_REPORT.md",
            query_budget=DEFAULT_QUERY_BUDGET,
            output_path_usable=False,
        )
    output_dir, relative_dir, root = _output_directory(
        base,
        mapping.get("graphify_output_dir", _MISSING),
        diagnostics,
    )
    budget = _query_budget(mapping.get("graphify_query_budget", _MISSING), diagnostics)

    graph_entry = _OutputEntryState.ABSENT
    report_entry = _OutputEntryState.ABSENT
    if not enabled:
        state = STATE_DISABLED
    else:
        if output_dir is not None and root is not None:
            graph_entry = _inspect_output_entry(
                output_dir / "graph.json",
                label="graph",
                root=root,
                output_dir=output_dir,
                diagnostics=diagnostics,
            )
            report_entry = _inspect_output_entry(
                output_dir / "GRAPH_REPORT.md",
                label="report",
                root=root,
                output_dir=output_dir,
                diagnostics=diagnostics,
            )
        if (
            graph_entry is _OutputEntryState.SAFE_PRESENT
            and report_entry is _OutputEntryState.SAFE_PRESENT
        ):
            state = STATE_READY
        elif (
            graph_entry is _OutputEntryState.SAFE_PRESENT
            or report_entry is _OutputEntryState.SAFE_PRESENT
        ):
            state = STATE_PARTIAL
        else:
            state = STATE_MISSING

    relative_root = Path(relative_dir)
    return GraphContextStatus(
        enabled=enabled,
        state=state,
        graph_path=(relative_root / "graph.json").as_posix(),
        report_path=(relative_root / "GRAPH_REPORT.md").as_posix(),
        query_budget=budget,
        diagnostics=tuple(diagnostics),
        output_path_usable=(
            output_dir is not None
            and root is not None
            and graph_entry is not _OutputEntryState.UNSAFE
            and report_entry is not _OutputEntryState.UNSAFE
        ),
    )


def _question(skill_name: str) -> str:
    normalized = "".join(
        character
        if character.isalnum()
        or character.isspace()
        or character in _SAFE_SKILL_PUNCTUATION
        else " "
        for character in str(skill_name)
    )
    safe_name = " ".join(normalized.split())
    safe_name = safe_name or "the selected skill"
    question = f"What project context is relevant to {safe_name}?"
    if len(question) > 300:
        question = question[:299].rstrip() + "?"
    return question


def render_query_directive(status: GraphContextStatus, skill_name: str) -> str:
    """Render a compact query-first contract for a ready Graphify index."""
    if not status.enabled or status.state != STATE_READY:
        return ""
    return (
        "An existing Graphify index is available. Query it before broad file search:\n"
        f'`graphify query "{_question(skill_name)}" --budget {status.query_budget}`\n\n'
        "Use returned source locations to open only the files needed for this task.\n"
        "Treat INFERRED or AMBIGUOUS edges as hypotheses. Verify critical behaviour in "
        "source and tests before making or approving a change."
    )
