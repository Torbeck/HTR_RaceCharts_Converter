"""Schema loader for HTR chart processing.

Loads all authoritative data sources at runtime:
- fields.json: field definitions (1-244)
- lookup.json: lookup translation tables
- points_of_call.csv: distance → call1–call5 mappings
- race_fractional_times.csv: distance → f1–f5 mappings
"""

import csv
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.utils.file_utils import resolve_scheme_path


# ── Type aliases ──────────────────────────────────────────────────────
FieldDefinition = Dict[str, Any]
FieldsSchema = List[FieldDefinition]
LookupEntry = Dict[str, Any]
LookupTable = List[LookupEntry]
DistanceTable = Dict[str, List[str]]


REQUIRED_FIELD_KEYS = {"field", "name", "type", "maxLength", "comments", "hasOptions"}
EXPECTED_FIELD_COUNT = 244

# ── Excel format mapping ──────────────────────────────────────────────
# Maps canonical field "type" values (from fields.json) to Excel number
# format codes.  "General" is represented as None – openpyxl skips
# setting number_format when None is returned by get_column_formats().

EXCEL_FORMATS: Dict[str, str] = {
    "Text": "@",
    "Integer": "0",
    "Decimal": "0.00",
    "Date": "m/d/yyyy",
    "Currency": "$#,##0.00",
}

VALID_TYPES: List[str] = list(EXCEL_FORMATS.keys())

_logger = logging.getLogger(__name__)


def get_column_formats(
    fields_schema: FieldsSchema,
    progress: Optional[Callable[[str], None]] = None,
) -> List[Optional[str]]:
    """Return a list of Excel format strings for each column in fields_schema.

    For each field, looks up the ``"type"`` value in :data:`EXCEL_FORMATS`.
    If the type is missing or unknown, returns ``None`` (Excel General
    format) and logs a warning via the ``progress`` callback and the
    module-level logger.

    Args:
        fields_schema: List of field definitions loaded from fields.json.
        progress: Optional callback ``(str) -> None`` for progress/warning
            messages (e.g. the GUI log).  When provided, unmapped columns
            are also reported through this callback.

    Returns:
        List of Excel format strings (one per field), or ``None`` where
        the field type has no mapping (Excel will use General format).
    """
    formats: List[Optional[str]] = []
    for field_def in fields_schema:
        field_type = field_def.get("type", "")
        fmt = EXCEL_FORMATS.get(field_type) if field_type else None
        if fmt is None:
            field_num = field_def.get("field", "?")
            field_name = field_def.get("name", "?")
            msg = (
                f"Field {field_num} ({field_name!r}): type {field_type!r}"
                f" has no Excel format mapping; using General."
            )
            _logger.warning(msg)
            if progress is not None:
                progress(f"WARNING: {msg}")
        formats.append(fmt)
    return formats


