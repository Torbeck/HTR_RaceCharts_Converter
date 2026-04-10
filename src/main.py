# ──────────────────────────────────────────────────────────────────────
# HTR Race Charts Converter
# Version: 1.2.0
# Development Team:  Ken Torbeck (ktorbeck@gmail.com) & Dr. Russ Winterbotham
# Not affiliated with HTR or its developers. This is an independent project
# GPL-3.0 license
# ──────────────────────────────────────────────────────────────────────


"""Entry point for the HTR Chart Processing Application.

Launches the GUI. The scheme directory and config.ini path are resolved
relative to this file's parent directory (project root).
"""

import os
import sys


def main() -> None:
    """Resolve the scheme directory and config path, then launch the GUI."""
    # Project root is one level above src/
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scheme_dir = os.path.join(project_root, "scheme")
    config_path = os.path.join(project_root, "config.ini")

    if not os.path.isdir(scheme_dir):
        print(f"FATAL: Scheme directory not found: {scheme_dir}", file=sys.stderr)
        sys.exit(1)

    # Add project root to sys.path so imports resolve correctly
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Create config.ini with defaults if it does not exist yet.
    if not os.path.isfile(config_path):
        from src.utils.ini_utils import rebuild_config
        rebuild_config(config_path)

    from src.gui import HTRApp

    app = HTRApp(scheme_dir=scheme_dir, config_path=config_path)
    app.run()


if __name__ == "__main__":
    main()
