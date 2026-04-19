"""Tests for runtime path resolution helpers."""

import os
import tempfile
import unittest
from pathlib import Path

from src.main import resolve_runtime_paths
from src.utils.file_utils import resolve_existing_directory


class TestRuntimePathResolution(unittest.TestCase):
    """Validate main/gui path normalization helpers."""

    def test_main_resolve_runtime_paths_returns_absolute_paths(self):
        project_root, scheme_dir, config_path = resolve_runtime_paths()
        self.assertTrue(project_root.is_absolute())
        self.assertTrue(scheme_dir.is_absolute())
        self.assertTrue(config_path.is_absolute())
        self.assertEqual(scheme_dir.name, "scheme")
        self.assertEqual(config_path.name, "config.ini")
        self.assertEqual(scheme_dir.parent, project_root)
        self.assertEqual(config_path.parent, project_root)

    def test_resolve_existing_directory_normalizes_relative_path(self):
        original_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                os.chdir(tmpdir)
                os.makedirs("output", exist_ok=True)
                resolved = resolve_existing_directory("output")
                self.assertEqual(resolved, str(Path(tmpdir, "output").resolve()))
        finally:
            os.chdir(original_cwd)

    def test_resolve_existing_directory_raises_for_missing_path(self):
        with self.assertRaises(FileNotFoundError):
            resolve_existing_directory("definitely_missing_directory_12345")


if __name__ == "__main__":
    unittest.main()
