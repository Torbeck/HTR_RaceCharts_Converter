# ProjectStructure.md
A deterministic blueprint for the HTR Chart Processing Application

__Created: 04-02-2026 by Ken Torbeck__
__Updated: 04-05-2026 by Ken Torbeck__

---

# 1. Project Overview

This project processes HTR chart CSV files (exported as `.TXT`) using a strict schema defined by:

- `fields.json`
- `lookup.json`
- `points_of_call.csv`
- `race_fractional_times.csv`

The program loads these schema files, validates and transforms the HTR data, applies lookup translations, and exports:

- A processed CSV
- An Excel workbook with three sheets
- Optional merging of multiple HTR files
- A GUI for file selection and drag‑and‑drop launching

All behavior must be deterministic, schema‑driven, and free of assumptions.

---

## 2. Project Folder Layout

```text
project_root/
│
├── main.py
│
├── gui/
│   ├── __init__.py
│   ├── app.py
│   └── dragdrop.py
│
├── core/
│   ├── __init__.py
│   ├── loader.py
│   ├── validator.py
│   ├── transformer.py
│   ├── exporter.py
│   └── merger.py
│
├── schema/
│   ├── fields.json
│   ├── lookup.json
│   ├── points_of_call.csv
│   └── race_fractional_times.csv
│
├── sample_data/
│   ├── AQU0322F.TXT
│   ├── FG0322F.TXT
│   ├── GP0322F.TXT
│   ├── OP0322F.TXT
│   ├── PHA0324F.TXT
│   ├── SA0322F.TXT
│   ├── TAM0318F.TXT
│   ├── TP0312F.TXT
│   └── TP0321F.TXT
│
└── FeatureRequirements.txt


---

# 3. Module Responsibilities

## main.py
- Entry point for the application
- Launches GUI
- Or runs CLI mode (optional)

---

## gui/app.py
- Main GUI window
- File selection dialogs
- Options panel (merge files, etc.)
- “Start Processing” button
- Error dialogs and validation messages

## gui/dragdrop.py
- Handles drag‑and‑drop of files or folders
- Populates GUI file list
- Does not auto‑start processing

---

## core/loader.py
Responsible for all file loading, including:

- Reading HTR `.TXT` files as CSV
- Ensuring exactly **244 fields** per row
- Preserving blank fields
- Loading JSON schema files
- Loading CSV lookup tables

Functions include:

- `load_htr_file(path)`
- `load_fields_schema(path)`
- `load_lookup_schema(path)`
- `load_points_of_call(path)`
- `load_fractional_times(path)`

---

## core/validator.py
Responsible for schema validation, including:

- Validating field counts
- Validating field types (text, integer, decimal)
- Validating lookup codes exist
- Validating distance exists in both lookup tables

Functions include:

- `validate_row(row, fields_schema)`
- `validate_distance(distance, points_of_call, fractional_times)`

---

## core/transformer.py
Responsible for data transformation, including:

- Adding headers
- Applying lookup translations
- Mapping distances to call structures
- Preparing rows for export

Functions include:

- `apply_headers(rows, fields_schema)`
- `apply_lookup_translations(rows, lookup_schema)`
- `attach_call_data(rows, points_of_call, fractional_times)`

---

## core/merger.py
Responsible for:

- Combining multiple HTR files into one table
- Ensuring consistent schema across files

Functions include:

- `merge_htr_files(list_of_paths)`

---

## core/exporter.py
Responsible for:

- Exporting processed CSV
- Building Excel workbook with 3 sheets
- Ensuring deterministic formatting

Functions include:

- `export_csv(rows, output_path)`
- `export_excel(processed_rows, points_of_call, fractional_times, output_path)`

---

# 4. Data Flow

Multiple HTR TXT → merger → loader → validator → transformer → exporter


GUI wraps this entire flow.

---

# 5. GUI Behavior Requirements

- User selects one or more HTR files
- Or drags files/folder onto the window
- User must press **Start** to begin
- GUI validates file types
- GUI displays progress and errors
- GUI writes output files to user‑selected location

---

# 6. Deterministic Rules

- No invented fields
- No inferred logic
- No guessing
- All transformations must come from schema files
- All blank fields must be preserved
- All rows must contain exactly 244 fields
- Fail loudly on schema mismatch

---

# 7. Future Extensions (Optional)

- Track code cross‑reference
- Race condition code cross‑reference
- CLI mode
- Logging module
