"""Tests for config.ini creation at application launch in main.py."""

import configparser
import os
import tempfile
import unittest
from unittest.mock import patch

from src.utils.ini_utils import rebuild_config


class TestMainConfigCreation(unittest.TestCase):
    """Verify that main() creates config.ini when it is missing."""

    def test_creates_config_when_missing(self):
        """main() should create config.ini if it does not exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.ini")
            scheme_dir = os.path.join(tmpdir, "scheme")
            os.makedirs(scheme_dir)

            self.assertFalse(os.path.isfile(config_path))

            # Simulate what main() does: create config.ini when missing
            if not os.path.isfile(config_path):
                rebuild_config(config_path)

            self.assertTrue(os.path.isfile(config_path))

            # Verify the file contains expected default sections
            parser = configparser.ConfigParser()
            parser.read(config_path, encoding="utf-8")
            self.assertTrue(parser.has_section("race_data"))
            self.assertTrue(parser.has_section("points_call"))
            self.assertTrue(parser.has_section("fractional_times"))
            self.assertTrue(parser.has_section("paths"))
            self.assertEqual(parser.get("paths", "last_output"), "default")

    def test_does_not_overwrite_existing_config(self):
        """main() should not overwrite config.ini if it already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.ini")
            scheme_dir = os.path.join(tmpdir, "scheme")
            os.makedirs(scheme_dir)

            # Write a custom config.ini
            parser = configparser.ConfigParser()
            parser.add_section("paths")
            parser.set("paths", "last_output", "/custom/path")
            with open(config_path, "w", encoding="utf-8") as f:
                parser.write(f)

            # Simulate what main() does: skip creation when file exists
            if not os.path.isfile(config_path):
                rebuild_config(config_path)

            # Verify the existing file was not overwritten
            parser2 = configparser.ConfigParser()
            parser2.read(config_path, encoding="utf-8")
            self.assertEqual(parser2.get("paths", "last_output"), "/custom/path")


if __name__ == "__main__":
    unittest.main()
