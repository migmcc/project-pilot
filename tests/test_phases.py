import unittest

from projectpilot.phases import Phase, PHASE_ORDER, next_phase, phase_from_str
from projectpilot.errors import UnknownPhaseError

CANONICAL = [
    "idea",
    "validation",
    "brief",
    "setup-advice",
    "planning",
    "execution",
    "final-validation",
    "done",
]


class PhaseCatalogueTests(unittest.TestCase):
    def test_catalogue_matches_d5_order(self):
        self.assertEqual([p.value for p in PHASE_ORDER], CANONICAL)

    def test_next_phase_transitions(self):
        self.assertEqual(next_phase(Phase.IDEA), Phase.VALIDATION)
        self.assertEqual(next_phase(Phase.FINAL_VALIDATION), Phase.DONE)

    def test_terminal_phase_has_no_next(self):
        self.assertIsNone(next_phase(Phase.DONE))

    def test_phase_from_str_valid(self):
        self.assertEqual(phase_from_str("setup-advice"), Phase.SETUP_ADVICE)

    def test_phase_from_str_invalid_raises(self):
        with self.assertRaises(UnknownPhaseError):
            phase_from_str("not-a-phase")


if __name__ == "__main__":
    unittest.main()
