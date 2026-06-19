"""
Tests for the clipboard helper (v0.5.0). Stdlib only.

Run:  python -m unittest test_briscola_clipboard -v
"""

import os
import unittest

import briscola_clipboard as clip


class TestClipboard(unittest.TestCase):
    def test_returns_bool_without_raising(self):
        self.assertIsInstance(clip.copy_to_clipboard("a-token-123"), bool)

    def test_false_off_windows(self):
        if os.name != "nt":
            self.assertFalse(clip.copy_to_clipboard("anything"))

    def test_is_write_only(self):
        # the module must not expose any clipboard-reading capability (no peeking)
        self.assertFalse(hasattr(clip, "read_clipboard"))
        self.assertFalse(hasattr(clip, "paste_from_clipboard"))
        self.assertFalse(hasattr(clip, "get_clipboard"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
