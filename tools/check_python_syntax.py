#!/usr/bin/env python3
"""Compile Python sources, including executable scripts without a .py suffix."""

from __future__ import annotations

import os
import sys
import tokenize
from pathlib import Path

IGNORED_DIRECTORIES = {
    ".git",
    ".pio",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}


def is_python_source(path: Path) -> bool:
    if path.suffix == ".py":
        return True
    try:
        with path.open("rb") as source:
            first_line = source.readline()
    except OSError:
        return False
    return first_line.startswith(b"#!") and b"python" in first_line.lower()


def python_sources(roots: list[Path]) -> list[Path]:
    sources: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for current_dir, directory_names, file_names in os.walk(root):
            directory_names[:] = [
                name for name in directory_names if name not in IGNORED_DIRECTORIES
            ]
            current_path = Path(current_dir)
            for file_name in file_names:
                path = current_path / file_name
                if path.is_file() and is_python_source(path):
                    sources.append(path)
    return sorted(sources)


def check_source(path: Path) -> None:
    with tokenize.open(path) as source:
        compile(source.read(), str(path), "exec")


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    roots = [repository_root / name for name in ("targets", "tests", "tools")]
    sources = python_sources(roots)

    errors: list[str] = []
    for path in sources:
        try:
            check_source(path)
        except (OSError, SyntaxError, UnicodeError) as error:
            errors.append(f"{path.relative_to(repository_root)}: {error}")

    if errors:
        print("Python syntax check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"Python syntax check passed: {len(sources)} sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
