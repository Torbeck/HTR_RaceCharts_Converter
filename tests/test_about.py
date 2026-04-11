"""Tests for the version module and the About dialog in gui.py."""

import unittest

from src.version import __version__

try:
    import tkinter as tk
    _HAS_TK = True
except ImportError:
    _HAS_TK = False


class TestVersion(unittest.TestCase):
    """Verify version module exposes a valid version string."""

    def test_version_is_string(self):
        """__version__ should be a non-empty string."""
        self.assertIsInstance(__version__, str)
        self.assertTrue(len(__version__) > 0)

    def test_version_format(self):
        """__version__ should follow major.minor.patch format."""
        parts = __version__.split(".")
        self.assertEqual(len(parts), 3, "Expected major.minor.patch format")
        for part in parts:
            self.assertTrue(part.isdigit(), f"'{part}' is not a digit")


@unittest.skipUnless(_HAS_TK, "tkinter not available")
class TestAboutDialog(unittest.TestCase):
    """Verify the About dialog displays required information."""

    def setUp(self):
        """Create a hidden root window for dialog testing."""
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        """Destroy the root window after each test."""
        self.root.destroy()

    def test_on_about_creates_toplevel(self):
        """_on_about should create a Toplevel window with expected content."""
        from src.gui import HTRApp

        # Patch __init__ to avoid full GUI startup; build just the about dialog
        app = object.__new__(HTRApp)
        app._root = self.root

        # Call the about handler
        app._on_about()

        # Find the Toplevel created by _on_about
        toplevels = [w for w in self.root.winfo_children()
                     if isinstance(w, tk.Toplevel)]
        self.assertEqual(len(toplevels), 1, "Expected one Toplevel window")

        about_win = toplevels[0]
        self.assertEqual(about_win.title(), "About HTR Race Charts Converter")

        # Collect all text from labels inside the dialog
        all_text = self._collect_label_texts(about_win)

        self.assertIn("HTR Race Charts Converter", all_text)
        self.assertIn(__version__, all_text)
        self.assertIn("Ken Torbeck", all_text)
        self.assertIn("Dr. Russ Winterbotham", all_text)
        self.assertIn("GPL-3.0", all_text)
        self.assertIn("Disclaimer", all_text)
        self.assertIn("\u00a9 2026", all_text)
        self.assertIn(
            "https://github.com/ktorbeck/htr-race-charts-converter", all_text
        )

        about_win.destroy()

    @staticmethod
    def _collect_label_texts(widget):
        """Recursively collect text from all Label widgets."""
        texts = []
        for child in widget.winfo_children():
            try:
                texts.append(child.cget("text"))
            except tk.TclError:
                pass
            texts.extend(TestAboutDialog._collect_label_texts(child))
        return " ".join(texts)


if __name__ == "__main__":
    unittest.main()
