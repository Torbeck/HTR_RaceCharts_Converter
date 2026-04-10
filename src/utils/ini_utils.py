"""INI configuration utilities for HTR chart processing.

Reads and writes config.ini for:
- [race_data] section: table_style, borders, auto_size_columns, freeze_header
- [points_call] section: table_style, borders, auto_size_columns, freeze_header
- [fractional_times] section: table_style, borders, auto_size_columns, freeze_header
- [paths] section: last_output

Fallback logic:
- If config.ini does not exist, return hardcoded defaults for all keys.
- If a key is missing or has an invalid value, use the hardcoded default.
- Only the keys defined in the INI spec are recognized; no new keys are added.

Table style validation:
- Validates against the set of known Excel table style names.
- If a table_style value is invalid, it is rewritten as
  'INVALID - <original_value>' in the INI and the hardcoded default is used.

Rebuild:
- rebuild_config() recreates config.ini from hardcoded defaults, preserving
  [paths].last_output if possible.
"""

import configparser
import os
import re
from dataclasses import dataclass
from typing import Optional


# ── Valid Excel table style names ─────────────────────────────────────
# Excel supports these built-in table style families.  Each family has a
# fixed number of numbered variants.
_VALID_TABLE_STYLES: set = set()

for _prefix, _count in [
    ("TableStyleLight", 21),
    ("TableStyleMedium", 28),
    ("TableStyleDark", 11),
]:
    for _i in range(1, _count + 1):
        _VALID_TABLE_STYLES.add(f"{_prefix}{_i}")


def is_valid_table_style(style: str) -> bool:
    """Return True if *style* is a recognised Excel table style name."""
    return style in _VALID_TABLE_STYLES


# ── Per-table hardcoded defaults ──────────────────────────────────────

_DEFAULTS = {
    "race_data": {
        "table_style": "TableStyleMedium9",
        "borders": True,
        "auto_size_columns": True,
        "freeze_header": True,
    },
    "points_call": {
        "table_style": "TableStyleMedium11",
        "borders": False,
        "auto_size_columns": True,
        "freeze_header": True,
    },
    "fractional_times": {
        "table_style": "TableStyleMedium12",
        "borders": False,
        "auto_size_columns": True,
        "freeze_header": True,
    },
}

DEFAULT_LAST_OUTPUT = "default"


@dataclass(frozen=True)
class ExcelSettings:
    """Immutable container for Excel formatting settings for one table.

    Attributes:
        table_style: Excel table style name (e.g. 'TableStyleMedium9').
        borders: Whether to apply thin borders to all cells in the table range.
        auto_size_columns: Whether to compute and apply column widths.
        freeze_header: Whether to freeze the first row (pane at A2).
    """
    table_style: str
    borders: bool
    auto_size_columns: bool
    freeze_header: bool


def load_config(config_path: str) -> configparser.ConfigParser:
    """Load config.ini from disk.

    If the file does not exist, returns an empty ConfigParser so that
    all subsequent reads fall through to defaults.

    Args:
        config_path: Absolute path to config.ini.

    Returns:
        Populated ConfigParser (or empty if file missing).
    """
    parser = configparser.ConfigParser()
    if os.path.isfile(config_path):
        parser.read(config_path, encoding="utf-8")
    return parser


def _read_table_settings(
    parser: configparser.ConfigParser,
    section: str,
    config_path: Optional[str] = None,
) -> ExcelSettings:
    """Read per-table formatting settings from an INI section.

    Validates table_style against known Excel table styles.  When the
    value is invalid the INI is updated in-place to flag it as
    ``INVALID - <original>``, and the hardcoded default is used instead.

    Args:
        parser: ConfigParser instance.
        section: INI section name (e.g. 'race_data').
        config_path: If provided and a style is invalid, the INI is
            rewritten with the invalid marker.

    Returns:
        ExcelSettings with resolved values.
    """
    defaults = _DEFAULTS[section]

    # table_style: non-empty string, validated
    raw_style = parser.get(section, "table_style", fallback="").strip()

    if raw_style.startswith("INVALID"):
        # Already flagged — use default
        table_style = defaults["table_style"]
    elif raw_style and not is_valid_table_style(raw_style):
        # Unknown style — flag it and fall back
        _mark_style_invalid(parser, section, raw_style, config_path)
        table_style = defaults["table_style"]
    elif raw_style:
        table_style = raw_style
    else:
        table_style = defaults["table_style"]

    borders = _read_bool(parser, section, "borders", defaults["borders"])
    auto_size_columns = _read_bool(
        parser, section, "auto_size_columns", defaults["auto_size_columns"]
    )
    freeze_header = _read_bool(
        parser, section, "freeze_header", defaults["freeze_header"]
    )

    return ExcelSettings(
        table_style=table_style,
        borders=borders,
        auto_size_columns=auto_size_columns,
        freeze_header=freeze_header,
    )


