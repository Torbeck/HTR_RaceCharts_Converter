"""Tests for lookup.json loading, validation, and translation."""

import json
import logging
import os
import tempfile
import unittest

from src.schema_loader import load_lookup_schema
from src.translator import apply_lookup_translations
from src.validator import validate_lookup_codes


class TestLoadLookupSchema(unittest.TestCase):
    """Verify load_lookup_schema handles the array-based lookup.json."""

    def _write_lookup(self, directory: str, data) -> None:
        """Helper: write lookup.json with given data."""
        path = os.path.join(directory, "lookup.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_loads_valid_array(self):
        """A well-formed array of {field, id, value} objects should load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            entries = [
                {"field": 4, "id": "TB", "value": "Thoroughbred"},
                {"field": 4, "id": "QH", "value": "Quarter Horse"},
                {"field": 7, "id": "D", "value": "Dirt"},
            ]
            self._write_lookup(tmpdir, entries)
            result = load_lookup_schema(tmpdir)
            self.assertIsInstance(result, list)
            self.assertEqual(len(result), 3)
            self.assertEqual(result[0]["field"], 4)
            self.assertEqual(result[0]["id"], "TB")
            self.assertEqual(result[0]["value"], "Thoroughbred")

    def test_rejects_dict_format(self):
        """The old hash/object format should be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            old_format = {
                "4": [{"code": "TB", "value": "Thoroughbred"}],
            }
            self._write_lookup(tmpdir, old_format)
            with self.assertRaises(ValueError) as ctx:
                load_lookup_schema(tmpdir)
            self.assertIn("must be a JSON array", str(ctx.exception))

    def test_rejects_entry_missing_field(self):
        """An entry missing the 'field' key should be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            entries = [{"id": "TB", "value": "Thoroughbred"}]
            self._write_lookup(tmpdir, entries)
            with self.assertRaises(ValueError) as ctx:
                load_lookup_schema(tmpdir)
            self.assertIn("missing 'field', 'id', or 'value'", str(ctx.exception))

    def test_rejects_entry_missing_id(self):
        """An entry missing the 'id' key should be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            entries = [{"field": 4, "value": "Thoroughbred"}]
            self._write_lookup(tmpdir, entries)
            with self.assertRaises(ValueError) as ctx:
                load_lookup_schema(tmpdir)
            self.assertIn("missing 'field', 'id', or 'value'", str(ctx.exception))

    def test_rejects_entry_missing_value(self):
        """An entry missing the 'value' key should be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            entries = [{"field": 4, "id": "TB"}]
            self._write_lookup(tmpdir, entries)
            with self.assertRaises(ValueError) as ctx:
                load_lookup_schema(tmpdir)
            self.assertIn("missing 'field', 'id', or 'value'", str(ctx.exception))

    def test_rejects_non_dict_entry(self):
        """A non-object entry in the array should be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            entries = ["not an object"]
            self._write_lookup(tmpdir, entries)
            with self.assertRaises(ValueError) as ctx:
                load_lookup_schema(tmpdir)
            self.assertIn("is not an object", str(ctx.exception))

    def test_loads_real_scheme_file(self):
        """The actual scheme/lookup.json should load as an array with 216 entries."""
        scheme_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scheme",
        )
        result = load_lookup_schema(scheme_dir)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 216)
        # Every entry must have field, id, and value keys
        for entry in result:
            self.assertIn("field", entry)
            self.assertIn("id", entry)
            self.assertIn("value", entry)


