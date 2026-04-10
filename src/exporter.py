"""Exporter module for HTR chart processing.

Exports processed data to:
- CSV with headers and translated values
- Excel workbook with 3 sheets (formatted per INI settings)
"""

from typing import Dict, List, Optional, Tuple

from src.utils.csv_utils import write_csv
from src.utils.excel_utils import build_workbook
from src.utils.ini_utils import ExcelSettings


def export_csv(
    rows: List[List[str]],
    headers: List[str],
    output_path: str,
) -> None:
    """Export processed rows to a CSV file with headers.

    Args:
        rows: Translated data rows (244 fields each).
        headers: Column headers (244 items).
        output_path: Path to write the output CSV.
    """
    write_csv(rows, headers, output_path)


def export_excel(
    processed_headers: List[str],
    processed_rows: List[List[str]],
    poc_data: Tuple[List[str], List[List[str]]],
    ft_data: Tuple[List[str], List[List[str]]],
    output_path: str,
    excel_settings: Optional[Dict[str, ExcelSettings]] = None,
) -> None:
    """Export processed data and reference tables to an Excel workbook.

    Sheet 1: Processed race data (with headers and lookup translations).
    Sheet 2: Points of Call by Distance.
    Sheet 3: Race Fractional Times by Distance.

    Args:
        processed_headers: Column headers for sheet 1.
        processed_rows: Data rows for sheet 1.
        poc_data: Tuple of (headers, rows) for points_of_call.csv.
        ft_data: Tuple of (headers, rows) for race_fractional_times.csv.
        output_path: Path to write the .xlsx file.
        excel_settings: Optional dict of per-table ExcelSettings.
    """
    poc_headers, poc_rows = poc_data
    ft_headers, ft_rows = ft_data

    build_workbook(
        processed_headers=processed_headers,
        processed_rows=processed_rows,
        points_of_call_headers=poc_headers,
        points_of_call_rows=poc_rows,
        fractional_times_headers=ft_headers,
        fractional_times_rows=ft_rows,
        output_path=output_path,
        excel_settings=excel_settings,
    )
