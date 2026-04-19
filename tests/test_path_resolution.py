"""Tests for runtime path resolution helpers."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_main_resolve_runtime_paths_when_frozen_uses_meipass_for_resources(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_root = Path(tmpdir, "bundle")
            exe_root = Path(tmpdir, "app")
            bundle_root.mkdir(parents=True)
            (bundle_root / "scheme").mkdir()
            exe_root.mkdir(parents=True)
            exe_path = exe_root / "HTR_RaceCharts_Converter.exe"
            exe_path.write_text("", encoding="utf-8")

            with patch.object(sys, "frozen", True, create=True), patch.object(
                sys, "_MEIPASS", str(bundle_root), create=True
            ), patch.object(sys, "executable", str(exe_path)):
                project_root, scheme_dir, config_path = resolve_runtime_paths()

            self.assertEqual(project_root, exe_root.resolve())
            self.assertEqual(scheme_dir, (bundle_root / "scheme").resolve())
            self.assertEqual(config_path, (exe_root / "config.ini").resolve())

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
