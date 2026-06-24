"""Test package for ProjectPilot.

Ensures the stdlib-first package under ``src/`` is importable during
``python -m unittest discover`` without requiring an editable install.
"""
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
