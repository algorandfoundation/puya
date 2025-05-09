#!/usr/bin/env python3
"""Bump stubs version and update version bounds."""

import argparse
import re
import sys
from pathlib import Path

VCS_ROOT = Path(__file__).parent.parent
STUBS_PYPROJECT = VCS_ROOT / "stubs" / "pyproject.toml"
PARSE_PY = VCS_ROOT / "src" / "puyapy" / "parse.py"


def search_replace_first(path: Path, search_pattern: str, replacement: str) -> None:
    content = path.read_text()
    new_content = re.sub(
        search_pattern,
        replacement,
        content,
        flags=re.MULTILINE,
        count=1,  # first occurrence only
    )
    path.write_text(new_content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump stubs version")
    parser.add_argument(
        "version",
        type=str,
        help="New version number (e.g. 1.2.3)",
    )
    args = parser.parse_args()

    new_version = args.version.strip()
    # validate and extract version elements
    major, minor, _ = list(map(int, new_version.split(".")))
    next_minor_version = f"{major}.{minor + 1}.0"

    # tomllib can't write so do a naive search_replace
    search_replace_first(
        STUBS_PYPROJECT, search_pattern="^version =.*$", replacement=f'version = "{new_version}"'
    )
    search_replace_first(
        PARSE_PY,
        search_pattern="^MAX_SUPPORTED_ALGOPY_VERSION_EX =.*$",
        replacement=f'MAX_SUPPORTED_ALGOPY_VERSION_EX = version.parse("{next_minor_version}")',
    )
    print(f"Updated version to {new_version}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
