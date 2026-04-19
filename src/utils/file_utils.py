"""File I/O utilities for HTR chart processing."""

import os
from pathlib import Path
from typing import List


def validate_file_extension(file_path: str) -> None:
    """Validate that the file has a .TXT extension.

    Args:
        file_path: Path to the file to validate.

    Raises:
        ValueError: If the file does not have a .TXT extension.
    """
    if not file_path.upper().endswith(".TXT"):
        raise ValueError(f"Invalid file extension: {file_path}. Expected .TXT")


def validate_file_exists(file_path: str) -> None:
    """Validate that the file exists on disk.

    Args:
        file_path: Path to the file to validate.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")


def resolve_scheme_path(scheme_dir: str, filename: str) -> str:
    """Resolve and validate a scheme file path.

    Args:
        scheme_dir: Directory containing scheme files.
        filename: Name of the scheme file.

    Returns:
        Absolute path to the scheme file.

    Raises:
        FileNotFoundError: If the scheme file does not exist.
    """
    path = os.path.join(scheme_dir, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Required scheme file not found: {path}")
    return path


def check_file_writable(file_path: str) -> None:
    """Check that a file path is writable before attempting to write.

    If the file already exists, verifies it can be opened for writing.
    This catches the common case where an Excel or CSV file is open in
    another application (e.g. Excel) which holds a lock on it.

    If the file does not yet exist, this is a no-op (the directory was
    already validated elsewhere).

    Args:
        file_path: Path to the output file.

    Raises:
        PermissionError: If the file exists but cannot be opened for writing.
    """
    if not os.path.isfile(file_path):
        return
    try:
        with open(file_path, mode="a", encoding="utf-8"):
            pass
    except PermissionError:
        raise PermissionError(
            f"Cannot write to '{file_path}'. "
            f"The file may be open in another application. "
            f"Please close it and try again."
        )


def collect_txt_files(paths: List[str]) -> List[str]:
    """Collect .TXT files from a list of file and/or directory paths.

    Args:
        paths: List of file paths or directory paths to scan.

    Returns:
        List of resolved .TXT file paths.

    Raises:
        FileNotFoundError: If a path does not exist.
        ValueError: If a file does not have a .TXT extension.
    """
    result: List[str] = []
    for p in paths:
        if os.path.isdir(p):
            for entry in sorted(os.listdir(p)):
                full = os.path.join(p, entry)
                if os.path.isfile(full) and full.upper().endswith(".TXT"):
                    result.append(full)
        elif os.path.isfile(p):
            validate_file_extension(p)
            result.append(p)
        else:
            raise FileNotFoundError(f"Path not found: {p}")
    return result


def resolve_existing_directory(path_value: str) -> str:
    """Resolve a directory path and return normalized absolute path.

    Args:
        path_value: User-provided directory path.

    Returns:
        Resolved absolute directory path.

    Raises:
        ValueError: If path_value is empty.
        FileNotFoundError: If the resolved path is not an existing directory.
    """
    if not path_value:
        raise ValueError("Directory path cannot be empty.")
    # strict=False keeps normalization robust across environments even when
    # symlink components cannot be fully resolved; existence is validated below.
    resolved = Path(path_value).expanduser().resolve(strict=False)
    if not resolved.is_dir():
        raise FileNotFoundError(f"Directory not found: {resolved}")
    return str(resolved)
