"""Restart proof: state written by one process is readable by a separate one.

Uses ``python -m projectpilot`` in two distinct subprocesses to prove the
``.project-pilot/status.json`` foundation persists across process boundaries —
not merely in memory.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"


def _run(args, cwd):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(SRC), env.get("PYTHONPATH", "")])
    return subprocess.run(
        [sys.executable, "-m", "projectpilot", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


class PersistenceTests(unittest.TestCase):
    def test_state_survives_restart(self):
        with tempfile.TemporaryDirectory() as d:
            first = _run(["init", "a persistent idea", "--dir", "."], cwd=d)
            self.assertEqual(first.returncode, 0, first.stderr)

            # Separate process — simulates a fresh session / restart.
            second = _run(["status", "--dir", "."], cwd=d)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("idea", second.stdout)
            self.assertIn("validation", second.stdout)


if __name__ == "__main__":
    unittest.main()
