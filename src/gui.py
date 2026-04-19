"""GUI module for HTR chart processing.

Provides a tkinter-based GUI with:
- File selection via dialog and drag-and-drop
- Merge mode toggle
- Output directory chooser
- Start button (processing never auto-starts)
- Progress log and error display
"""

import os
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, List, Optional

from src.processor import process_files
from src.utils.file_utils import (
    collect_txt_files,
    resolve_existing_directory,
    validate_file_extension,
)
from src.utils.ini_utils import read_last_output, rebuild_config
from src.output_settings import (
    output_is_customized,
    read_output_settings,
    reset_output_settings,
    write_output_settings,
)
from src.version import __version__

_ICON_DIR = (
    Path(__file__).resolve().parent.parent / "assets" / "icons" / "apps"
)


class HTRApp:
    """Main application window for HTR chart processing."""

    def __init__(self, scheme_dir: str, config_path: str) -> None:
        """Initialize the application.

        Args:
            scheme_dir: Path to the directory containing scheme files.
            config_path: Absolute path to config.ini. Used for:
                - Preselecting the last output directory on launch.
                - Passing to process_files so it can read Excel settings
                  and persist the output path after export.
        """
        self._scheme_dir = scheme_dir
        self._config_path = config_path
        self._file_paths: List[str] = []
        self._processing = False
        self._dnd_available = False

        # Create the root window. Use TkinterDnD.Tk() if tkinterdnd2 is
        # installed so that drag-and-drop is supported; fall back to
        # standard tk.Tk() otherwise.
        try:
            from tkinterdnd2 import TkinterDnD
            self._root = TkinterDnD.Tk()
            self._dnd_available = True
        except Exception:
            self._root = tk.Tk()

        self._root.title("HTR Chart Processor")
        self._root.geometry("800x620")
        self._root.minsize(700, 550)
        self._app_icons: List[tk.PhotoImage] = []
        self._set_app_icon()

        self._build_ui()
        self._setup_drag_and_drop()

        # ── Preselect last output directory from config.ini ───────────
        # read_last_output returns None when the value is "Default" or
        # missing.  In that case we leave the output field empty; it
        # will be auto-filled to the input file's directory when the
        # user adds files (see _add_files).
        last_output = read_last_output(config_path)
        if last_output:
            try:
                self._output_var.set(resolve_existing_directory(last_output))
            except (FileNotFoundError, ValueError):
                pass

        self._update_output_indicator()

    def run(self) -> None:
        """Start the tkinter main loop."""
        self._root.mainloop()

    # ── UI Construction ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build all UI components."""
        # ── Menu Bar ──────────────────────────────────────────────────
        menu_bar = tk.Menu(self._root)
        tools_menu = tk.Menu(menu_bar, tearoff=0)
        tools_menu.add_command(
            label="Rebuild config.ini", command=self._on_rebuild_config
        )
        menu_bar.add_cascade(label="Tools", menu=tools_menu)

        output_menu = tk.Menu(menu_bar, tearoff=0)
        output_menu.add_command(
            label="Field Visibility...", command=self._on_field_visibility
        )
        output_menu.add_command(
            label="Field Ordering...", command=self._on_field_ordering
        )
        menu_bar.add_cascade(label="Output", menu=output_menu)

        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="About", command=self._on_about)
        menu_bar.add_cascade(label="Help", menu=help_menu)

        self._root.config(menu=menu_bar)

        main_frame = ttk.Frame(self._root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ── File List Section ─────────────────────────────────────────
        file_frame = ttk.LabelFrame(main_frame, text="HTR Files", padding=5)
        file_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        self._file_listbox = tk.Listbox(
            file_frame, selectmode=tk.EXTENDED, height=10
        )
        file_scrollbar = ttk.Scrollbar(
            file_frame, orient=tk.VERTICAL, command=self._file_listbox.yview
        )
        self._file_listbox.configure(yscrollcommand=file_scrollbar.set)

        self._file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        file_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ── File Buttons ──────────────────────────────────────────────
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(
            btn_frame, text="Add Files...", command=self._on_add_files
        ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(
            btn_frame, text="Add Folder...", command=self._on_add_folder
        ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(
            btn_frame, text="Remove Selected", command=self._on_remove_selected
        ).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(
            btn_frame, text="Clear All", command=self._on_clear_all
        ).pack(side=tk.LEFT)

        # ── Options Section ───────────────────────────────────────────
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding=5)
        options_frame.pack(fill=tk.X, pady=(0, 5))

        self._merge_var = tk.BooleanVar(value=False)
        self._merge_check = ttk.Checkbutton(
            options_frame, text="Merge all files into one output",
            variable=self._merge_var,
        )
        self._merge_check.pack(side=tk.LEFT)
        self._merge_check.state(["disabled"])

        # ── Output Customization Indicator ────────────────────────────
        self._reset_output_btn = ttk.Button(
            options_frame,
            text="Reset to Default",
            command=self._on_reset_output,
        )
        self._reset_output_btn.pack(side=tk.RIGHT, padx=(5, 0))

        self._output_indicator_var = tk.StringVar(value="")
        self._output_indicator_label = ttk.Label(
            options_frame, textvariable=self._output_indicator_var,
        )
        self._output_indicator_label.pack(side=tk.RIGHT)

        # ── Output Directory Section ──────────────────────────────────
        output_frame = ttk.LabelFrame(
            main_frame, text="Output Directory", padding=5
        )
        output_frame.pack(fill=tk.X, pady=(0, 5))

        self._output_var = tk.StringVar(value="")
        ttk.Entry(
            output_frame, textvariable=self._output_var, state="readonly"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(
            output_frame, text="Browse...", command=self._on_browse_output
        ).pack(side=tk.RIGHT)

        # ── Start Button ─────────────────────────────────────────────
        self._start_button = ttk.Button(
            main_frame, text="Start Processing", command=self._on_start
        )
        self._start_button.pack(fill=tk.X, pady=(0, 5))

        # ── Progress Log ──────────────────────────────────────────────
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self._log_text = tk.Text(log_frame, height=10, state=tk.DISABLED, wrap=tk.WORD)
        log_scrollbar = ttk.Scrollbar(
            log_frame, orient=tk.VERTICAL, command=self._log_text.yview
        )
        self._log_text.configure(yscrollcommand=log_scrollbar.set)
        self._log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _setup_drag_and_drop(self) -> None:
        """Set up drag-and-drop support using tkinterdnd2 if available."""
        if not self._dnd_available:
            self._log(
                "Drag-and-drop unavailable (install tkinterdnd2 to enable). "
                "Use 'Add Files...' or 'Add Folder...' instead."
            )
            return
        try:
            from tkinterdnd2 import DND_FILES

            self._root.drop_target_register(DND_FILES)
            self._root.dnd_bind("<<Drop>>", self._on_drop)
            self._log("Drag-and-drop enabled.")
        except Exception:
            self._log(
                "Drag-and-drop unavailable (install tkinterdnd2 to enable). "
                "Use 'Add Files...' or 'Add Folder...' instead."
            )

    # ── Event Handlers ────────────────────────────────────────────────

    def _set_app_icon(self) -> None:
        """Load and set the application window icon from assets/icons/apps."""
        sizes = [512, 256, 128, 64, 32]
        icons: List[tk.PhotoImage] = []
        for size in sizes:
            path = _ICON_DIR / f"htr_racecharts_converter_{size}.png"
            if path.is_file():
                try:
                    icons.append(tk.PhotoImage(file=str(path)))
                except Exception:
                    pass
        if icons:
            self._root.iconphoto(True, *icons)
        self._app_icons = icons  # Prevent garbage collection

    def _on_rebuild_config(self) -> None:
        """Rebuild config.ini from hardcoded defaults after confirmation."""
        if not messagebox.askyesno(
            "Rebuild config.ini",
            "This will reset all Excel style settings to their defaults.\n"
            "The last output path will be preserved.\n\n"
            "Continue?",
        ):
            return
        try:
            rebuild_config(self._config_path)
            self._log("config.ini rebuilt with default settings.")
            self._update_output_indicator()
        except Exception as e:
            self._log(f"ERROR rebuilding config.ini: {e}")

    def _on_field_visibility(self) -> None:
        """Open the Field Visibility dialog."""
        try:
            from src.schema_loader import load_fields_schema
            fields_schema = load_fields_schema(self._scheme_dir)
        except Exception as e:
            messagebox.showerror("Load Error", f"Cannot load fields.json: {e}")
            return

        visible_raw, _ = read_output_settings(self._config_path)
        _FieldVisibilityDialog(
            self._root, fields_schema, self._config_path, visible_raw,
            log_callback=self._log,
            on_save_callback=self._update_output_indicator,
        )

    def _on_field_ordering(self) -> None:
        """Open the Field Ordering dialog."""
        try:
            from src.schema_loader import load_fields_schema
            fields_schema = load_fields_schema(self._scheme_dir)
        except Exception as e:
            messagebox.showerror("Load Error", f"Cannot load fields.json: {e}")
            return

        _, order_raw = read_output_settings(self._config_path)
        _FieldOrderingDialog(
            self._root, fields_schema, self._config_path, order_raw,
            log_callback=self._log,
            on_save_callback=self._update_output_indicator,
        )

    def _update_output_indicator(self) -> None:
        """Refresh the output-customization indicator and reset button."""
        customized = output_is_customized(self._config_path)
        if customized:
            self._output_indicator_var.set("Output: Customized")
            self._output_indicator_label.configure(foreground="blue")
            self._reset_output_btn.configure(state=tk.NORMAL)
        else:
            self._output_indicator_var.set("Output: Default")
            self._output_indicator_label.configure(foreground="")
            self._reset_output_btn.configure(state=tk.DISABLED)

    def _on_reset_output(self) -> None:
        """Reset output settings to defaults and update the indicator."""
        reset_output_settings(self._config_path)
        self._update_output_indicator()
        self._log("Output settings reset to defaults.")

    def _on_about(self) -> None:
        """Show the About dialog."""
        about_win = tk.Toplevel(self._root)
        about_win.title("About HTR Race Charts Converter")
        about_win.resizable(False, False)
        about_win.transient(self._root)
        about_win.grab_set()

        frame = ttk.Frame(about_win, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        logo_path = _ICON_DIR / "htr_racecharts_converter_128.png"
        if logo_path.is_file():
            try:
                logo_img = tk.PhotoImage(file=str(logo_path))
                logo_label = ttk.Label(frame, image=logo_img)
                logo_label.image = logo_img  # Prevent garbage collection
                logo_label.pack(pady=(0, 5))
            except Exception:
                pass

        ttk.Label(
            frame,
            text="HTR Race Charts Converter",
            font=("TkDefaultFont", 14, "bold"),
        ).pack(pady=(0, 5))

        ttk.Label(frame, text=f"Version: {__version__}").pack()

        ttk.Label(
            frame,
            text=(
                "Development Team:\n"
                "Ken Torbeck & Dr. Russ Winterbotham"
            ),
            justify=tk.CENTER,
        ).pack(pady=(10, 0))

        ttk.Label(frame, text="License: GPL-3.0").pack(pady=(10, 0))

        ttk.Label(
            frame,
            text=(
                "Disclaimer: This project is not affiliated with\n"
                "HTR (Handicapping Technology & Research) or its\n"
                "developers. It is an independent, community-\n"
                "developed tool for processing HTR race chart exports."
            ),
            justify=tk.CENTER,
        ).pack(pady=(10, 0))

        ttk.Label(
            frame,
            text="\u00a9 2026 Ken Torbeck and Dr. Russ Winterbotham",
        ).pack(pady=(10, 0))

        github_url = "https://github.com/ktorbeck/htr-race-charts-converter"
        link = ttk.Label(
            frame, text=github_url, foreground="blue", cursor="hand2"
        )
        link.pack(pady=(5, 10))
        link.bind(
            "<Button-1>", lambda e: webbrowser.open_new_tab(github_url)
        )

        ttk.Button(about_win, text="OK", command=about_win.destroy).pack(
            pady=(0, 10)
        )

    def _on_add_files(self) -> None:
        """Open a file dialog to select .TXT files."""
        paths = filedialog.askopenfilenames(
            title="Select HTR Files",
            filetypes=[("HTR Text Files", "*.TXT *.txt"), ("All Files", "*.*")],
        )
        if paths:
            self._add_files(list(paths))

    def _on_add_folder(self) -> None:
        """Open a directory dialog and add all .TXT files in it."""
        folder = filedialog.askdirectory(title="Select Folder Containing HTR Files")
        if folder:
            try:
                files = collect_txt_files([folder])
                if not files:
                    self._log(f"No .TXT files found in {folder}")
                else:
                    self._add_files(files)
            except Exception as e:
                self._log(f"ERROR: {e}")

    def _on_remove_selected(self) -> None:
        """Remove selected files from the list."""
        selected = list(self._file_listbox.curselection())
        if not selected:
            return
        # Remove in reverse order to maintain indices
        for idx in reversed(selected):
            self._file_listbox.delete(idx)
            del self._file_paths[idx]
        self._update_merge_state()

    def _on_clear_all(self) -> None:
        """Clear all files from the list."""
        self._file_listbox.delete(0, tk.END)
        self._file_paths.clear()
        self._update_merge_state()
        self._log("All files cleared.")

    def _on_browse_output(self) -> None:
        """Open a directory dialog to select the output location."""
        folder = filedialog.askdirectory(title="Select Output Directory")
        if folder:
            try:
                self._output_var.set(resolve_existing_directory(folder))
            except (FileNotFoundError, ValueError):
                messagebox.showerror(
                    "Invalid Directory",
                    f"Output directory does not exist or is not accessible:\n{folder}",
                )

    def _on_drop(self, event: tk.Event) -> None:
        """Handle drag-and-drop of files or folders.

        Args:
            event: The drop event containing file paths.
        """
        raw = event.data  # type: ignore[attr-defined]
        # tkinterdnd2 returns paths separated by spaces; braces around paths with spaces
        paths = self._parse_drop_data(raw)
        try:
            files = collect_txt_files(paths)
            if files:
                self._add_files(files)
            else:
                self._log("No .TXT files found in dropped items.")
        except Exception as e:
            self._log(f"ERROR: {e}")

    def _on_start(self) -> None:
        """Start processing in a background thread."""
        if self._processing:
            return

        # Validate inputs
        if not self._file_paths:
            messagebox.showwarning("No Files", "Please add HTR files to process.")
            return

        output_raw = self._output_var.get()
        if not output_raw:
            messagebox.showwarning(
                "No Output Directory", "Please select an output directory."
            )
            return
        try:
            output_dir = resolve_existing_directory(output_raw)
        except (FileNotFoundError, ValueError):
            messagebox.showerror(
                "Invalid Directory",
                f"Output directory does not exist or is not accessible:\n{output_raw}",
            )
            return

        self._output_var.set(output_dir)

        # Validate file types before processing
        for fp in self._file_paths:
            try:
                validate_file_extension(fp)
            except ValueError as e:
                messagebox.showerror("Invalid File", str(e))
                return

        self._processing = True
        self._start_button.configure(state=tk.DISABLED)
        self._clear_log()

        # Run processing in background thread
        thread = threading.Thread(
            target=self._run_processing,
            args=(
                list(self._file_paths),
                self._scheme_dir,
                output_dir,
                self._merge_var.get(),
                self._config_path,
            ),
            daemon=True,
        )
        thread.start()

    # ── Processing ────────────────────────────────────────────────────

    def _run_processing(
        self,
        file_paths: List[str],
        scheme_dir: str,
        output_dir: str,
        merge: bool,
        config_path: str,
    ) -> None:
        """Run the processing pipeline in a background thread.

        Args:
            file_paths: HTR file paths.
            scheme_dir: Scheme directory.
            output_dir: Output directory.
            merge: Whether to merge files.
            config_path: Path to config.ini for Excel settings and
                path persistence.
        """
        try:
            process_files(
                file_paths=file_paths,
                scheme_dir=scheme_dir,
                output_dir=output_dir,
                merge=merge,
                progress=self._thread_safe_log,
                config_path=config_path,
            )
            self._root.after(0, lambda: messagebox.showinfo(
                "Complete", "Processing completed successfully."
            ))
        except Exception as e:
            error_msg = f"ERROR: {e}"
            self._thread_safe_log(error_msg)
            self._root.after(0, lambda: messagebox.showerror(
                "Processing Error", str(e)
            ))
        finally:
            self._root.after(0, self._on_processing_done)

    def _on_processing_done(self) -> None:
        """Re-enable the start button after processing finishes."""
        self._processing = False
        self._start_button.configure(state=tk.NORMAL)

    # ── Helpers ───────────────────────────────────────────────────────

    def _add_files(self, paths: List[str]) -> None:
        """Add file paths to the list, skipping duplicates.

        When the output directory is empty, it is automatically set to
        the directory of the first input file that is added.

        Args:
            paths: File paths to add.
        """
        existing = set(self._file_paths)
        for p in paths:
            if p not in existing:
                self._file_paths.append(p)
                self._file_listbox.insert(tk.END, p)
                existing.add(p)
                self._log(f"Added: {os.path.basename(p)}")
        self._update_merge_state()

        # Auto-set output directory to the first input file's folder
        # when no output directory has been chosen yet.
        if not self._output_var.get() and self._file_paths:
            input_dir = os.path.dirname(self._file_paths[0])
            if input_dir and os.path.isdir(input_dir):
                self._output_var.set(input_dir)

    def _update_merge_state(self) -> None:
        """Enable the merge checkbox only when multiple files are loaded."""
        if len(self._file_paths) > 1:
            self._merge_check.state(["!disabled"])
        else:
            self._merge_var.set(False)
            self._merge_check.state(["disabled"])

    def _log(self, message: str) -> None:
        """Append a message to the log text widget.

        Args:
            message: Message to log.
        """
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.insert(tk.END, message + "\n")
        self._log_text.see(tk.END)
        self._log_text.configure(state=tk.DISABLED)

    def _thread_safe_log(self, message: str) -> None:
        """Log a message from a background thread using root.after.

        Args:
            message: Message to log.
        """
        self._root.after(0, lambda m=message: self._log(m))

    def _clear_log(self) -> None:
        """Clear the log text widget."""
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.delete("1.0", tk.END)
        self._log_text.configure(state=tk.DISABLED)

    @staticmethod
    def _parse_drop_data(raw: str) -> List[str]:
        """Parse drag-and-drop data string into a list of paths.

        tkinterdnd2 encodes paths with spaces in curly braces,
        e.g. '{C:/path with spaces/file.txt} C:/simple.txt'

        Args:
            raw: Raw drop data string.

        Returns:
            List of file/directory paths.
        """
        paths: List[str] = []
        i = 0
        while i < len(raw):
            if raw[i] == "{":
                # Find closing brace
                end = raw.index("}", i + 1)
                paths.append(raw[i + 1 : end])
                i = end + 1
            elif raw[i] == " ":
                i += 1
            else:
                # Find next space or end
                end = raw.find(" ", i)
                if end == -1:
                    end = len(raw)
                paths.append(raw[i:end])
                i = end
        return paths


# ── Field Visibility Dialog ───────────────────────────────────────────


class _FieldVisibilityDialog:
    """Checkbox dialog for selecting which fields are visible in Excel output.

    Saves the selection to ``[output] visible_fields`` in config.ini.
    """

    def __init__(
        self,
        parent: tk.Tk,
        fields_schema: List,
        config_path: str,
        visible_fields_raw: str,
        log_callback: Optional[Callable] = None,
        on_save_callback: Optional[Callable] = None,
    ) -> None:
        self._config_path = config_path
        self._fields_schema = fields_schema
        self._log_callback = log_callback
        self._on_save_callback = on_save_callback

        self._win = tk.Toplevel(parent)
        self._win.title("Field Visibility")
        self._win.geometry("500x600")
        self._win.transient(parent)
        self._win.grab_set()

        # Parse current visible fields setting
        if visible_fields_raw.lower() == "all":
            self._visible_set: Optional[set] = None  # all visible
        else:
            from src.output_settings import _parse_int_list
            self._visible_set = set(_parse_int_list(visible_fields_raw))

        self._build_ui()

    def _build_ui(self) -> None:
        top_frame = ttk.Frame(self._win, padding=5)
        top_frame.pack(fill=tk.X)

        ttk.Label(
            top_frame,
            text="Select fields to include in the Excel export:",
        ).pack(side=tk.LEFT)

        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="All", command=self._select_all).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btn_frame, text="None", command=self._select_none).pack(
            side=tk.LEFT, padx=2
        )

        # Scrollable checkbox list
        list_frame = ttk.Frame(self._win)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5)

        canvas = tk.Canvas(list_frame)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=canvas.yview)
        self._inner_frame = ttk.Frame(canvas)

        self._inner_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self._inner_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._vars: List[tk.BooleanVar] = []
        for field_def in self._fields_schema:
            field_num = field_def["field"]
            field_name = field_def.get("name") or f"Field_{field_num}"
            var = tk.BooleanVar(
                value=(self._visible_set is None or field_num in self._visible_set)
            )
            self._vars.append(var)
            ttk.Checkbutton(
                self._inner_frame,
                text=f"{field_num}. {field_name}",
                variable=var,
            ).pack(anchor=tk.W)

        # Save / Cancel buttons
        bottom_frame = ttk.Frame(self._win, padding=5)
        bottom_frame.pack(fill=tk.X)
        ttk.Button(bottom_frame, text="Save", command=self._on_save).pack(
            side=tk.RIGHT, padx=5
        )
        ttk.Button(bottom_frame, text="Cancel", command=self._win.destroy).pack(
            side=tk.RIGHT
        )

    def _select_all(self) -> None:
        for var in self._vars:
            var.set(True)

    def _select_none(self) -> None:
        for var in self._vars:
            var.set(False)

    def _on_save(self) -> None:
        selected = []
        all_selected = True
        for i, var in enumerate(self._vars):
            if var.get():
                selected.append(str(self._fields_schema[i]["field"]))
            else:
                all_selected = False

        if all_selected:
            visible_value = "all"
        else:
            visible_value = ",".join(selected)

        _, current_order = read_output_settings(self._config_path)
        write_output_settings(self._config_path, visible_value, current_order)

        if self._log_callback:
            if all_selected:
                self._log_callback("Field visibility: all fields visible.")
            else:
                self._log_callback(
                    f"Field visibility: {len(selected)} of "
                    f"{len(self._fields_schema)} fields selected."
                )
        if self._on_save_callback:
            self._on_save_callback()
        self._win.destroy()


