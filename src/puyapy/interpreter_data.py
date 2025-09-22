# ruff: noqa: PTH100,PTH118,T201
"""
Module to get sys.path from an interpreter in a sanitized way (mostly for the sake of mypy).
When invoked as a script will also check the Python version is compatible.
"""

import os
import sys


def get_sys_path() -> list[str]:
    # drop the first path entry unless PYTHONSAFEPATH is active
    offset = 0 if sys.flags.safe_path else 1
    return [os.path.abspath(p) for p in sys.path[offset:]]


if __name__ == "__main__":
    version_tuple = sys.version_info[:3]
    if not ((3, 12, 0) <= version_tuple < (4, 0, 0)):
        print(f"unsupported Python version: {'.'.join(map(str, version_tuple))}", file=sys.stderr)
        sys.exit(1)
    else:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        print("\n".join(get_sys_path()))
