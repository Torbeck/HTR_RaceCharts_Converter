"""Tests for read_last_output in ini_utils."""

import configparser
import os
import tempfile
import unittest

from src.utils.ini_utils import read_last_output, write_last_output


class TestReadLastOutput(unittest.TestCase):
    """Verify read_last_output returns None for 'Default' and stored paths otherwise."""

    def _write_ini(self, path: str, last_output_value: str) -> None:
        """Helper: write a minimal config.ini with a [paths] section."""
        parser = configparser.ConfigParser()
        parser.add_section("paths")
        parser.set("paths", "last_output", last_output_value)
        with open(path, "w", encoding="utf-8") as f:
            parser.write(f)

    def test_returns_none_when_value_is_default(self):
        """'Default' (any case) should return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ini = os.path.join(tmpdir, "config.ini")
            for variant in ("Default", "default", "DEFAULT"):
                self._write_ini(ini, variant)
                result = read_last_output(ini)
                self.assertIsNone(result, f"Expected None for '{variant}'")

    def test_returns_none_when_value_is_empty(self):
        """Empty or missing value should return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ini = os.path.join(tmpdir, "config.ini")
            self._write_ini(ini, "")
            self.assertIsNone(read_last_output(ini))

    def test_returns_none_when_file_missing(self):
        """Missing config.ini should return None."""
        result = read_last_output("/nonexistent/config.ini")
        self.assertIsNone(result)

    def test_returns_none_when_path_does_not_exist(self):
        """A stored path that no longer exists on disk should return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ini = os.path.join(tmpdir, "config.ini")
            self._write_ini(ini, "/nonexistent/path/that/does/not/exist")
            self.assertIsNone(read_last_output(ini))

    def test_returns_stored_path_when_valid_directory(self):
        """A stored path that exists on disk should be returned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ini = os.path.join(tmpdir, "config.ini")
            output_dir = os.path.join(tmpdir, "output")
            os.makedirs(output_dir)
            self._write_ini(ini, output_dir)
            self.assertEqual(read_last_output(ini), output_dir)

    def test_write_then_read_round_trip(self):
        """write_last_output should persist a path that read_last_output returns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ini = os.path.join(tmpdir, "config.ini")
            output_dir = os.path.join(tmpdir, "my_output")
            os.makedirs(output_dir)

            # Start with Default
            self._write_ini(ini, "Default")
            self.assertIsNone(read_last_output(ini))

            # Write a real path
            write_last_output(ini, output_dir)
            self.assertEqual(read_last_output(ini), output_dir)


if __name__ == "__main__":
    unittest.main()
