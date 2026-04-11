"""Translator module for HTR chart processing.

Applies lookup translations to fields where hasOptions is true,
replacing raw codes with human-readable values from lookup.json.
Blank fields are preserved as-is.
"""

import logging
from typing import Callable, Dict, List, Optional, Set

from src.schema_loader import FieldsSchema, LookupTable

logger = logging.getLogger(__name__)


def apply_lookup_translations(
    rows: List[List[str]],
    fields_schema: FieldsSchema,
    lookup_table: LookupTable,
    progress: Optional[Callable[[str], None]] = None,
) -> List[List[str]]:
    """Apply lookup translations to all rows.

    For every field where hasOptions is true, replace the raw code with the
    human-readable value from lookup.json. Blank values are preserved.
    Values not found in the lookup are preserved and a warning is logged.

    Args:
        rows: Parsed data rows (244 fields each). These are modified in place
            and also returned.
        fields_schema: Loaded fields.json schema.
        lookup_table: Loaded lookup.json.
        progress: Optional callback for progress/warning messages
            (e.g. GUI log display).

    Returns:
        The same rows list with translated values.
    """
    # Build translation dicts: field_index (0-based) → {id: value}
    translation_maps: Dict[int, Dict[str, str]] = {}
    for field_def in fields_schema:
        if field_def.get("hasOptions"):
            field_num = field_def["field"]
            field_idx = field_num - 1  # 0-based

            lookup_field_num = field_def.get("lookupRef", field_num)
            entries = [e for e in lookup_table if e["field"] == lookup_field_num]
            if not entries:
                logger.warning(
                    "No lookup entries found for field %d (%s).",
                    field_num,
                    field_def.get("name", "unknown"),
                )
                continue

            code_map: Dict[str, str] = {}
            for entry in entries:
                code_map[entry["id"]] = entry["value"]
            translation_maps[field_idx] = code_map

    # Apply translations
    for row_num, row in enumerate(rows, start=1):
        for field_idx, code_map in translation_maps.items():
            raw_value = row[field_idx]
            if raw_value == "":
                continue  # Preserve blanks
            if raw_value not in code_map:
                field_num = field_idx + 1
                field_name = fields_schema[field_idx].get("name", "unknown")
                msg = (
                    f"{raw_value} for field {field_num} ({field_name})"
                    " was not found."
                )
                logger.warning("%s", msg)
                if progress is not None:
                    progress(msg)
                continue
            row[field_idx] = code_map[raw_value]

    return rows


def get_headers(fields_schema: FieldsSchema) -> List[str]:
    """Extract column headers from the fields schema.

    For fields with a null name (unused fields), the header is
    'Field_<number>' to maintain the exact 244-column structure.

    Args:
        fields_schema: Loaded fields.json schema.

    Returns:
        List of 244 header strings.
    """
    headers: List[str] = []
    for field_def in fields_schema:
        name = field_def.get("name")
        if name is None:
            headers.append(f"Field_{field_def['field']}")
        else:
            headers.append(name)
    return headers
