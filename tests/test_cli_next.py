import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from projectpilot.cli import main
from projectpilot.phases import Phase
from projectpilot.state import ProjectState, save_state


def seed_state(base: Path, phase=Phase.PLANNING, **over):
    data = dict(
        name="Demo",
        slug="demo",
        idea="build a thing",
        created_at="2026-06-30T00:00:00Z",
        updated_at="2026-06-30T00:00:00Z",
        current_phase=phase,
    )
    data.update(over)
    save_state(base, ProjectState(**data))


class NextCliFixture(unittest.TestCase):
    def _run(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = main(argv)
        return rc, out.getvalue()


class NextTextTests(NextCliFixture):
    def test_no_state(self):
        with tempfile.TemporaryDirectory() as d:
            rc, text = self._run(["next", "--dir", d])
            self.assertEqual(rc, 0)
            self.assertIn("not initialized", text)
            self.assertIn("Initialize ProjectPilot", text)

    def test_text_output_structure(self):
        with tempfile.TemporaryDirectory() as d:
            seed_state(Path(d))
            rc, text = self._run(["next", "--dir", d])
            self.assertEqual(rc, 0)
            self.assertIn("Current phase: Planning", text)
            self.assertIn("Recommended next action", text)
            self.assertIn("1.", text)
            self.assertIn("Priority:", text)
            self.assertIn("Reason:", text)
            self.assertIn("Suggested command:", text)

    def test_verbose_shows_depends_on(self):
        with tempfile.TemporaryDirectory() as d:
            seed_state(Path(d))
            rc_plain, plain = self._run(["next", "--dir", d])
            rc_verbose, verbose = self._run(["next", "--verbose", "--dir", d])
            self.assertEqual((rc_plain, rc_verbose), (0, 0))
            self.assertNotIn("Depends on:", plain)
            self.assertIn("Depends on:", verbose)

    def test_followup_present_for_non_terminal_phase(self):
        with tempfile.TemporaryDirectory() as d:
            seed_state(Path(d), phase=Phase.PLANNING)
            _, text = self._run(["next", "--dir", d])
            self.assertIn("advances to the Execution phase", text)


class NextJsonTests(NextCliFixture):
    def test_json_is_valid_and_shaped(self):
        with tempfile.TemporaryDirectory() as d:
            seed_state(Path(d))
            rc, text = self._run(["next", "--json", "--dir", d])
            self.assertEqual(rc, 0)
            payload = json.loads(text)
            self.assertEqual(payload["phase"], "planning")
            self.assertIn("recommendations", payload)
            self.assertTrue(payload["recommendations"])
            rec = payload["recommendations"][0]
            for key in ("priority", "action", "reason", "command", "depends_on"):
                self.assertIn(key, rec)

    def test_json_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            seed_state(Path(d))
            _, a = self._run(["next", "--json", "--dir", d])
            _, b = self._run(["next", "--json", "--dir", d])
            self.assertEqual(a, b)

    def test_json_no_state(self):
        with tempfile.TemporaryDirectory() as d:
            rc, text = self._run(["next", "--json", "--dir", d])
            payload = json.loads(text)
            self.assertIsNone(payload["phase"])
            self.assertEqual(len(payload["recommendations"]), 1)


if __name__ == "__main__":
    unittest.main()
