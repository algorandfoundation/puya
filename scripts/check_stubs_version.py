#!/usr/bin/env python3
"""Check if stubs version was bumped when .pyi files are changed."""

import subprocess
import sys
import tomllib
from pathlib import Path

_VCS_ROOT = Path(__file__).parent.parent
_STUBS_ROOT = _VCS_ROOT / "stubs"
_STUBS_PYPROJECT = _STUBS_ROOT / "pyproject.toml"
_ALGOPY_STUBS_PATH = _STUBS_ROOT / "algopy-stubs"


def check_cmd(*cmd: str) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()


def extract_pyproject_version(file_contents: str) -> str:
    """Extract version from pyproject.toml content."""
    toml_data = tomllib.loads(file_contents)
    try:
        version = toml_data["project"]["version"]
    except KeyError:
        # TODO: remove this fallback once a release is done without poetry
        version = toml_data["tool"]["poetry"]["version"]
    assert isinstance(version, str), "expected str"
    return version


def main() -> int:
    last_release = check_cmd("git", "describe", "--tags", "--abbrev=0")
    print(f"Last release: {last_release}")

    current_version = extract_pyproject_version(_STUBS_PYPROJECT.read_text())
    print(f"Current version: {current_version}")

    released_stubs_pyproject = check_cmd("git", "show", f"{last_release}:stubs/pyproject.toml")
    previous_version = extract_pyproject_version(released_stubs_pyproject)
    print(f"Previous version: {previous_version}")

    changed_files = [
        _VCS_ROOT / p
        for p in check_cmd("git", "diff", "--name-only", f"{last_release}...HEAD").splitlines()
    ]
    changed_stubs = [
        f for f in changed_files if f.suffix == ".pyi" and _ALGOPY_STUBS_PATH in f.parents
    ]
    print(f"Stub files changed:\n\t{"\n\t".join(map(str, changed_stubs))}")

    if current_version == previous_version and changed_stubs:
        print(
            "Error: Stubs version must be bumped in stubs/pyproject.toml when"
            " .pyi files in stubs directory are changed"
        )
        return 1

    print("Stub check passed!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
