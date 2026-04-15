"""Tests for the schema editor non-GUI helpers.

Covers:
- Type normalization
- Type display labels
- Fields-schema validation
- lookupRef validation
- JSON round-trip save/load fidelity
"""

import json
import os
import tempfile
import unittest

from tools.schema_editor import (
    EXCEL_FORMATS,
    VALID_TYPES,
    load_fields_json,
    load_lookup_json,
    normalize_type,
    save_json,
    type_display_label,
    validate_fields_schema,
    validate_lookup_refs,
)


class TestNormalizeType(unittest.TestCase):
    """Verify normalize_type maps known types and defaults unknowns to Text."""

    def test_known_types_unchanged(self):
        for t in VALID_TYPES:
            self.assertEqual(normalize_type(t), t)

    def test_case_insensitive(self):
        self.assertEqual(normalize_type("text"), "Text")
        self.assertEqual(normalize_type("INTEGER"), "Integer")
        self.assertEqual(normalize_type("decimal"), "Decimal")

    def test_unknown_falls_back_to_text(self):
        self.assertEqual(normalize_type("FooBar"), "Text")
        self.assertEqual(normalize_type(""), "Text")

    def test_empty_string_returns_text(self):
        self.assertEqual(normalize_type(""), "Text")


class TestTypeDisplayLabel(unittest.TestCase):
    """Verify type_display_label returns label with Excel format."""

    def test_text_label(self):
        self.assertEqual(type_display_label("Text"), "Text  (@)")

    def test_integer_label(self):
        self.assertEqual(type_display_label("Integer"), "Integer  (0)")

    def test_decimal_label(self):
        self.assertEqual(type_display_label("Decimal"), "Decimal  (0.00)")

    def test_date_label(self):
        self.assertEqual(type_display_label("Date"), "Date  (m/d/yyyy)")

    def test_currency_label(self):
        self.assertEqual(type_display_label("Currency"), "Currency  ($#,##0.00)")

    def test_unknown_type_no_format(self):
        self.assertEqual(type_display_label("Unknown"), "Unknown")


class TestValidateFieldsSchema(unittest.TestCase):
    """Verify validate_fields_schema catches common problems."""

    def _make_entry(self, field_num, **overrides):
        entry = {
            "field": field_num,
            "name": f"Field {field_num}",
            "type": "Text",
            "maxLength": "",
            "comments": "",
            "hasOptions": "",
        }
        entry.update(overrides)
        return entry

    def test_valid_schema_no_errors(self):
        data = [self._make_entry(i + 1) for i in range(3)]
        self.assertEqual(validate_fields_schema(data), [])

    def test_not_a_list(self):
        errors = validate_fields_schema({"not": "a list"})
        self.assertTrue(any("must be a JSON array" in e for e in errors))

    def test_missing_required_keys(self):
        data = [{"field": 1, "name": "X"}]
        errors = validate_fields_schema(data)
        self.assertTrue(any("missing keys" in e for e in errors))

    def test_unknown_type_flagged(self):
        data = [self._make_entry(1, type="FooBar")]
        errors = validate_fields_schema(data)
        self.assertTrue(any("unknown type" in e for e in errors))

    def test_empty_type_not_flagged(self):
        data = [self._make_entry(1, type="")]
        errors = validate_fields_schema(data)
        self.assertEqual(errors, [])


class TestValidateLookupRefs(unittest.TestCase):
    """Verify lookupRef validation against lookup.json."""

    def test_valid_ref(self):
        fields = [
            {"field": 137, "name": "X", "type": "Text", "maxLength": "",
             "comments": "", "hasOptions": "Y", "lookupRef": 131}
        ]
        lookup = [{"field": 131, "id": "W", "value": "Win"}]
        self.assertEqual(validate_lookup_refs(fields, lookup), [])

    def test_invalid_ref(self):
        fields = [
            {"field": 137, "name": "X", "type": "Text", "maxLength": "",
             "comments": "", "hasOptions": "Y", "lookupRef": 999}
        ]
        lookup = [{"field": 131, "id": "W", "value": "Win"}]
        errors = validate_lookup_refs(fields, lookup)
        self.assertTrue(any("lookupRef=999" in e for e in errors))

    def test_ref_ignored_when_no_has_options(self):
        fields = [
            {"field": 137, "name": "X", "type": "Text", "maxLength": "",
             "comments": "", "hasOptions": "", "lookupRef": 999}
        ]
        lookup = [{"field": 131, "id": "W", "value": "Win"}]
        self.assertEqual(validate_lookup_refs(fields, lookup), [])