class TestValidateLookupCodes(unittest.TestCase):
    """Verify validate_lookup_codes works with the array-based lookup table."""

    def _make_fields_schema(self, has_options_fields):
        """Build a minimal 244-entry fields schema.

        Args:
            has_options_fields: Set of 1-based field numbers with hasOptions=true.
        """
        schema = []
        for i in range(1, 245):
            schema.append({
                "field": i,
                "name": f"Field{i}",
                "type": "Text",
                "maxLength": 10,
                "comments": "",
                "hasOptions": i in has_options_fields,
            })
        return schema

    def test_valid_codes_pass(self):
        """Rows with valid lookup codes should not raise."""
        lookup = [
            {"field": 4, "id": "TB", "value": "Thoroughbred"},
            {"field": 4, "id": "QH", "value": "Quarter Horse"},
        ]
        fields = self._make_fields_schema({4})
        # Field 4 is at 0-based index 3
        row = [""] * 244
        row[3] = "TB"
        validate_lookup_codes([row], fields, lookup, "test.txt")

    def test_invalid_code_logs_warning(self):
        """A row with an unknown lookup code should log a warning."""
        lookup = [
            {"field": 4, "id": "TB", "value": "Thoroughbred"},
        ]
        fields = self._make_fields_schema({4})
        row = [""] * 244
        row[3] = "INVALID"
        with self.assertLogs("src.validator", level="WARNING") as cm:
            validate_lookup_codes([row], fields, lookup, "test.txt")
        self.assertTrue(
            any("INVALID" in msg and "field 4" in msg for msg in cm.output)
        )

    def test_blank_values_skip_validation(self):
        """Blank values in lookup fields should be accepted."""
        lookup = [
            {"field": 4, "id": "TB", "value": "Thoroughbred"},
        ]
        fields = self._make_fields_schema({4})
        row = [""] * 244
        # Field 4 is blank — should pass
        validate_lookup_codes([row], fields, lookup, "test.txt")

    def test_missing_field_in_lookup_logs_warning(self):
        """A field with hasOptions=true but no lookup entries should log warning."""
        lookup = []  # Empty lookup
        fields = self._make_fields_schema({4})
        row = [""] * 244
        row[3] = "TB"
        with self.assertLogs("src.validator", level="WARNING") as cm:
            validate_lookup_codes([row], fields, lookup, "test.txt")
        self.assertTrue(
            any("field 4" in msg for msg in cm.output)
        )

    def test_invalid_code_preserves_value(self):
        """A row with an unknown lookup code should keep its original value."""
        lookup = [
            {"field": 4, "id": "TB", "value": "Thoroughbred"},
        ]
        fields = self._make_fields_schema({4})
        row = [""] * 244
        row[3] = "BF"
        with self.assertLogs("src.validator", level="WARNING"):
            validate_lookup_codes([row], fields, lookup, "test.txt")
        self.assertEqual(row[3], "BF")


class TestApplyLookupTranslations(unittest.TestCase):
    """Verify apply_lookup_translations works with the array-based lookup table."""

    def _make_fields_schema(self, has_options_fields):
        """Build a minimal 244-entry fields schema."""
        schema = []
        for i in range(1, 245):
            schema.append({
                "field": i,
                "name": f"Field{i}",
                "type": "Text",
                "maxLength": 10,
                "comments": "",
                "hasOptions": i in has_options_fields,
            })
        return schema

    def test_translates_codes_to_values(self):
        """Lookup codes should be replaced with human-readable values."""
        lookup = [
            {"field": 4, "id": "TB", "value": "Thoroughbred"},
            {"field": 4, "id": "QH", "value": "Quarter Horse"},
            {"field": 7, "id": "D", "value": "Dirt"},
        ]
        fields = self._make_fields_schema({4, 7})
        row = [""] * 244
        row[3] = "TB"  # Field 4
        row[6] = "D"   # Field 7
        result = apply_lookup_translations([row], fields, lookup)
        self.assertEqual(result[0][3], "Thoroughbred")
        self.assertEqual(result[0][6], "Dirt")

    def test_preserves_blank_values(self):
        """Blank fields should remain blank after translation."""
        lookup = [
            {"field": 4, "id": "TB", "value": "Thoroughbred"},
        ]
        fields = self._make_fields_schema({4})
        row = [""] * 244
        # Field 4 is blank
        result = apply_lookup_translations([row], fields, lookup)
        self.assertEqual(result[0][3], "")

    def test_unknown_code_logs_warning_and_preserves_value(self):
        """An unrecognized code in a lookup field should log warning and keep value."""
        lookup = [
            {"field": 4, "id": "TB", "value": "Thoroughbred"},
        ]
        fields = self._make_fields_schema({4})
        row = [""] * 244
        row[3] = "XX"
        with self.assertLogs("src.translator", level="WARNING") as cm:
            result = apply_lookup_translations([row], fields, lookup)
        self.assertEqual(result[0][3], "XX")
        self.assertTrue(
            any("XX" in msg and "field 4" in msg for msg in cm.output)
        )

    def test_unknown_code_calls_progress_callback(self):
        """An unrecognized code should send the 'not found' message via progress."""
        lookup = [
            {"field": 4, "id": "TB", "value": "Thoroughbred"},
        ]
        fields = self._make_fields_schema({4})
        row = [""] * 244
        row[3] = "BF"
        messages = []
        with self.assertLogs("src.translator", level="WARNING"):
            apply_lookup_translations([row], fields, lookup,
                                      progress=messages.append)
        self.assertEqual(row[3], "BF")
        self.assertEqual(len(messages), 1)
        self.assertIn("BF for field 4 (Field4) was not found.", messages[0])

    def test_missing_field_in_lookup_logs_warning(self):
        """A field with hasOptions=true but no entries should log warning."""
        lookup = []
        fields = self._make_fields_schema({4})
        row = [""] * 244
        row[3] = "TB"
        with self.assertLogs("src.translator", level="WARNING") as cm:
            result = apply_lookup_translations([row], fields, lookup)
        self.assertEqual(result[0][3], "TB")
        self.assertTrue(
            any("field 4" in msg for msg in cm.output)
        )


