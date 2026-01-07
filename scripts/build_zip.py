#!/usr/bin/env python3
"""Create a ZIP archive of the repository for easy sharing."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
}

EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def should_include(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in EXCLUDE_DIRS for part in relative.parts):
        return False
    if path.suffix in EXCLUDE_SUFFIXES:
        return False
    return True


def build_zip(root: Path, output: Path) -> None:
    paths: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_include(path, root):
            paths.append(path)

    paths.sort()

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for path in paths:
            zipf.write(path, path.relative_to(root))



def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a ZIP archive of the repository contents.",
    )
    parser.add_argument(
        "--output",
        default="fukada.zip",
        help="Output ZIP path (default: fukada.zip)",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output = Path(args.output).expanduser()
    build_zip(root=root, output=output)
    print(f"ZIP archive created: {output}")


if __name__ == "__main__":
    main()
