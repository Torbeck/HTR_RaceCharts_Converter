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
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

from src.processor import process_files
from src.utils.file_utils import collect_txt_files, validate_file_extension
from src.utils.ini_utils import read_last_output, rebuild_config


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

        self._build_ui()
        self._setup_drag_and_drop()

        # ── Preselect last output directory from config.ini ───────────
        # Fallback logic (in read_last_output):
        #   - If last_output is "default" or missing → use default_output_dir
        #   - If the stored path doesn't exist on disk → use default_output_dir
        # The default output dir is the user's home directory.
        default_output = os.path.expanduser("~")
        last_output = read_last_output(config_path, default_output)
        if last_output and os.path.isdir(last_output):
            self._output_var.set(last_output)

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
        except Exception as e:
            self._log(f"ERROR rebuilding config.ini: {e}")

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
            self._output_var.set(folder)

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

        output_dir = self._output_var.get()
        if not output_dir:
            messagebox.showwarning(
                "No Output Directory", "Please select an output directory."
            )
            return

        if not os.path.isdir(output_dir):
            messagebox.showerror(
                "Invalid Directory",
                f"Output directory does not exist: {output_dir}",
            )
            return

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