class TestJsonRoundTrip(unittest.TestCase):
    """Verify save_json + load round-trip preserves order and content."""

    def test_fields_round_trip(self):
        original = [
            {"field": 1, "name": "Track", "type": "Text",
             "maxLength": 3, "comments": "code", "hasOptions": ""},
            {"field": 2, "name": "Date", "type": "Text",
             "maxLength": 10, "comments": "", "hasOptions": ""},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "fields.json")
            save_json(path, original)
            loaded = load_fields_json(path)
            self.assertEqual(loaded, original)

    def test_key_order_preserved(self):
        """Keys must appear in the same order after round-trip."""
        original = [
            {"field": 1, "name": "A", "type": "Text",
             "maxLength": "", "comments": "", "hasOptions": ""},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            save_json(path, original)
            with open(path, encoding="utf-8") as f:
                raw = f.read()
            # "field" must appear before "name" in the raw JSON
            self.assertLess(raw.index('"field"'), raw.index('"name"'))
            self.assertLess(raw.index('"name"'), raw.index('"type"'))

    def test_lookup_round_trip(self):
        original = [
            {"field": 4, "id": "TB", "value": "Thoroughbred"},
            {"field": 4, "id": "QH", "value": "Quarter Horse"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "lookup.json")
            save_json(path, original)
            loaded = load_lookup_json(path)
            self.assertEqual(loaded, original)

    def test_real_fields_json_round_trip(self):
        """Loading and re-saving the real fields.json should be idempotent."""
        scheme_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scheme",
        )
        path = os.path.join(scheme_dir, "fields.json")
        with open(path, encoding="utf-8") as f:
            original_text = f.read()
        data = json.loads(original_text)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "fields.json")
            save_json(out_path, data)
            with open(out_path, encoding="utf-8") as f:
                saved_text = f.read()
            # Normalize line endings for comparison
            self.assertEqual(
                json.loads(original_text),
                json.loads(saved_text),
            )

    def test_real_lookup_json_round_trip(self):
        """Loading and re-saving the real lookup.json should be idempotent."""
        scheme_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scheme",
        )
        path = os.path.join(scheme_dir, "lookup.json")
        with open(path, encoding="utf-8") as f:
            original_text = f.read()
        data = json.loads(original_text)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "lookup.json")
            save_json(out_path, data)
            with open(out_path, encoding="utf-8") as f:
                saved_text = f.read()
            self.assertEqual(
                json.loads(original_text),
                json.loads(saved_text),
            )


class TestExcelFormatsMapping(unittest.TestCase):
    """Verify the EXCEL_FORMATS dict matches the spec."""

    def test_text_format(self):
        self.assertEqual(EXCEL_FORMATS["Text"], "@")

    def test_integer_format(self):
        self.assertEqual(EXCEL_FORMATS["Integer"], "0")

    def test_decimal_format(self):
        self.assertEqual(EXCEL_FORMATS["Decimal"], "0.00")

    def test_date_format(self):
        self.assertEqual(EXCEL_FORMATS["Date"], "m/d/yyyy")

    def test_currency_format(self):
        self.assertEqual(EXCEL_FORMATS["Currency"], "$#,##0.00")

    def test_valid_types_list(self):
        self.assertEqual(set(VALID_TYPES), set(EXCEL_FORMATS.keys()))


if __name__ == "__main__":
    unittest.main()
