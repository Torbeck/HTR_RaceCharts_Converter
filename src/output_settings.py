"""Output customization settings for HTR chart processing.

Reads and writes the ``[output]`` section in config.ini:

- ``visible_fields``: Controls which fields appear in the Excel export.
  - Default: ``"all"`` (include every field from fields.json).
  - Custom: comma-separated list of 1-based field numbers, e.g. ``"1,2,3,5"``

- ``custom_order``: Controls the column order in the Excel export.
  - Default: ``"default"`` (use the order from fields.json).
  - Custom: comma-separated list of 1-based field numbers, e.g. ``"3,1,2,5"``

This module never modifies fields.json.  All user preferences are stored
exclusively in config.ini.
"""

import os
import re
from typing import List, Optional, Tuple

from src.schema_loader import FieldsSchema


# ── Defaults ──────────────────────────────────────────────────────────

DEFAULT_VISIBLE_FIELDS = "all"
DEFAULT_CUSTOM_ORDER = "default"


# ── Parsing helpers ───────────────────────────────────────────────────

def _parse_int_list(raw: str) -> List[int]:
    """Parse a comma-separated string of integers.

    Whitespace around values is stripped.  Empty strings and non-integer
    tokens are silently ignored.

    Args:
        raw: Comma-separated string (e.g. ``"1, 2 ,3"``).

    Returns:
        List of parsed integers.
    """
    result: List[int] = []
    for token in raw.split(","):
        token = token.strip()
        if token and re.fullmatch(r"\d+", token):
            result.append(int(token))
    return result


# ── Reading from config ───────────────────────────────────────────────

def read_output_settings(config_path: str) -> Tuple[str, str]:
    """Read ``[output]`` settings from config.ini.

    Falls back to defaults when the section or keys are missing.

    Args:
        config_path: Absolute path to config.ini.

    Returns:
        Tuple of (visible_fields, custom_order) raw strings.
    """
    from src.utils.ini_utils import load_config

    parser = load_config(config_path)
    visible = parser.get("output", "visible_fields",
                         fallback=DEFAULT_VISIBLE_FIELDS).strip()
    order = parser.get("output", "custom_order",
                       fallback=DEFAULT_CUSTOM_ORDER).strip()
    return visible, order


def write_output_settings(
    config_path: str,
    visible_fields: str,
    custom_order: str,
) -> None:
    """Write ``[output]`` settings to config.ini.

    Preserves all existing sections and keys.

    Args:
        config_path: Absolute path to config.ini.
        visible_fields: Raw value for ``visible_fields``.
        custom_order: Raw value for ``custom_order``.
    """
    from src.utils.ini_utils import load_config

    parser = load_config(config_path)
    if not parser.has_section("output"):
        parser.add_section("output")
    parser.set("output", "visible_fields", visible_fields)
    parser.set("output", "custom_order", custom_order)

    with open(config_path, mode="w", encoding="utf-8") as f:
        parser.write(f)


# ── Resolve final field list ──────────────────────────────────────────

def resolve_field_indices(
    fields_schema: FieldsSchema,
    visible_fields_raw: str,
    custom_order_raw: str,
) -> Optional[List[int]]:
    """Compute the final ordered list of 0-based column indices.

    Implements the algorithm from the issue spec::

        order  = custom_order if custom_order != "default" else default_order
        visible = visible_fields if visible_fields != "all" else default_order
        final  = [f for f in order if f in visible]

    Args:
        fields_schema: The canonical field list from fields.json.
        visible_fields_raw: Raw ``visible_fields`` value from config.ini.
        custom_order_raw: Raw ``custom_order`` value from config.ini.

    Returns:
        ``None`` when both settings are at their defaults (meaning
        "use all fields in canonical order — no filtering needed").
        Otherwise a list of 0-based column indices in the desired order.
    """
    # Fast path: both defaults → no transformation needed
    if (visible_fields_raw.lower() == "all"
            and custom_order_raw.lower() == "default"):
        return None

    total_fields = len(fields_schema)
    default_order = list(range(1, total_fields + 1))  # 1-based field numbers

    # Determine ordering
    if custom_order_raw.lower() != "default":
        order = _parse_int_list(custom_order_raw)
        # Filter out invalid field numbers
        valid = set(default_order)
        order = [f for f in order if f in valid]
        # Append any fields not explicitly listed (keeps output deterministic)
        listed = set(order)
        for f in default_order:
            if f not in listed:
                order.append(f)
    else:
        order = list(default_order)

    # Determine visibility
    if visible_fields_raw.lower() != "all":
        visible_set = set(_parse_int_list(visible_fields_raw))
        # Only keep valid field numbers
        valid = set(default_order)
        visible_set = visible_set & valid
    else:
        visible_set = set(default_order)

    # Final list: ordered, visible
    final = [f for f in order if f in visible_set]

    # Convert to 0-based indices
    return [f - 1 for f in final]


def apply_field_filter(
    headers: List[str],
    rows: List[List[str]],
    column_formats: Optional[List[Optional[str]]],
    indices: List[int],
) -> Tuple[List[str], List[List[str]], Optional[List[Optional[str]]]]:
    """Filter and reorder headers, rows, and column formats.

    Args:
        headers: Full list of column headers (244 items).
        rows: Data rows (each with 244 fields).
        column_formats: Optional list of Excel format strings (244 items),
            or ``None``.
        indices: 0-based column indices in the desired order.

    Returns:
        Tuple of (filtered_headers, filtered_rows, filtered_formats).
    """
    filtered_headers = [headers[i] for i in indices]
    filtered_rows = [[row[i] for i in indices] for row in rows]
    filtered_formats: Optional[List[Optional[str]]] = None
    if column_formats is not None:
        filtered_formats = [column_formats[i] for i in indices]
    return filtered_headers, filtered_rows, filtered_formats


# ── Customized-output helpers ─────────────────────────────────────────

def is_customized(field_indices: Optional[List[int]]) -> bool:
    """Return ``True`` when the output is customized.

    A non-``None`` *field_indices* value means the user has changed field
    visibility, ordering, or both.
    """
    return field_indices is not None


def write_field_list(
    output_dir: str,
    output_name: str,
    headers: List[str],
    field_indices: List[int],
) -> str:
    """Write a companion ``.txt`` file listing the customized fields.

    Each line shows the position, original field number, and field name
    so users can quickly verify the structure of their customized output.

    Args:
        output_dir: Directory for the output file.
        output_name: Base filename (should already include
            ``_customized`` suffix).
        headers: Full list of column headers (canonical order).
        field_indices: 0-based column indices in the desired order.

    Returns:
        The absolute path to the written ``.txt`` file.
    """
    txt_path = os.path.join(output_dir, f"{output_name}.txt")
    lines: List[str] = ["Customized Output Fields", "=" * 24, ""]
    for position, idx in enumerate(field_indices, start=1):
        field_num = idx + 1  # convert back to 1-based
        name = headers[idx]
        lines.append(f"{position}. {name} (Field #{field_num})")
    lines.append("")  # trailing newline

    with open(txt_path, mode="w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return txt_path
