"""Tests for src.output_settings module."""

import configparser
import os
import tempfile
import unittest

from src.output_settings import (
    DEFAULT_CUSTOM_ORDER,
    DEFAULT_VISIBLE_FIELDS,
    _parse_int_list,
    apply_field_filter,
    is_customized,
    read_output_settings,
    resolve_field_indices,
    write_field_list,
    write_output_settings,
)


class TestParseIntList(unittest.TestCase):
    """Verify _parse_int_list helper."""

    def test_simple_list(self):
        self.assertEqual(_parse_int_list("1,2,3"), [1, 2, 3])

    def test_whitespace_handling(self):
        self.assertEqual(_parse_int_list(" 1 , 2 , 3 "), [1, 2, 3])

    def test_empty_string(self):
        self.assertEqual(_parse_int_list(""), [])

    def test_non_integer_tokens_ignored(self):
        self.assertEqual(_parse_int_list("1,abc,3"), [1, 3])

    def test_trailing_comma(self):
        self.assertEqual(_parse_int_list("1,2,3,"), [1, 2, 3])

    def test_negative_numbers_ignored(self):
        """Negative numbers are not matched by the \\d+ regex."""
        self.assertEqual(_parse_int_list("-1,2,3"), [2, 3])


class TestReadWriteOutputSettings(unittest.TestCase):
    """Verify reading and writing [output] section in config.ini."""

    def test_defaults_when_section_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.ini")
            # Write an INI with no [output] section
            parser = configparser.ConfigParser()
            parser.add_section("paths")
            parser.set("paths", "last_output", "default")
            with open(config_path, "w", encoding="utf-8") as f:
                parser.write(f)

            visible, order = read_output_settings(config_path)
            self.assertEqual(visible, DEFAULT_VISIBLE_FIELDS)
            self.assertEqual(order, DEFAULT_CUSTOM_ORDER)

    def test_defaults_when_file_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "nonexistent.ini")
            visible, order = read_output_settings(config_path)
            self.assertEqual(visible, DEFAULT_VISIBLE_FIELDS)
            self.assertEqual(order, DEFAULT_CUSTOM_ORDER)

    def test_write_then_read_round_trip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.ini")
            write_output_settings(config_path, "1,2,3", "3,2,1")
            visible, order = read_output_settings(config_path)
            self.assertEqual(visible, "1,2,3")
            self.assertEqual(order, "3,2,1")

    def test_write_preserves_other_sections(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.ini")
            # Create config with existing section
            parser = configparser.ConfigParser()
            parser.add_section("paths")
            parser.set("paths", "last_output", "/my/path")
            with open(config_path, "w", encoding="utf-8") as f:
                parser.write(f)

            write_output_settings(config_path, "1,5,10", "default")

            parser2 = configparser.ConfigParser()
            parser2.read(config_path, encoding="utf-8")
            self.assertEqual(parser2.get("paths", "last_output"), "/my/path")
            self.assertEqual(parser2.get("output", "visible_fields"), "1,5,10")
            self.assertEqual(parser2.get("output", "custom_order"), "default")


class TestResolveFieldIndices(unittest.TestCase):
    """Verify resolve_field_indices logic."""

    def _make_schema(self, n):
        """Create a minimal fields schema with n fields."""
        return [
            {"field": i + 1, "name": f"Field_{i + 1}", "type": "Text",
             "maxLength": 10, "comments": "", "hasOptions": ""}
            for i in range(n)
        ]

    def test_both_defaults_returns_none(self):
        schema = self._make_schema(5)
        result = resolve_field_indices(schema, "all", "default")
        self.assertIsNone(result)

    def test_both_defaults_case_insensitive(self):
        schema = self._make_schema(5)
        self.assertIsNone(resolve_field_indices(schema, "All", "Default"))
        self.assertIsNone(resolve_field_indices(schema, "ALL", "DEFAULT"))

    def test_visible_fields_subset(self):
        schema = self._make_schema(5)
        result = resolve_field_indices(schema, "1,3,5", "default")
        # 0-based indices: [0, 2, 4]
        self.assertEqual(result, [0, 2, 4])

    def test_custom_order(self):
        schema = self._make_schema(5)
        result = resolve_field_indices(schema, "all", "3,1,2,4,5")
        # 0-based: [2, 0, 1, 3, 4]
        self.assertEqual(result, [2, 0, 1, 3, 4])

    def test_custom_order_partial_appends_missing(self):
        """Fields not listed in custom_order are appended in default order."""
        schema = self._make_schema(5)
        result = resolve_field_indices(schema, "all", "3,1")
        # Explicitly: 3,1 -> then 2,4,5 appended
        self.assertEqual(result, [2, 0, 1, 3, 4])

    def test_visible_and_order_combined(self):
        schema = self._make_schema(5)
        # Order: 3,1,2,4,5 but only 1,3 visible
        result = resolve_field_indices(schema, "1,3", "3,1,2,4,5")
        # From order: 3 is visible, 1 is visible => [2, 0]
        self.assertEqual(result, [2, 0])

    def test_invalid_field_numbers_ignored(self):
        schema = self._make_schema(3)
        result = resolve_field_indices(schema, "1,2,99", "default")
        self.assertEqual(result, [0, 1])

    def test_invalid_order_field_numbers_ignored(self):
        schema = self._make_schema(3)
        result = resolve_field_indices(schema, "all", "99,1,2,3")
        # 99 is filtered, remaining: 1,2,3
        self.assertEqual(result, [0, 1, 2])


class TestApplyFieldFilter(unittest.TestCase):
    """Verify apply_field_filter selects and reorders correctly."""

    def test_basic_filter(self):
        headers = ["A", "B", "C", "D"]
        rows = [["a1", "b1", "c1", "d1"], ["a2", "b2", "c2", "d2"]]
        formats = ["@", "0", "0.00", None]
        indices = [2, 0]  # C, A

        fh, fr, ff = apply_field_filter(headers, rows, formats, indices)
        self.assertEqual(fh, ["C", "A"])
        self.assertEqual(fr, [["c1", "a1"], ["c2", "a2"]])
        self.assertEqual(ff, ["0.00", "@"])

    def test_formats_none_passthrough(self):
        headers = ["A", "B"]
        rows = [["a1", "b1"]]
        indices = [1]

        fh, fr, ff = apply_field_filter(headers, rows, None, indices)
        self.assertEqual(fh, ["B"])
        self.assertEqual(fr, [["b1"]])
        self.assertIsNone(ff)


class TestRebuildConfigOutputSection(unittest.TestCase):
    """Verify rebuild_config includes the [output] section."""

    def test_rebuild_creates_output_section(self):
        from src.utils.ini_utils import rebuild_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.ini")
            rebuild_config(config_path)

            parser = configparser.ConfigParser()
            parser.read(config_path, encoding="utf-8")
            self.assertTrue(parser.has_section("output"))
            self.assertEqual(
                parser.get("output", "visible_fields"), "all"
            )
            self.assertEqual(
                parser.get("output", "custom_order"), "default"
            )


class TestIsCustomized(unittest.TestCase):
    """Verify is_customized helper."""

    def test_none_means_not_customized(self):
        self.assertFalse(is_customized(None))

    def test_empty_list_means_customized(self):
        self.assertTrue(is_customized([]))

    def test_non_empty_list_means_customized(self):
        self.assertTrue(is_customized([0, 2, 4]))


class TestWriteFieldList(unittest.TestCase):
    """Verify write_field_list generates the correct companion .txt file."""

    def test_generates_txt_file(self):
        headers = ["Track Code", "Race Date", "Horse Name", "Jockey", "Trainer"]
        indices = [2, 0, 4]  # Horse Name, Track Code, Trainer

        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_field_list(tmpdir, "test_customized", headers, indices)
            self.assertTrue(os.path.isfile(path))
            self.assertTrue(path.endswith(".txt"))

    def test_filename_matches_output_name(self):
        headers = ["A", "B", "C"]
        indices = [1, 0]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_field_list(tmpdir, "myfile_customized", headers, indices)
            self.assertEqual(os.path.basename(path), "myfile_customized.txt")

    def test_content_lists_fields_in_order(self):
        headers = ["Track Code", "Race Date", "Horse Name", "Jockey", "Trainer"]
        indices = [2, 0, 4]  # Horse Name, Track Code, Trainer

        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_field_list(tmpdir, "test_customized", headers, indices)
            with open(path, encoding="utf-8") as f:
                content = f.read()

            # Verify header section
            self.assertIn("Customized Output Fields", content)

            # Verify field entries
            self.assertIn("1. Horse Name (Field #3)", content)
            self.assertIn("2. Track Code (Field #1)", content)
            self.assertIn("3. Trainer (Field #5)", content)

    def test_field_order_is_explicit(self):
        """Each field line must start with its 1-based position number."""
        headers = ["A", "B", "C", "D"]
        indices = [3, 1]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_field_list(tmpdir, "ordered_customized", headers, indices)
            with open(path, encoding="utf-8") as f:
                content = f.read()

            self.assertIn("1. D (Field #4)", content)
            self.assertIn("2. B (Field #2)", content)

    def test_returns_path_to_written_file(self):
        headers = ["A", "B"]
        indices = [0]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_field_list(tmpdir, "check_customized", headers, indices)
            self.assertEqual(
                path, os.path.join(tmpdir, "check_customized.txt"),
            )

    def test_human_readable_in_text_editor(self):
        """File must be plain text (UTF-8) readable in any basic text editor."""
        headers = ["Field One", "Field Two", "Field Three"]
        indices = [2, 0]

        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_field_list(tmpdir, "readable_customized", headers, indices)
            with open(path, mode="r", encoding="utf-8") as f:
                lines = f.readlines()
            # Every line should be plain text (no binary/special chars)
            for line in lines:
                self.assertIsInstance(line, str)


if __name__ == "__main__":
    unittest.main()
