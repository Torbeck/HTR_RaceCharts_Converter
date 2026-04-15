"""Processor module for HTR chart processing.

Orchestrates the full processing pipeline:
1. Load scheme files
2. Parse HTR input file(s)
3. Validate rows, lookup codes, and distances
4. Optionally merge multiple files
5. Apply lookup translations
6. Export CSV and Excel
"""

import copy
import os
from typing import Callable, Dict, List, Optional, Set, Tuple

from src.schema_loader import (
    FieldsSchema,
    LookupTable,
    build_distance_lookup,
    get_column_formats,
    load_fields_schema,
    load_fractional_times,
    load_lookup_schema,
    load_points_of_call,
)
from src.output_settings import (
    apply_field_filter,
    read_output_settings,
    resolve_field_indices,
)
from src.translator import apply_lookup_translations, get_headers
from src.validator import validate_distances, validate_lookup_codes, validate_rows
from src.exporter import export_csv, export_excel
from src.utils.csv_utils import parse_htr_file
from src.utils.ini_utils import ExcelSettings, read_excel_settings, write_last_output


# Type for progress callback: (message: str) -> None
ProgressCallback = Callable[[str], None]


def _noop_progress(message: str) -> None:
    """Default no-op progress callback."""
    pass


def process_files(
    file_paths: List[str],
    scheme_dir: str,
    output_dir: str,
    merge: bool = False,
    progress: Optional[ProgressCallback] = None,
    config_path: Optional[str] = None,
) -> None:
    """Process one or more HTR files through the full pipeline.

    Args:
        file_paths: List of HTR .TXT file paths to process.
        scheme_dir: Directory containing scheme files.
        output_dir: Directory to write output files.
        merge: If True, merge all files into one unified output.
            If False, process each file individually.
        progress: Optional callback for progress messages.
        config_path: Optional path to config.ini. If provided, Excel
            formatting settings are loaded from it and last_output is
            persisted after successful export.

    Raises:
        FileNotFoundError: If any input or scheme file is missing.
        ValueError: On any validation failure.
    """
    if progress is None:
        progress = _noop_progress

    if not file_paths:
        raise ValueError("No input files provided.")

    # ── Step 0: Load Excel settings from config.ini ───────────────────
    # If config_path is provided, read per-table settings from the
    # [race_data], [points_call], and [fractional_times] sections.
    excel_settings: Optional[Dict[str, ExcelSettings]] = None
    field_indices: Optional[List[int]] = None
    if config_path is not None:
        progress("Loading Excel settings from config.ini...")
        excel_settings = read_excel_settings(config_path)

        # Load output field visibility / ordering settings
        progress("Loading output field settings from config.ini...")
        visible_raw, order_raw = read_output_settings(config_path)

    # ── Step 1: Load scheme files ─────────────────────────────────────
    progress("Loading scheme files...")
    fields_schema = load_fields_schema(scheme_dir)
    lookup_table = load_lookup_schema(scheme_dir)
    poc_headers, poc_rows = load_points_of_call(scheme_dir)
    ft_headers, ft_rows = load_fractional_times(scheme_dir)

    # Build distance sets for validation
    poc_distances: Set[str] = {row[0] for row in poc_rows}
    ft_distances: Set[str] = {row[0] for row in ft_rows}

    headers = get_headers(fields_schema)

    # Build column format list from field type specs in fields.json
    progress("Building Excel column formats from fields.json...")
    column_formats = get_column_formats(fields_schema, progress=progress)

    # Resolve output field visibility / ordering
    if config_path is not None:
        field_indices = resolve_field_indices(
            fields_schema, visible_raw, order_raw,
        )
        if field_indices is not None:
            progress(
                f"Output field filter active: "
                f"{len(field_indices)} of {len(fields_schema)} fields selected."
            )

    # ── Step 2: Parse and validate all files ──────────────────────────
    all_rows: List[List[str]] = []
    for file_path in file_paths:
        progress(f"Parsing {os.path.basename(file_path)}...")
        rows = parse_htr_file(file_path)

        progress(f"Validating {os.path.basename(file_path)}...")
        validate_rows(rows, file_path)
        validate_lookup_codes(rows, fields_schema, lookup_table, file_path)
        validate_distances(rows, fields_schema, poc_distances, ft_distances, file_path)

        all_rows.append(rows)
        progress(f"  {os.path.basename(file_path)}: {len(rows)} rows validated.")

    # ── Step 3: Merge or process individually ─────────────────────────
    if merge:
        progress("Merging all files...")
        merged = _merge_rows(all_rows)
        _translate_and_export(
            rows=merged,
            fields_schema=fields_schema,
            lookup_table=lookup_table,
            headers=headers,
            poc_data=(poc_headers, poc_rows),
            ft_data=(ft_headers, ft_rows),
            output_dir=output_dir,
            output_name="merged",
            progress=progress,
            excel_settings=excel_settings,
            column_formats=column_formats,
            field_indices=field_indices,
        )
    else:
        for file_path, rows in zip(file_paths, all_rows):
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            _translate_and_export(
                rows=rows,
                fields_schema=fields_schema,
                lookup_table=lookup_table,
                headers=headers,
                poc_data=(poc_headers, poc_rows),
                ft_data=(ft_headers, ft_rows),
                output_dir=output_dir,
                output_name=base_name,
                progress=progress,
                excel_settings=excel_settings,
                column_formats=column_formats,
                field_indices=field_indices,
            )

    # ── Step 4: Persist last output path ──────────────────────────────
    # After successful export, write the output directory to config.ini
    # so the GUI can preselect it on next launch.
    if config_path is not None:
        progress("Saving last output path to config.ini...")
        write_last_output(config_path, output_dir)

    progress("Processing complete.")


