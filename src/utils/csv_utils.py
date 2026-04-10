"""CSV reading and writing utilities for HTR chart processing."""

import csv
import io
from typing import List


EXPECTED_FIELD_COUNT = 244


def parse_htr_file(file_path: str) -> List[List[str]]:
    """Parse an HTR .TXT file as CSV and return all rows.

    Each row is normalized to exactly 244 fields. A trailing comma artifact
    (producing 245 fields with an empty last element) is handled by stripping
    the trailing empty field.

    Args:
        file_path: Path to the HTR .TXT file.

    Returns:
        List of rows, each row being a list of 244 string values.

    Raises:
        ValueError: If any row does not contain exactly 244 fields after
            trailing-comma normalization, or if the file is not valid CSV.
    """
    rows: List[List[str]] = []
    try:
        with open(file_path, mode="r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            for line_num, row in enumerate(reader, start=1):
                normalized = _normalize_row(row, line_num, file_path)
                rows.append(normalized)
    except csv.Error as e:
        raise ValueError(
            f"Invalid CSV in file {file_path}: {e}"
        ) from e
    return rows


def _normalize_row(
    row: List[str], line_num: int, file_path: str
) -> List[str]:
    """Normalize a parsed CSV row to exactly 244 fields.

    Handles the trailing-comma artifact where csv.reader produces 245 fields
    with the last being an empty string.

    Args:
        row: Parsed CSV row.
        line_num: 1-based line number for error reporting.
        file_path: File path for error reporting.

    Returns:
        Row with exactly 244 fields.

    Raises:
        ValueError: If the row cannot be normalized to 244 fields.
    """
    field_count = len(row)

    if field_count == EXPECTED_FIELD_COUNT:
        return row
    elif field_count == EXPECTED_FIELD_COUNT + 1 and row[-1] == "":
        # Trailing comma artifact: strip the extra empty field
        return row[:EXPECTED_FIELD_COUNT]
    else:
        raise ValueError(
            f"Row {line_num} in {file_path} has {field_count} fields, "
            f"expected exactly {EXPECTED_FIELD_COUNT}."
        )


def write_csv(
    rows: List[List[str]],
    headers: List[str],
    output_path: str,
) -> None:
    """Write rows with headers to a CSV file.

    Args:
        rows: List of rows to write.
        headers: Column headers.
        output_path: Path to write the CSV file.

    Raises:
        ValueError: If any row does not have 244 fields.
        PermissionError: If the file is locked by another application.
    """
    from src.utils.file_utils import check_file_writable

    check_file_writable(output_path)
    with open(output_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for i, row in enumerate(rows, start=1):
            if len(row) != EXPECTED_FIELD_COUNT:
                raise ValueError(
                    f"Row {i} has {len(row)} fields during CSV export, "
                    f"expected {EXPECTED_FIELD_COUNT}."
                )
            writer.writerow(row)
