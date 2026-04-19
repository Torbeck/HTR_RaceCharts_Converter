# ──────────────────────────────────────────────────────────────────────
# HTR Race Charts Converter
# Version: see src/version.py
# Development Team:  Ken Torbeck (ktorbeck@gmail.com) & Dr. Russ Winterbotham
# Not affiliated with HTR or its developers. This is an independent project
# GPL-3.0 license
# ──────────────────────────────────────────────────────────────────────


"""Entry point for the HTR Chart Processing Application.

Launches the GUI. The scheme directory and config.ini path are resolved
relative to this file's parent directory (project root).
"""

import sys
from pathlib import Path


def resolve_runtime_paths() -> tuple[Path, Path, Path]:
    """Resolve project-root, scheme-dir, and config.ini absolute paths."""
    project_root = Path(__file__).resolve().parent.parent
    scheme_dir = project_root / "scheme"
    config_path = project_root / "config.ini"
    return project_root, scheme_dir, config_path


def main() -> None:
    """Resolve the scheme directory and config path, then launch the GUI."""
    project_root, scheme_dir, config_path = resolve_runtime_paths()

    if not scheme_dir.is_dir():
        print(f"FATAL: Scheme directory not found: {scheme_dir}", file=sys.stderr)
        sys.exit(1)

    # Ensure deterministic runtime paths when launched from run.bat or IDEs.
    # This keeps any incidental relative-path behavior rooted at project root.
    from os import chdir
    chdir(str(project_root))

    # Add project root to sys.path so imports resolve correctly
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

    # Create config.ini with defaults if it does not exist yet.
    if not config_path.is_file():
        from src.utils.ini_utils import rebuild_config
        rebuild_config(str(config_path))

    from src.gui import HTRApp

    app = HTRApp(scheme_dir=str(scheme_dir), config_path=str(config_path))
    app.run()


if __name__ == "__main__":
    main()
