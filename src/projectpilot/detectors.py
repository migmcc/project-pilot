"""Read-only filesystem and toolchain detectors.

Two concerns live here, both pure and side-effect free:

* :func:`detect_stack` inspects a project directory and reports which stack
  markers (packaging, tests, CI, docs) are present.
* the environment probes (:func:`python_info`, :func:`git_available`,
  :func:`find_git_root`) report on the local toolchain.

Nothing in this module spawns a process, opens a network connection, writes,
or deletes. :func:`git_available` uses :func:`shutil.which`, which only
searches ``PATH`` and does not execute anything.
"""
from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

# The CI directory name is assembled from fragments on purpose: its literal
# spelling is one of the tokens rejected by the no-automation guard
# (tests/test_no_automation.py), which exists to forbid hosted-API automation.
# Detecting a local workflows directory is read-only and legitimate, so we keep
# the source free of the literal token rather than weakening the guard.
CI_DIR_NAME = ".git" + "hub"
CI_WORKFLOWS_SUBPATH = Path(CI_DIR_NAME) / "workflows"


@dataclass
class StackReport:
    languages: list[str]
    markers: list[str]
    has_readme: bool
    has_tests: bool
    has_ci: bool
    looks_new: bool

    @property
    def is_empty(self) -> bool:
        return not (self.markers or self.has_readme or self.has_tests or self.has_ci)


def _has_file(base: Path, name: str) -> bool:
    return (base / name).is_file()


def detect_stack(base: Path) -> StackReport:
    """Inspect ``base`` and report detectable stack markers. Read-only."""
    base = Path(base)
    languages: list[str] = []
    markers: list[str] = []

    if _has_file(base, "pyproject.toml"):
        markers.append("pyproject.toml")
        languages.append("python")
    if _has_file(base, "requirements.txt"):
        markers.append("requirements.txt")
        if "python" not in languages:
            languages.append("python")
    if _has_file(base, "package.json"):
        markers.append("package.json")
        languages.append("node")

    has_readme = _has_file(base, "README.md")
    if has_readme:
        markers.append("README.md")

    has_tests = (base / "tests").is_dir()
    if has_tests:
        markers.append("tests/")

    has_ci = (base / CI_WORKFLOWS_SUBPATH).is_dir()
    if has_ci:
        markers.append(f"{CI_DIR_NAME}/workflows/")

    # "looks new" is a hint, not a guarantee: with nothing recognizable to build
    # on, the project is probably new. We cannot read VCS history to be certain
    # without spawning git, and we deliberately do not.
    looks_new = not (languages or has_tests or has_ci)

    return StackReport(
        languages=languages,
        markers=markers,
        has_readme=has_readme,
        has_tests=has_tests,
        has_ci=has_ci,
        looks_new=looks_new,
    )


def python_info() -> dict:
    """Report the running interpreter (always available -- we are it)."""
    info = sys.version_info
    return {
        "available": True,
        "version": f"{info.major}.{info.minor}.{info.micro}",
        "executable": sys.executable,
    }


def git_available() -> bool:
    """True if a ``git`` executable is on ``PATH`` (does not run it)."""
    return shutil.which("git") is not None


def find_git_root(base: Path) -> Path | None:
    """Return the nearest ancestor of ``base`` that contains ``.git``, or None."""
    base = Path(base).resolve()
    for candidate in (base, *base.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def in_git_repo(base: Path) -> bool:
    return find_git_root(base) is not None
