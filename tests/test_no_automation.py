"""Static guard: the runtime package must perform no forbidden automation.

Scans ``src/`` for tokens that would indicate process spawning, network access,
GitHub API usage, or VCS/release/install automation. The test suite itself is
exempt (e.g. ``test_persistence.py`` legitimately uses ``subprocess``); only
``src/`` is scanned.
"""
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

# Precise tokens (chosen to avoid substring false-positives like "through").
FORBIDDEN_TOKENS = [
    "subprocess",
    "socket",
    "urllib",
    "http.client",
    "httplib",
    "os.system",
    "os.popen",
    "requests",
    "github",
    "pip install",
    "git push",
    "git commit",
]


class NoAutomationTests(unittest.TestCase):
    def test_src_has_no_forbidden_tokens(self):
        offenders = []
        for path in sorted(SRC.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for token in FORBIDDEN_TOKENS:
                if token in text:
                    offenders.append(f"{path.name}: {token!r}")
        self.assertEqual(offenders, [], f"Forbidden tokens in src/: {offenders}")


if __name__ == "__main__":
    unittest.main()