def _merge_rows(all_rows: List[List[List[str]]]) -> List[List[str]]:
    """Merge multiple file row-lists into a single list, preserving order.

    Args:
        all_rows: List of per-file row lists.

    Returns:
        Single flat list of all rows in original order.
    """
    merged: List[List[str]] = []
    for file_rows in all_rows:
        merged.extend(file_rows)
    return merged


def _translate_and_export(
    rows: List[List[str]],
    fields_schema: FieldsSchema,
    lookup_table: LookupTable,
    headers: List[str],
    poc_data: Tuple[List[str], List[List[str]]],
    ft_data: Tuple[List[str], List[List[str]]],
    output_dir: str,
    output_name: str,
    progress: ProgressCallback,
    excel_settings: Optional[Dict[str, ExcelSettings]] = None,
    column_formats: Optional[List[Optional[str]]] = None,
    field_indices: Optional[List[int]] = None,
) -> None:
    """Apply translations and export to CSV and Excel.

    Args:
        rows: Validated rows to process.
        fields_schema: Loaded fields schema.
        lookup_table: Loaded lookup table.
        headers: Column headers.
        poc_data: Points of call (headers, rows).
        ft_data: Fractional times (headers, rows).
        output_dir: Output directory.
        output_name: Base name for output files.
        progress: Progress callback.
        excel_settings: Optional dict of per-table ExcelSettings.
        column_formats: Optional list of Excel number-format strings for
            each column in sheet 1, derived from fields.json field types.
        field_indices: Optional list of 0-based column indices that
            defines the visible fields and their order for Excel export.
            ``None`` means use all fields in canonical order.
    """
    # Deep copy rows so translations don't mutate the originals
    translated_rows = copy.deepcopy(rows)

    progress(f"Applying lookup translations for {output_name}...")
    apply_lookup_translations(translated_rows, fields_schema, lookup_table,
                              progress=progress)

    # Export CSV (always uses the full canonical 244-column layout)
    csv_path = os.path.join(output_dir, f"{output_name}.csv")
    progress(f"Exporting CSV: {csv_path}")
    export_csv(translated_rows, headers, csv_path)

    # Apply field visibility / ordering for Excel export
    excel_headers = headers
    excel_rows = translated_rows
    excel_formats = column_formats
    if field_indices is not None:
        progress(f"Applying output field filter for {output_name}...")
        excel_headers, excel_rows, excel_formats = apply_field_filter(
            headers, translated_rows, column_formats, field_indices,
        )

    # Export Excel
    xlsx_path = os.path.join(output_dir, f"{output_name}.xlsx")
    progress(f"Exporting Excel: {xlsx_path}")
    export_excel(
        processed_headers=excel_headers,
        processed_rows=excel_rows,
        poc_data=poc_data,
        ft_data=ft_data,
        output_path=xlsx_path,
        excel_settings=excel_settings,
        column_formats=excel_formats,
    )

    progress(f"Finished exporting {output_name}.")
