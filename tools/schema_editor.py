# ──────────────────────────────────────────────────────────────────────
# HTR Race Charts Converter – Schema Editor (Developer Tool)
# Not part of the main program; for internal/developer use only.
# ──────────────────────────────────────────────────────────────────────

"""Standalone developer tool for safely editing JSON schema files.

Provides a Tkinter GUI that allows developers to view and edit:
- scheme/fields.json  (field definitions)
- scheme/lookup.json  (lookup translation tables)

Reuses the main application's modules for JSON loading, validation,
and type handling to ensure consistent behaviour and avoid duplication.

Usage:
    python -m tools.schema_editor          (from project root)
    python tools/schema_editor.py          (from project root)
"""

import json
import os
import sys
from typing import Any, Dict, List, Optional, Set

# ── Ensure project root is on sys.path so ``src.*`` imports work ─────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.schema_loader import (
    EXCEL_FORMATS,
    REQUIRED_FIELD_KEYS,
    VALID_TYPES,
    FieldsSchema,
    LookupTable,
    load_fields_schema,
    load_lookup_schema,
)

# ── Non-GUI helpers (testable without tkinter) ───────────────────────


def normalize_type(raw_type: str) -> str:
    """Return *raw_type* if it is a known type, otherwise ``'Text'``.

    Comparison is case-insensitive; the returned value always uses the
    canonical casing from :data:`VALID_TYPES`.
    """
    lower_map = {t.lower(): t for t in VALID_TYPES}
    return lower_map.get(raw_type.lower(), "Text") if raw_type else "Text"


def type_display_label(type_name: str) -> str:
    """Return a display string like ``'Text  (@)'`` for drop-down labels."""
    fmt = EXCEL_FORMATS.get(type_name, "")
    return f"{type_name}  ({fmt})" if fmt else type_name


def validate_fields_schema(data: FieldsSchema) -> List[str]:
    """Return a list of human-readable validation errors (empty = OK)."""
    errors: List[str] = []
    if not isinstance(data, list):
        errors.append("Schema must be a JSON array.")
        return errors

    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            errors.append(f"Entry {i} is not an object.")
            continue
        missing = REQUIRED_FIELD_KEYS - set(entry.keys())
        if missing:
            errors.append(
                f"Field {entry.get('field', '?')}: missing keys {missing}"
            )
        ftype = entry.get("type", "")
        if ftype and ftype not in VALID_TYPES:
            errors.append(
                f"Field {entry.get('field', '?')}: unknown type '{ftype}'"
            )
    return errors


def validate_lookup_refs(
    fields: FieldsSchema, lookup: LookupTable
) -> List[str]:
    """Validate that every ``lookupRef`` points to a valid lookup field."""
    errors: List[str] = []
    lookup_field_nums: Set[int] = {e["field"] for e in lookup}
    for entry in fields:
        ref = entry.get("lookupRef")
        if ref is not None and entry.get("hasOptions") == "Y":
            if ref not in lookup_field_nums:
                errors.append(
                    f"Field {entry['field']}: lookupRef={ref} not found in lookup.json"
                )
    return errors


def save_json(path: str, data: Any) -> None:
    """Write *data* to *path* as indented JSON, preserving key order."""
    with open(path, mode="w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")