# ── Field Ordering Dialog ─────────────────────────────────────────────


class _FieldOrderingDialog:
    """Drag-and-drop style dialog for reordering fields in the Excel output.

    Uses Up/Down buttons to move fields.  Saves the order to
    ``[output] custom_order`` in config.ini.
    """

    def __init__(
        self,
        parent: tk.Tk,
        fields_schema: List,
        config_path: str,
        custom_order_raw: str,
        log_callback: Optional[Callable] = None,
        on_save_callback: Optional[Callable] = None,
    ) -> None:
        self._config_path = config_path
        self._fields_schema = fields_schema
        self._log_callback = log_callback
        self._on_save_callback = on_save_callback

        self._win = tk.Toplevel(parent)
        self._win.title("Field Ordering")
        self._win.geometry("500x600")
        self._win.transient(parent)
        self._win.grab_set()

        # Build initial order
        all_field_nums = [f["field"] for f in fields_schema]
        if custom_order_raw.lower() != "default":
            from src.output_settings import _parse_int_list
            parsed = _parse_int_list(custom_order_raw)
            valid = set(all_field_nums)
            order = [f for f in parsed if f in valid]
            listed = set(order)
            for f in all_field_nums:
                if f not in listed:
                    order.append(f)
            self._order = order
        else:
            self._order = list(all_field_nums)

        # Map field number → name for display
        self._name_map = {}
        for f in fields_schema:
            name = f.get("name") or f"Field_{f['field']}"
            self._name_map[f["field"]] = name

        self._build_ui()

    def _build_ui(self) -> None:
        top_frame = ttk.Frame(self._win, padding=5)
        top_frame.pack(fill=tk.X)
        ttk.Label(
            top_frame,
            text="Reorder fields using the buttons. Top = first column.",
        ).pack(side=tk.LEFT)

        # Listbox with scrollbar
        list_frame = ttk.Frame(self._win)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5)

        self._listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE)
        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self._listbox.yview
        )
        self._listbox.configure(yscrollcommand=scrollbar.set)
        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._refresh_listbox()

        # Move buttons
        btn_frame = ttk.Frame(self._win, padding=5)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="▲ Move Up", command=self._move_up).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_frame, text="▼ Move Down", command=self._move_down).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_frame, text="Reset", command=self._reset_order).pack(
            side=tk.LEFT, padx=5
        )

        # Save / Cancel
        bottom_frame = ttk.Frame(self._win, padding=5)
        bottom_frame.pack(fill=tk.X)
        ttk.Button(bottom_frame, text="Save", command=self._on_save).pack(
            side=tk.RIGHT, padx=5
        )
        ttk.Button(bottom_frame, text="Cancel", command=self._win.destroy).pack(
            side=tk.RIGHT
        )

    def _refresh_listbox(self) -> None:
        self._listbox.delete(0, tk.END)
        for field_num in self._order:
            name = self._name_map.get(field_num, f"Field_{field_num}")
            self._listbox.insert(tk.END, f"{field_num}. {name}")

    def _move_up(self) -> None:
        sel = self._listbox.curselection()
        if not sel or sel[0] == 0:
            return
        idx = sel[0]
        self._order[idx - 1], self._order[idx] = (
            self._order[idx], self._order[idx - 1]
        )
        self._refresh_listbox()
        self._listbox.selection_set(idx - 1)
        self._listbox.see(idx - 1)

    def _move_down(self) -> None:
        sel = self._listbox.curselection()
        if not sel or sel[0] >= len(self._order) - 1:
            return
        idx = sel[0]
        self._order[idx + 1], self._order[idx] = (
            self._order[idx], self._order[idx + 1]
        )
        self._refresh_listbox()
        self._listbox.selection_set(idx + 1)
        self._listbox.see(idx + 1)

    def _reset_order(self) -> None:
        self._order = [f["field"] for f in self._fields_schema]
        self._refresh_listbox()

    def _on_save(self) -> None:
        default_order = [f["field"] for f in self._fields_schema]
        if self._order == default_order:
            order_value = "default"
        else:
            order_value = ",".join(str(f) for f in self._order)

        current_visible, _ = read_output_settings(self._config_path)
        write_output_settings(self._config_path, current_visible, order_value)

        if self._log_callback:
            if order_value == "default":
                self._log_callback("Field ordering: using default order.")
            else:
                self._log_callback("Field ordering: custom order saved.")
        if self._on_save_callback:
            self._on_save_callback()
        self._win.destroy()
