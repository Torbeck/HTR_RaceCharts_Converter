"""Excel workbook utilities for HTR chart processing.

Builds the 3-sheet Excel workbook:
- Sheet 1 (Processed Race Data): formatted per [race_data] INI settings.
- Sheet 2 (Points of Call by Distance): formatted per [points_call] INI settings.
- Sheet 3 (Fractional Times by Distance): formatted per [fractional_times] INI settings.
"""

from typing import Dict, List, Optional

import openpyxl

from src.utils.ini_utils import ExcelSettings
from src.utils.formatting_utils import apply_sheet_formatting


def build_workbook(
    processed_headers: List[str],
    processed_rows: List[List[str]],
    points_of_call_headers: List[str],
    points_of_call_rows: List[List[str]],
    fractional_times_headers: List[str],
    fractional_times_rows: List[List[str]],
    output_path: str,
    excel_settings: Optional[Dict[str, ExcelSettings]] = None,
) -> None:
    """Build and save an Excel workbook with three sheets.

    Sheet 1: Processed race data (headers + translated rows).
    Sheet 2: Points of Call by Distance.
    Sheet 3: Race Fractional Times by Distance.

    Each sheet's formatting is driven by its corresponding entry in
    excel_settings (keyed by 'race_data', 'points_call',
    'fractional_times').

    Args:
        processed_headers: Column headers for sheet 1.
        processed_rows: Data rows for sheet 1.
        points_of_call_headers: Column headers for sheet 2.
        points_of_call_rows: Data rows for sheet 2.
        fractional_times_headers: Column headers for sheet 3.
        fractional_times_rows: Data rows for sheet 3.
        output_path: Path to write the .xlsx file.
        excel_settings: Optional dict of per-table ExcelSettings from
            config.ini.  If provided, applies formatting to all sheets.
    """
    wb = openpyxl.Workbook()

    # ── Sheet 1: Processed Race Data ──────────────────────────────────
    ws1 = wb.active
    ws1.title = "Processed Race Data"
    _write_sheet(ws1, processed_headers, processed_rows)

    if excel_settings and "race_data" in excel_settings:
        apply_sheet_formatting(
            ws1,
            table_name="race_data",
            row_count=1 + len(processed_rows),
            col_count=len(processed_headers),
            settings=excel_settings["race_data"],
        )

    # ── Sheet 2: Points of Call by Distance ───────────────────────────
    ws2 = wb.create_sheet(title="Points of Call by Distance")
    _write_sheet(ws2, points_of_call_headers, points_of_call_rows)

    if excel_settings and "points_call" in excel_settings:
        apply_sheet_formatting(
            ws2,
            table_name="points_call",
            row_count=1 + len(points_of_call_rows),
            col_count=len(points_of_call_headers),
            settings=excel_settings["points_call"],
        )

    # ── Sheet 3: Fractional Times by Distance ─────────────────────────
    ws3 = wb.create_sheet(title="Fractional Times by Distance")
    _write_sheet(ws3, fractional_times_headers, fractional_times_rows)

    if excel_settings and "fractional_times" in excel_settings:
        apply_sheet_formatting(
            ws3,
            table_name="fractional_times",
            row_count=1 + len(fractional_times_rows),
            col_count=len(fractional_times_headers),
            settings=excel_settings["fractional_times"],
        )

    from src.utils.file_utils import check_file_writable

    check_file_writable(output_path)
    wb.save(output_path)


def _write_sheet(
    ws: openpyxl.worksheet.worksheet.Worksheet,
    headers: List[str],
    rows: List[List[str]],
) -> None:
    """Write headers and rows to a worksheet.

    Args:
        ws: The openpyxl worksheet.
        headers: Column headers.
        rows: Data rows.
    """
    ws.append(headers)
    for row in rows:
        ws.append(row)
