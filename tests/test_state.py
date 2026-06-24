import tempfile
import unittest
from pathlib import Path

from projectpilot.phases import Phase
from projectpilot.state import (
    SCHEMA_VERSION,
    ProjectState,
    load_state,
    save_state,
    state_exists,
)
from projectpilot.errors import StateNotFoundError

FROZEN = "2026-06-24T10:00:00Z"


def make_state() -> ProjectState:
    return ProjectState(
        name="Demo",
        slug="demo",
        idea="an idea",
        created_at=FROZEN,
        updated_at=FROZEN,
        current_phase=Phase.IDEA,
        decision=None,
        history=[{"event": "init", "phase": "idea", "timestamp": FROZEN}],
    )


class StateTests(unittest.TestCase):
    def test_round_trip_dict(self):
        state = make_state()
        self.assertEqual(ProjectState.from_dict(state.to_dict()), state)

    def test_schema_version_is_one(self):
        self.assertEqual(SCHEMA_VERSION, 1)
        self.assertEqual(make_state().to_dict()["schema_version"], 1)

    def test_save_then_load_equal(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            save_state(base, make_state())
            self.assertTrue(state_exists(base))
            self.assertEqual(load_state(base), make_state())

    def test_load_missing_raises(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(StateNotFoundError):
                load_state(Path(d))

    def test_frozen_clock_timestamps(self):
        state = make_state()
        self.assertEqual(state.created_at, FROZEN)
        self.assertEqual(state.updated_at, FROZEN)


if __name__ == "__main__":
    unittest.main()