def load_fields_json(path: str) -> FieldsSchema:
    """Load fields.json from an explicit file path (order-preserving)."""
    with open(path, mode="r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def load_lookup_json(path: str) -> LookupTable:
    """Load lookup.json from an explicit file path (order-preserving)."""
    with open(path, mode="r", encoding="utf-8") as f:
        data = json.load(f)
    return data


# ── GUI (only imported when tkinter is available) ────────────────────


class SchemaEditorApp:
    """Tkinter GUI for editing fields.json and lookup.json.

    Tkinter is imported lazily inside ``__init__`` so that the non-GUI
    helpers above can be imported and tested in headless environments.
    """

    def __init__(self, scheme_dir: str) -> None:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk

        self._tk = tk
        self._filedialog = filedialog
        self._messagebox = messagebox
        self._ttk = ttk

        self._scheme_dir = scheme_dir
        self._fields: FieldsSchema = []
        self._lookup: LookupTable = []
        self._fields_path = ""
        self._lookup_path = ""
        self._dirty = False
        self._current_index: Optional[int] = None

        self._root = tk.Tk()
        self._root.title("Schema Editor \u2013 Developer Tool")
        self._root.geometry("960x640")
        self._root.minsize(800, 500)
        self._app_icons: List[Any] = []
        self._set_app_icon()

        self._build_ui()
        self._load_scheme(scheme_dir)

    # ── UI construction ──────────────────────────────────────────────

    def _set_app_icon(self) -> None:
        """Load and set the schema editor window icon from assets/icons/apps."""
        tk = self._tk
        icon_dir = os.path.join(_PROJECT_ROOT, "assets", "icons", "apps")
        sizes = [512, 256, 128, 64, 32]
        icons = []
        for size in sizes:
            path = os.path.join(icon_dir, f"schema_editor_{size}.png")
            if os.path.isfile(path):
                try:
                    icons.append(tk.PhotoImage(file=path))
                except Exception:
                    pass
        if icons:
            self._root.iconphoto(True, *icons)
        self._app_icons = icons  # Prevent garbage collection

    def _build_ui(self) -> None:
        tk = self._tk
        ttk = self._ttk

        menu_bar = tk.Menu(self._root)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(
            label="Open scheme directory\u2026", command=self._on_open
        )
        file_menu.add_command(
            label="Save", command=self._on_save, accelerator="Ctrl+S"
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_exit)
        menu_bar.add_cascade(label="File", menu=file_menu)
        self._root.config(menu=menu_bar)
        self._root.bind("<Control-s>", lambda _e: self._on_save())

        # ── Paned layout: field list | editor ────────────────────────
        paned = ttk.PanedWindow(self._root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel – field list
        left = ttk.Frame(paned, width=300)
        paned.add(left, weight=1)

        ttk.Label(left, text="Fields (canonical order)").pack(anchor=tk.W)
        list_frame = ttk.Frame(left)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self._field_listbox = tk.Listbox(
            list_frame, selectmode=tk.SINGLE, exportselection=False
        )
        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self._field_listbox.yview
        )
        self._field_listbox.configure(yscrollcommand=scrollbar.set)
        self._field_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._field_listbox.bind("<<ListboxSelect>>", self._on_field_select)

        # Right panel – editor form
        right = ttk.Frame(paned, width=500)
        paned.add(right, weight=2)

        form = ttk.LabelFrame(right, text="Field Properties", padding=10)
        form.pack(fill=tk.BOTH, expand=True)

        # Field number (read-only)
        row = 0
        ttk.Label(form, text="Field #:").grid(
            row=row, column=0, sticky=tk.W, pady=2
        )
        self._field_num_var = tk.StringVar()
        ttk.Entry(
            form, textvariable=self._field_num_var, state="readonly", width=8
        ).grid(row=row, column=1, sticky=tk.W, pady=2)

        # Name
        row += 1
        ttk.Label(form, text="Name:").grid(
            row=row, column=0, sticky=tk.W, pady=2
        )
        self._name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self._name_var, width=40).grid(
            row=row, column=1, sticky=tk.W + tk.E, pady=2
        )

        # Type (drop-down with Excel format)
        row += 1
        ttk.Label(form, text="Type:").grid(
            row=row, column=0, sticky=tk.W, pady=2
        )
        type_frame = ttk.Frame(form)
        type_frame.grid(row=row, column=1, sticky=tk.W + tk.E, pady=2)

        self._type_var = tk.StringVar()
        self._type_combo = ttk.Combobox(
            type_frame,
            textvariable=self._type_var,
            values=VALID_TYPES,
            state="readonly",
            width=12,
        )
        self._type_combo.pack(side=tk.LEFT)
        self._type_combo.bind("<<ComboboxSelected>>", self._on_type_changed)

        self._excel_fmt_label = ttk.Label(
            type_frame, text="", foreground="gray"
        )
        self._excel_fmt_label.pack(side=tk.LEFT, padx=(10, 0))

        # maxLength
        row += 1
        ttk.Label(form, text="maxLength:").grid(
            row=row, column=0, sticky=tk.W, pady=2
        )
        self._maxlen_var = tk.StringVar()
        ttk.Entry(form, textvariable=self._maxlen_var, width=10).grid(
            row=row, column=1, sticky=tk.W, pady=2
        )

        # comments
        row += 1
        ttk.Label(form, text="Comments:").grid(
            row=row, column=0, sticky=tk.NW, pady=2
        )
        self._comments_text = tk.Text(form, height=4, width=50, wrap=tk.WORD)
        self._comments_text.grid(
            row=row, column=1, sticky=tk.W + tk.E, pady=2
        )

        # hasOptions
        row += 1
        ttk.Label(form, text="hasOptions:").grid(
            row=row, column=0, sticky=tk.W, pady=2
        )
        self._hasopts_var = tk.StringVar()
        self._hasopts_combo = ttk.Combobox(
            form,
            textvariable=self._hasopts_var,
            values=["", "Y"],
            state="readonly",
            width=5,
        )
        self._hasopts_combo.grid(row=row, column=1, sticky=tk.W, pady=2)

        # lookupRef (read-only display)
        row += 1
        ttk.Label(form, text="lookupRef:").grid(
            row=row, column=0, sticky=tk.W, pady=2
        )
        self._lookupref_var = tk.StringVar()
        ttk.Entry(
            form,
            textvariable=self._lookupref_var,
            state="readonly",
            width=10,
        ).grid(row=row, column=1, sticky=tk.W, pady=2)

        form.columnconfigure(1, weight=1)

        # ── Apply / Validate / Save buttons ──────────────────────────
        btn_frame = ttk.Frame(right)
        btn_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(
            btn_frame, text="Apply Changes", command=self._on_apply
        ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(
            btn_frame, text="Validate", command=self._on_validate
        ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(
            side=tk.LEFT
        )

        # ── Status bar ───────────────────────────────────────────────
        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(
            self._root, textvariable=self._status_var, relief=tk.SUNKEN
        ).pack(fill=tk.X, side=tk.BOTTOM)

    # ── Data loading ─────────────────────────────────────────────────

    def _load_scheme(self, scheme_dir: str) -> None:
        """Load fields.json and lookup.json from *scheme_dir*."""
        tk = self._tk
        messagebox = self._messagebox
        try:
            self._fields_path = os.path.join(scheme_dir, "fields.json")
            self._lookup_path = os.path.join(scheme_dir, "lookup.json")

            # Use the canonical loader from the main app for validation
            self._fields = load_fields_schema(scheme_dir)
            self._lookup = load_lookup_schema(scheme_dir)

            # Normalize unknown types to Text
            for entry in self._fields:
                entry["type"] = normalize_type(entry.get("type", ""))

            self._populate_field_list()
            self._dirty = False
            self._status_var.set(
                f"Loaded {len(self._fields)} fields, "
                f"{len(self._lookup)} lookup entries"
            )
        except Exception as e:
            messagebox.showerror("Load Error", str(e))
            self._status_var.set(f"Error: {e}")

    def _populate_field_list(self) -> None:
        """Fill the left-panel listbox with field numbers and names."""
        tk = self._tk
        self._field_listbox.delete(0, tk.END)
        for entry in self._fields:
            num = entry["field"]
            name = entry.get("name") or "(unnamed)"
            self._field_listbox.insert(tk.END, f"{num:>3}  {name}")

    # ── Selection handling ───────────────────────────────────────────

    def _on_field_select(self, _event: Any) -> None:
        sel = self._field_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        # Auto-apply pending edits from previous selection
        if self._current_index is not None and self._current_index != idx:
            self._apply_edits_to_model()
        self._current_index = idx
        self._load_field_into_form(idx)

    def _load_field_into_form(self, idx: int) -> None:
        tk = self._tk
        entry = self._fields[idx]
        self._field_num_var.set(str(entry["field"]))

        name = entry.get("name")
        self._name_var.set(name if name is not None else "")

        type_val = entry.get("type", "")
        self._type_var.set(type_val)
        self._update_excel_format_label(type_val)

        ml = entry.get("maxLength", "")
        self._maxlen_var.set(str(ml) if ml is not None else "")

        self._comments_text.delete("1.0", tk.END)
        comments = entry.get("comments", "")
        if comments:
            self._comments_text.insert("1.0", comments)

        self._hasopts_var.set(entry.get("hasOptions", ""))

        ref = entry.get("lookupRef")
        self._lookupref_var.set(str(ref) if ref is not None else "")

    def _update_excel_format_label(self, type_name: str) -> None:
        fmt = EXCEL_FORMATS.get(type_name, "")
        self._excel_fmt_label.configure(
            text=f"Excel: {fmt}" if fmt else ""
        )

    def _on_type_changed(self, _event: Any) -> None:
        self._update_excel_format_label(self._type_var.get())

    # ── Editing ──────────────────────────────────────────────────────

    def _apply_edits_to_model(self) -> None:
        """Write form values back to the in-memory model."""
        tk = self._tk
        idx = self._current_index
        if idx is None or idx >= len(self._fields):
            return
        entry = self._fields[idx]

        new_name = self._name_var.get()
        entry["name"] = new_name if new_name else None

        entry["type"] = self._type_var.get()

        raw_ml = self._maxlen_var.get().strip()
        if raw_ml == "":
            entry["maxLength"] = ""
        else:
            try:
                entry["maxLength"] = int(raw_ml)
            except ValueError:
                entry["maxLength"] = raw_ml

        entry["comments"] = self._comments_text.get("1.0", tk.END).strip()
        entry["hasOptions"] = self._hasopts_var.get()

        self._dirty = True

    def _on_apply(self) -> None:
        """Apply edits for the currently selected field."""
        messagebox = self._messagebox
        if self._current_index is None:
            messagebox.showinfo("Apply", "No field selected.")
            return
        self._apply_edits_to_model()
        # Refresh the list label in case the name changed
        entry = self._fields[self._current_index]
        label = f"{entry['field']:>3}  {entry.get('name') or '(unnamed)'}"
        self._field_listbox.delete(self._current_index)
        self._field_listbox.insert(self._current_index, label)
        self._field_listbox.selection_set(self._current_index)
        self._status_var.set(f"Applied changes to field {entry['field']}.")

    # ── Validation ───────────────────────────────────────────────────

    def _on_validate(self) -> None:
        messagebox = self._messagebox
        self._apply_edits_to_model()
        errors = validate_fields_schema(self._fields)
        errors.extend(validate_lookup_refs(self._fields, self._lookup))
        if errors:
            messagebox.showwarning(
                "Validation Errors",
                "\n".join(errors[:30]),
            )
            self._status_var.set(f"{len(errors)} validation error(s).")
        else:
            messagebox.showinfo("Validation", "Schema is valid.")
            self._status_var.set("Validation passed.")

    # ── Save ─────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        messagebox = self._messagebox
        self._apply_edits_to_model()
        errors = validate_fields_schema(self._fields)
        errors.extend(validate_lookup_refs(self._fields, self._lookup))
        if errors:
            proceed = messagebox.askyesno(
                "Validation Errors",
                f"{len(errors)} error(s) found:\n"
                + "\n".join(errors[:10])
                + "\n\nSave anyway?",
            )
            if not proceed:
                return
        try:
            save_json(self._fields_path, self._fields)
            self._dirty = False
            self._status_var.set(f"Saved {self._fields_path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))
            self._status_var.set(f"Save error: {e}")

    # ── File menu handlers ───────────────────────────────────────────

    def _on_open(self) -> None:
        filedialog = self._filedialog
        folder = filedialog.askdirectory(title="Select scheme directory")
        if folder:
            self._load_scheme(folder)

    def _on_exit(self) -> None:
        messagebox = self._messagebox
        if self._dirty:
            if not messagebox.askyesno(
                "Unsaved Changes", "Discard unsaved changes?"
            ):
                return
        self._root.destroy()

    # ── Run ──────────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the Tkinter main loop."""
        self._root.mainloop()


# ── CLI entry point ──────────────────────────────────────────────────


def main() -> None:
    """Resolve the scheme directory and launch the editor."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scheme_dir = os.path.join(project_root, "scheme")
    if not os.path.isdir(scheme_dir):
        print(
            f"FATAL: Scheme directory not found: {scheme_dir}",
            file=sys.stderr,
        )
        sys.exit(1)
    app = SchemaEditorApp(scheme_dir=scheme_dir)
    app.run()


if __name__ == "__main__":
    main()
