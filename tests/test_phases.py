import unittest

from projectpilot.phases import Phase, PHASE_ORDER, next_phase, phase_from_str, phase_label
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


class PhaseLabelTests(unittest.TestCase):
    def test_single_word_phase(self):
        self.assertEqual(phase_label(Phase.PLANNING), "Planning")

    def test_hyphenated_phase_becomes_title_case(self):
        self.assertEqual(phase_label(Phase.SETUP_ADVICE), "Setup Advice")
        self.assertEqual(phase_label(Phase.FINAL_VALIDATION), "Final Validation")

    def test_every_phase_has_a_label(self):
        for phase in Phase:
            label = phase_label(phase)
            self.assertTrue(label and "-" not in label)


if __name__ == "__main__":
    unittest.main()
