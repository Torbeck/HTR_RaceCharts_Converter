"""Validation module for HTR chart processing.

Validates:
- Row field counts (exactly 244)
- Lookup codes exist in lookup.json for fields with hasOptions=true
- Distances exist in points_of_call and fractional_times tables
"""

import logging
from typing import Dict, List, Set, Tuple

from src.schema_loader import (
    FieldsSchema,
    LookupTable,
)
from src.utils.csv_utils import EXPECTED_FIELD_COUNT

logger = logging.getLogger(__name__)


def validate_rows(rows: List[List[str]], file_path: str) -> None:
    """Validate that all rows contain exactly 244 fields.

    Args:
        rows: Parsed rows (already normalized by csv_utils).
        file_path: File path for error reporting.

    Raises:
        ValueError: If any row does not contain exactly 244 fields.
    """
    for i, row in enumerate(rows, start=1):
        if len(row) != EXPECTED_FIELD_COUNT:
            raise ValueError(
                f"Row {i} in {file_path} has {len(row)} fields, "
                f"expected exactly {EXPECTED_FIELD_COUNT}."
            )


def validate_lookup_codes(
    rows: List[List[str]],
    fields_schema: FieldsSchema,
    lookup_table: LookupTable,
    file_path: str,
) -> None:
    """Validate that all non-blank lookup field values exist in lookup.json.

    For every field where hasOptions is true, each non-blank raw value is
    checked against lookup.json. Values not found are preserved and a
    warning is logged.

    Args:
        rows: Parsed data rows (244 fields each).
        fields_schema: Loaded fields.json schema.
        lookup_table: Loaded lookup.json.
        file_path: File path for error reporting.
    """
    # Build set of field indices (0-based) that require lookup
    lookup_field_indices: List[int] = []
    for field_def in fields_schema:
        if field_def.get("hasOptions"):
            lookup_field_indices.append(field_def["field"] - 1)  # 0-based

    # Build code-sets per field for fast lookup
    code_sets: Dict[int, Set[str]] = {}
    for idx in lookup_field_indices:
        field_num = idx + 1  # 1-based
        entries = [e for e in lookup_table if e["field"] == field_num]
        if not entries:
            logger.warning(
                "No lookup entries found for field %d (%s).",
                field_num,
                fields_schema[idx].get("name", "unknown"),
            )
            continue
        code_sets[idx] = {entry["id"] for entry in entries}

    # Validate each row
    for row_num, row in enumerate(rows, start=1):
        for idx in lookup_field_indices:
            if idx not in code_sets:
                continue
            raw_value = row[idx]
            # Blank fields are preserved as-is; no lookup required
            if raw_value == "":
                continue
            if raw_value not in code_sets[idx]:
                field_num = idx + 1
                field_name = fields_schema[idx].get("name", "unknown")
                logger.warning(
                    "%s for field %d (%s) was not found.",
                    raw_value,
                    field_num,
                    field_name,
                )


def _normalize_distance(value: str) -> str:
    """Normalize a distance string to a canonical decimal form.

    Strips trailing zeros after the decimal point so that '6.50' and '6.5'
    compare equal. Integer distances like '7.00' normalize to '7'.
    Field 5 is typed as Decimal in fields.json, so numeric normalization
    is appropriate.

    Args:
        value: Raw distance string.

    Returns:
        Normalized distance string.

    Raises:
        ValueError: If the value is not a valid decimal number.
    """
    try:
        # Convert to float then back to string to strip trailing zeros
        # Using Decimal for precision, but float is fine for furlong values
        num = float(value)
    except (ValueError, OverflowError) as e:
        raise ValueError(f"Invalid distance value '{value}': {e}") from e

    # Format: remove trailing zeros, remove trailing dot if integer
    normalized = f"{num:g}"
    return normalized


def build_normalized_distance_set(raw_distances: Set[str]) -> Dict[str, str]:
    """Build a mapping from normalized distance to original string.

    Args:
        raw_distances: Set of raw distance strings from a CSV file.

    Returns:
        Dict mapping normalized distance → original distance string.
    """
    result: Dict[str, str] = {}
    for d in raw_distances:
        normalized = _normalize_distance(d)
        result[normalized] = d
    return result


def validate_distances(
    rows: List[List[str]],
    fields_schema: FieldsSchema,
    poc_distances: Set[str],
    ft_distances: Set[str],
    file_path: str,
) -> None:
    """Validate that all distance values exist in points_of_call and fractional_times.

    The distance field is field 5 (0-based index 4). Comparison is done
    numerically to handle formatting differences (e.g. '6.50' vs '6.5').

    Args:
        rows: Parsed data rows.
        fields_schema: Loaded fields.json schema.
        poc_distances: Set of valid distances from points_of_call.csv.
        ft_distances: Set of valid distances from race_fractional_times.csv.
        file_path: File path for error reporting.

    Raises:
        ValueError: If a distance is not found in either lookup table.
    """
    distance_idx = 4  # Field 5 is at 0-based index 4

    # Normalize reference distance sets for comparison
    poc_normalized = {_normalize_distance(d) for d in poc_distances}
    ft_normalized = {_normalize_distance(d) for d in ft_distances}

    for row_num, row in enumerate(rows, start=1):
        distance = row[distance_idx]
        if distance == "":
            continue  # Blank distance preserved as-is

        normalized = _normalize_distance(distance)

        if normalized not in poc_normalized:
            raise ValueError(
                f"Row {row_num} in {file_path}: distance '{distance}' "
                f"not found in points_of_call.csv."
            )
        if normalized not in ft_normalized:
            raise ValueError(
                f"Row {row_num} in {file_path}: distance '{distance}' "
                f"not found in race_fractional_times.csv."
            )
