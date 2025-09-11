# ruff: noqa: PTH100,PTH118,T201
"""
Module to get sys.path from an interpreter in a sanitized way (mostly for the sake of mypy).
When invoked as a script will also check the Python version is compatible.
"""

import os
import sys
import sysconfig


def get_sys_path() -> list[str]:
    # exclude stuff that should come from typeshed for mypy's sake (for now at least)
    stdlib_zip = os.path.join(
        sys.base_exec_prefix,
        sys.platlibdir,
        f"python{sys.version_info.major}{sys.version_info.minor}.zip",
    )
    stdlib = sysconfig.get_path("stdlib")
    stdlib_ext = os.path.join(stdlib, "lib-dynload")
    excludes = {stdlib_zip, stdlib, stdlib_ext}

    # drop the first path entry unless PYTHONSAFEPATH is active
    offset = 0 if sys.flags.safe_path else 1
    abs_sys_path = (os.path.abspath(p) for p in sys.path[offset:])
    return [p for p in abs_sys_path if p not in excludes]


if __name__ == "__main__":
    version_tuple = sys.version_info[:3]
    if not ((3, 12, 0) <= version_tuple < (4, 0, 0)):
        print(f"unsupported Python version: {'.'.join(map(str, version_tuple))}", file=sys.stderr)
        sys.exit(1)
    else:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        print("\n".join(get_sys_path()))