def load_fields_schema(scheme_dir: str) -> FieldsSchema:
    """Load and validate fields.json.

    Args:
        scheme_dir: Directory containing scheme files.

    Returns:
        List of 244 field definition dicts, ordered by field number.

    Raises:
        FileNotFoundError: If fields.json does not exist.
        ValueError: If the schema is malformed or incomplete.
    """
    path = resolve_scheme_path(scheme_dir, "fields.json")
    with open(path, mode="r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"fields.json must be a JSON array, got {type(data).__name__}")

    if len(data) != EXPECTED_FIELD_COUNT:
        raise ValueError(
            f"fields.json must contain exactly {EXPECTED_FIELD_COUNT} field definitions, "
            f"got {len(data)}"
        )

    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(f"fields.json entry {i} is not an object")
        missing = REQUIRED_FIELD_KEYS - set(entry.keys())
        if missing:
            raise ValueError(
                f"fields.json entry {i} (field {entry.get('field', '?')}) "
                f"is missing keys: {missing}"
            )
        expected_field_num = i + 1
        if entry["field"] != expected_field_num:
            raise ValueError(
                f"fields.json entry {i} has field number {entry['field']}, "
                f"expected {expected_field_num}"
            )

    return data


def load_lookup_schema(scheme_dir: str) -> LookupTable:
    """Load and validate lookup.json.

    Args:
        scheme_dir: Directory containing scheme files.

    Returns:
        List of lookup entry dicts, each with 'field' (int), 'id', and 'value'.

    Raises:
        FileNotFoundError: If lookup.json does not exist.
        ValueError: If the schema is malformed.
    """
    path = resolve_scheme_path(scheme_dir, "lookup.json")
    with open(path, mode="r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"lookup.json must be a JSON array, got {type(data).__name__}")

    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(f"lookup.json entry {i} is not an object")
        if "field" not in entry or "id" not in entry or "value" not in entry:
            raise ValueError(
                f"lookup.json entry {i} missing 'field', 'id', or 'value'"
            )

    return data


def load_points_of_call(scheme_dir: str) -> Tuple[List[str], List[List[str]]]:
    """Load and validate points_of_call.csv.

    Args:
        scheme_dir: Directory containing scheme files.

    Returns:
        Tuple of (headers, rows) where headers is [distance, call1, ..., call5]
        and rows is a list of [distance, call1, ..., call5] value lists.

    Raises:
        FileNotFoundError: If points_of_call.csv does not exist.
        ValueError: If the file is malformed.
    """
    path = resolve_scheme_path(scheme_dir, "points_of_call.csv")
    return _load_distance_csv(path, "points_of_call.csv")


def load_fractional_times(scheme_dir: str) -> Tuple[List[str], List[List[str]]]:
    """Load and validate race_fractional_times.csv.

    Args:
        scheme_dir: Directory containing scheme files.

    Returns:
        Tuple of (headers, rows) where headers is [distance, f1, ..., f5]
        and rows is a list of [distance, f1, ..., f5] value lists.

    Raises:
        FileNotFoundError: If race_fractional_times.csv does not exist.
        ValueError: If the file is malformed.
    """
    path = resolve_scheme_path(scheme_dir, "race_fractional_times.csv")
    return _load_distance_csv(path, "race_fractional_times.csv")


def _load_distance_csv(
    path: str, filename: str
) -> Tuple[List[str], List[List[str]]]:
    """Load a distance-keyed CSV file (points of call or fractional times).

    Args:
        path: Full path to the CSV file.
        filename: Filename for error messages.

    Returns:
        Tuple of (headers, rows).

    Raises:
        ValueError: If the file has no header row or is empty.
    """
    with open(path, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        headers_row = next(reader, None)
        if headers_row is None:
            raise ValueError(f"{filename} is empty, expected header row")

        headers = [h.strip() for h in headers_row]
        expected_cols = len(headers)

        rows: List[List[str]] = []
        for line_num, row in enumerate(reader, start=2):
            # Strip whitespace from values
            cleaned = [v.strip() for v in row]
            # Pad short rows with empty strings (trailing commas may vary)
            while len(cleaned) < expected_cols:
                cleaned.append("")
            # Truncate extra empty trailing fields
            cleaned = cleaned[:expected_cols]
            rows.append(cleaned)

    if not rows:
        raise ValueError(f"{filename} has no data rows")

    return headers, rows


def build_distance_lookup(
    headers: List[str], rows: List[List[str]]
) -> Dict[str, Dict[str, str]]:
    """Build a dict mapping distance string → {call1: ..., call2: ..., ...}.

    Args:
        headers: Column headers (first is 'distance', rest are call/fraction names).
        rows: Data rows.

    Returns:
        Dict mapping distance value to dict of column name → value.

    Raises:
        ValueError: If duplicate distances are found.
    """
    lookup: Dict[str, Dict[str, str]] = {}
    for row in rows:
        distance = row[0]
        if distance in lookup:
            raise ValueError(f"Duplicate distance '{distance}' in lookup table")
        entry: Dict[str, str] = {}
        for col_idx in range(1, len(headers)):
            entry[headers[col_idx]] = row[col_idx] if col_idx < len(row) else ""
        lookup[distance] = entry
    return lookup
