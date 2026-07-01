import io
import types
import unittest
from unittest import mock

from projectpilot import console


class EncodableTests(unittest.TestCase):
    def test_ascii_always_encodable(self):
        self.assertTrue(console.encodable("plain ascii"))

    def test_unicode_encodable_under_utf8(self):
        # A StringIO has no encoding attribute, so the helper assumes UTF-8.
        with mock.patch("sys.stdout", io.StringIO()):
            self.assertTrue(console.encodable("★✓█"))

    def test_unicode_not_encodable_under_cp1252(self):
        with mock.patch("sys.stdout", types.SimpleNamespace(encoding="cp1252")):
            self.assertFalse(console.encodable("★"))
            self.assertTrue(console.encodable("plain"))

    def test_unknown_encoding_is_not_fatal(self):
        with mock.patch("sys.stdout", types.SimpleNamespace(encoding="definitely-not-a-codec")):
            self.assertFalse(console.encodable("x"))


class GlyphsTests(unittest.TestCase):
    def test_prefers_unicode_when_encodable(self):
        with mock.patch("projectpilot.console.encodable", return_value=True):
            self.assertEqual(console.glyphs(("★", "☆"), ("*", ".")), ("★", "☆"))

    def test_falls_back_when_not_encodable(self):
        with mock.patch("projectpilot.console.encodable", return_value=False):
            self.assertEqual(console.glyphs(("★", "☆"), ("*", ".")), ("*", "."))


class MakeOutputResilientTests(unittest.TestCase):
    def test_reconfigures_when_supported(self):
        stream = mock.Mock()
        with mock.patch("sys.stdout", stream), mock.patch("sys.stderr", stream):
            console.make_output_resilient()
        stream.reconfigure.assert_called_with(errors="replace")

    def test_ignores_streams_without_reconfigure(self):
        # StringIO has no reconfigure attribute; must not raise.
        with mock.patch("sys.stdout", io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
            console.make_output_resilient()


if __name__ == "__main__":
    unittest.main()