class TestLookupRef(unittest.TestCase):
    """Verify that lookupRef in fields.json allows fields to share a lookup."""

    SHARED_LOOKUP = [
        {"field": 131, "id": "$", "value": "Super Bet"},
        {"field": 131, "id": "D", "value": "Daily Double"},
        {"field": 131, "id": "T", "value": "Trifecta"},
    ]

    def _make_fields_schema_with_ref(self, ref_fields):
        """Build a 244-entry fields schema where ref_fields use lookupRef=131."""
        schema = []
        for i in range(1, 245):
            entry = {
                "field": i,
                "name": f"Field{i}",
                "type": "Text",
                "maxLength": 10,
                "comments": "",
                "hasOptions": i in ref_fields or i == 131,
            }
            if i in ref_fields:
                entry["lookupRef"] = 131
            schema.append(entry)
        return schema

    def test_field_with_lookupref_translates_correctly(self):
        """A field with lookupRef should be translated using the referenced field's data."""
        fields = self._make_fields_schema_with_ref({137})
        row = [""] * 244
        row[136] = "D"  # Field 137 (0-based index 136) uses lookupRef=131
        result = apply_lookup_translations([row], fields, self.SHARED_LOOKUP)
        self.assertEqual(result[0][136], "Daily Double")

    def test_field_131_and_lookupref_field_resolve_same_options(self):
        """Field 131 and a field with lookupRef=131 should resolve identically."""
        fields = self._make_fields_schema_with_ref({137})
        # Field 131
        row_131 = [""] * 244
        row_131[130] = "T"  # index 130 = field 131
        # Field 137
        row_137 = [""] * 244
        row_137[136] = "T"  # index 136 = field 137
        apply_lookup_translations([row_131, row_137], fields, self.SHARED_LOOKUP)
        self.assertEqual(row_131[130], "Trifecta")
        self.assertEqual(row_137[136], "Trifecta")

    def test_multiple_fields_share_same_lookupref(self):
        """Multiple fields sharing the same lookupRef should all resolve correctly."""
        ref_fields = {137, 143, 239}
        fields = self._make_fields_schema_with_ref(ref_fields)
        row = [""] * 244
        row[136] = "$"   # Field 137
        row[142] = "D"   # Field 143
        row[238] = "T"   # Field 239
        result = apply_lookup_translations([row], fields, self.SHARED_LOOKUP)
        self.assertEqual(result[0][136], "Super Bet")
        self.assertEqual(result[0][142], "Daily Double")
        self.assertEqual(result[0][238], "Trifecta")

    def test_lookupref_validate_accepts_valid_codes(self):
        """validate_lookup_codes should accept valid codes for fields with lookupRef."""
        fields = self._make_fields_schema_with_ref({137})
        row = [""] * 244
        row[136] = "D"
        # Should not raise or warn
        validate_lookup_codes([row], fields, self.SHARED_LOOKUP, "test.txt")

    def test_lookupref_validate_warns_on_invalid_code(self):
        """validate_lookup_codes should warn for invalid codes even with lookupRef."""
        fields = self._make_fields_schema_with_ref({137})
        row = [""] * 244
        row[136] = "INVALID"
        with self.assertLogs("src.validator", level="WARNING") as cm:
            validate_lookup_codes([row], fields, self.SHARED_LOOKUP, "test.txt")
        self.assertTrue(any("INVALID" in msg for msg in cm.output))

    def test_real_scheme_fields_137_to_239_use_lookupref(self):
        """Fields 137, 143, ..., 239 in the real fields.json should have lookupRef=131."""
        import json as _json
        scheme_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scheme",
        )
        fields_path = os.path.join(scheme_dir, "fields.json")
        with open(fields_path, encoding="utf-8") as fh:
            fields = _json.load(fh)
        target = {131, 137, 143, 149, 155, 161, 167, 173, 179, 185, 191, 197,
                  203, 209, 215, 221, 227, 233, 239}
        for fdef in fields:
            if fdef["field"] in target:
                self.assertTrue(
                    fdef.get("hasOptions"),
                    f"Field {fdef['field']} should have hasOptions set",
                )
                if fdef["field"] != 131:
                    self.assertEqual(
                        fdef.get("lookupRef"), 131,
                        f"Field {fdef['field']} should have lookupRef=131",
                    )

    def test_no_duplicate_lookup_entries_in_lookup_json(self):
        """lookup.json should store the wager-type option set only under field 131."""
        from src.schema_loader import load_lookup_schema
        scheme_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "scheme",
        )
        lookup = load_lookup_schema(scheme_dir)
        shared_fields = {137, 143, 149, 155, 161, 167, 173, 179, 185, 191, 197,
                         203, 209, 215, 221, 227, 233, 239}
        duplicated = [e for e in lookup if e["field"] in shared_fields]
        self.assertEqual(
            duplicated, [],
            "lookup.json should not contain entries for the shared-ref fields "
            "(137, 143, ..., 239); they reference field 131 via lookupRef",
        )


if __name__ == "__main__":
    unittest.main()
