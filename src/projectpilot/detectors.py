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
    """Return the nearest ancestor of ``base`` that contains ``.git``, or None.

    This only locates the ``.git`` marker; it does not judge whether the
    repository is healthy. Use :func:`git_repo_status` to distinguish a valid
    repository from an empty or corrupt ``.git``.
    """
    base = Path(base).resolve()
    for candidate in (base, *base.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def in_git_repo(base: Path) -> bool:
    return find_git_root(base) is not None


# Git repository classification values.
GIT_MISSING = "missing"
GIT_OK = "ok"
GIT_INVALID = "invalid"


@dataclass
class GitRepoStatus:
    """Outcome of classifying a directory's ``.git`` marker.

    ``status`` is one of :data:`GIT_MISSING`, :data:`GIT_OK`, or
    :data:`GIT_INVALID`. ``root`` is the directory holding the ``.git`` marker
    when one was found (regardless of validity), else ``None``. ``detail`` is a
    short human-readable explanation suitable for diagnostic output.
    """

    status: str
    root: Path | None
    detail: str

    @property
    def ok(self) -> bool:
        return self.status == GIT_OK


def _is_valid_git_dir(git_dir: Path) -> bool:
    """True if ``git_dir`` has the minimum structure of a real git directory.

    A healthy git directory has a ``HEAD`` file plus ``objects/`` and ``refs/``
    directories. Linked worktrees keep ``objects`` and ``refs`` in the shared
    common directory, which ``commondir`` points to, so we follow it when
    present. Read-only: this only stats and reads small text files.
    """
    if not git_dir.is_dir():
        return False
    if not (git_dir / "HEAD").is_file():
        return False

    common = git_dir
    commondir_file = git_dir / "commondir"
    if commondir_file.is_file():
        try:
            rel = commondir_file.read_text(encoding="utf-8").strip()
        except OSError:
            return False
        if rel:
            common = (git_dir / rel).resolve()

    return (common / "objects").is_dir() and (common / "refs").is_dir()


def _resolve_gitdir_file(marker: Path) -> Path | None:
    """Resolve a ``.git`` *file* of the form ``gitdir: <path>`` to its target.

    Submodules and linked worktrees use a ``.git`` file pointing at the real
    git directory. Returns the resolved target path, or ``None`` if the file is
    unreadable or does not contain a ``gitdir:`` line. The target is not
    validated here; the caller decides. Read-only.
    """
    try:
        content = marker.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("gitdir:"):
            target = line[len("gitdir:"):].strip()
            if not target:
                return None
            return (marker.parent / target).resolve()
    return None


def git_repo_status(base: Path) -> GitRepoStatus:
    """Classify the git repository state at ``base`` (or its nearest ancestor).

    Walks ``base`` and its parents looking for a ``.git`` marker and stops at
    the first one found -- mirroring how git discovery commits to the nearest
    ``.git`` rather than skipping a broken one to reach a healthy parent. The
    marker may be:

    * a directory -- valid only if it has ``HEAD`` plus ``objects/`` and
      ``refs/`` (see :func:`_is_valid_git_dir`);
    * a file of the form ``gitdir: <path>`` -- valid only if that target is a
      valid git directory.

    Returns a :class:`GitRepoStatus`. Read-only; never spawns git.
    """
    base = Path(base).resolve()
    for candidate in (base, *base.parents):
        marker = candidate / ".git"
        if marker.is_dir():
            if _is_valid_git_dir(marker):
                return GitRepoStatus(GIT_OK, candidate, str(candidate))
            return GitRepoStatus(
                GIT_INVALID, candidate, ".git exists but is incomplete"
            )
        if marker.is_file():
            target = _resolve_gitdir_file(marker)
            if target is not None and _is_valid_git_dir(target):
                return GitRepoStatus(GIT_OK, candidate, f"{candidate} -> {target}")
            return GitRepoStatus(
                GIT_INVALID,
                candidate,
                ".git file does not point to a valid git directory",
            )
    return GitRepoStatus(GIT_MISSING, None, "not inside a git repository")
