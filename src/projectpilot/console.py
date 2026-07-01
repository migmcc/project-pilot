"""Terminal-output helpers shared by the CLI commands.

ProjectPilot prints a few Unicode glyphs (stars, check marks, a progress bar).
Not every console can encode them -- a legacy Windows ``cp1252`` terminal will
raise ``UnicodeEncodeError`` mid-print. These helpers centralise the single
"can stdout encode this?" decision so every command degrades identically instead
of each re-implementing the probe.

Read-only and side-effect free apart from :func:`make_output_resilient`, which
adjusts the stdout/stderr error handler once at startup.
"""
from __future__ import annotations

import sys



__all__ = [
    "encodable",
    "glyphs",
    "make_output_resilient",
]

def encodable(text: str) -> bool:
    """True if ``text`` can be encoded with the current stdout encoding.

    Falls back to assuming UTF-8 when the stream has no declared encoding (as
    with the ``StringIO`` used in tests), so Unicode output is preserved there.
    """
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def glyphs(preferred: tuple[str, str], fallback: tuple[str, str]) -> tuple[str, str]:
    """Return ``preferred`` glyphs if the console can encode them, else ``fallback``.

    Used for paired marks such as filled/empty stars, tick/cross, or bar
    segments: ``filled, empty = glyphs(("★", "☆"), ("*", "."))``.
    """
    return preferred if encodable("".join(preferred)) else fallback


def make_output_resilient() -> None:
    """Make stdout/stderr tolerate content the console encoding can't represent.

    External skill libraries and artifact metadata may contain arbitrary Unicode
    that a legacy console cannot encode, which would otherwise raise
    ``UnicodeEncodeError`` mid-print. Switching the error handler to ``replace``
    keeps the console's own encoding but degrades unencodable characters instead
    of crashing. Guarded: streams without ``reconfigure`` (such as the
    ``StringIO`` used in tests) are left untouched.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(errors="replace")
        except (ValueError, OSError):  # pragma: no cover - stream already detached
            pass