def _mark_style_invalid(
    parser: configparser.ConfigParser,
    section: str,
    bad_value: str,
    config_path: Optional[str],
) -> None:
    """Rewrite the table_style value in the INI as ``INVALID - <value>``.

    Args:
        parser: ConfigParser instance (updated in-place).
        section: The INI section containing the bad value.
        bad_value: The original invalid style string.
        config_path: If provided, the INI is saved to disk.
    """
    marker = f"INVALID - {bad_value}"
    if parser.has_section(section):
        parser.set(section, "table_style", marker)

    if config_path and os.path.isfile(config_path):
        with open(config_path, mode="w", encoding="utf-8") as f:
            parser.write(f)


def read_excel_settings(config_path: str) -> dict:
    """Read per-table Excel formatting settings from config.ini.

    Returns a dict keyed by table name ('race_data', 'points_call',
    'fractional_times') with ExcelSettings values.

    Args:
        config_path: Absolute path to config.ini.

    Returns:
        Dict[str, ExcelSettings] with settings for each table.
    """
    parser = load_config(config_path)
    result = {}
    for section in _DEFAULTS:
        result[section] = _read_table_settings(parser, section, config_path)
    return result


def read_last_output(config_path: str) -> Optional[str]:
    """Read [paths].last_output from config.ini.

    Fallback logic:
    - If the key is missing or the value is the literal string
      'default' (case-insensitive), return ``None`` so the caller
      can fall back to the input file's directory.
    - If the stored path does not exist on disk, return ``None``.
    - Otherwise return the stored path.

    Args:
        config_path: Absolute path to config.ini.

    Returns:
        The stored output directory path, or ``None`` when the
        default (input-file directory) behaviour should be used.
    """
    parser = load_config(config_path)
    raw = parser.get("paths", "last_output", fallback="").strip()

    if not raw or raw.lower() == "default":
        return None

    if os.path.isdir(raw):
        return raw

    return None


def write_last_output(config_path: str, output_dir: str) -> None:
    """Write [paths].last_output back to config.ini after a successful export.

    Preserves all existing sections and keys.  Only updates the single value.

    Args:
        config_path: Absolute path to config.ini.
        output_dir: The output directory the user selected.
    """
    parser = load_config(config_path)

    if not parser.has_section("paths"):
        parser.add_section("paths")

    parser.set("paths", "last_output", output_dir)

    with open(config_path, mode="w", encoding="utf-8") as f:
        parser.write(f)


def rebuild_config(config_path: str) -> None:
    """Rebuild config.ini from hardcoded defaults.

    If the file already exists, [paths].last_output is preserved.
    All table style sections are reset to their defaults.

    Args:
        config_path: Absolute path to config.ini.
    """
    # Preserve last_output if possible
    last_output = DEFAULT_LAST_OUTPUT
    if os.path.isfile(config_path):
        try:
            old = configparser.ConfigParser()
            old.read(config_path, encoding="utf-8")
            saved = old.get("paths", "last_output", fallback="").strip()
            if saved:
                last_output = saved
        except Exception:
            pass

    parser = configparser.ConfigParser()

    for section, defaults in _DEFAULTS.items():
        parser.add_section(section)
        parser.set(section, "table_style", defaults["table_style"])
        parser.set(section, "borders", "yes" if defaults["borders"] else "no")
        parser.set(
            section, "auto_size_columns",
            "yes" if defaults["auto_size_columns"] else "no",
        )
        parser.set(
            section, "freeze_header",
            "yes" if defaults["freeze_header"] else "no",
        )

    parser.add_section("paths")
    parser.set("paths", "last_output", last_output)

    with open(config_path, mode="w", encoding="utf-8") as f:
        parser.write(f)


def _read_bool(
    parser: configparser.ConfigParser,
    section: str,
    key: str,
    default: bool,
) -> bool:
    """Safely read a boolean from the INI, falling back to default on error.

    Args:
        parser: ConfigParser instance.
        section: INI section name.
        key: INI key name.
        default: Value to return if key is missing or unparseable.

    Returns:
        Parsed boolean or the default.
    """
    try:
        return parser.getboolean(section, key, fallback=default)
    except ValueError:
        return default
