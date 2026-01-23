#!/usr/bin/env python3
"""Check if stubs version was bumped when .pyi files are changed."""

import re
import subprocess
import sys
import tomllib

import cyclopts

from scripts.script_utils import VCS_ROOT

app = cyclopts.App(help_on_error=True)

_STUBS_ROOT = VCS_ROOT / "stubs"
_STUBS_PYPROJECT = _STUBS_ROOT / "pyproject.toml"
_ALGOPY_STUBS_PATH = _STUBS_ROOT / "algopy-stubs"
_RELEASED_VERSION_TAG_PATTERN = re.compile(
    r"^v\d+\.\d+\.\d+$"
)  # matches exactly on release versions, with no suffix e.g. v5.7.0


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


def get_stubs_version(ref: str) -> str:
    pyproject = check_cmd("git", "show", f"{ref}:stubs/pyproject.toml")
    return extract_pyproject_version(pyproject)


def get_stubs_changed(ref: str) -> list[str]:
    changed_files = [
        VCS_ROOT / p for p in check_cmd("git", "diff", "--name-only", f"{ref}...HEAD").splitlines()
    ]
    changed_stubs = [
        f for f in changed_files if f.suffix == ".pyi" and _ALGOPY_STUBS_PATH in f.parents
    ]
    return [str(p.relative_to(_ALGOPY_STUBS_PATH)) for p in changed_stubs]


@app.default
def check_stubs(branch: str = "HEAD") -> None:
    """
    Checks for any changes to algorand-python stubs, and if there is a corresponding
    version change
    """
    print(f"Checking stubs for changes and corresponding version bump in {branch}")
    print()

    branch_base = check_cmd("git", "merge-base", branch, "origin/main")
    all_tags = check_cmd("git", "tag", "--sort=-version:refname").splitlines()
    release_tags = [tag for tag in all_tags if _RELEASED_VERSION_TAG_PATTERN.match(tag)]
    last_release = release_tags[0]
    print(f"Last puyapy release: {last_release}")

    this_branch_version = get_stubs_version(branch)
    print(f"This branch stubs version: {this_branch_version}")

    last_released_version = get_stubs_version(last_release)
    print(f"Last released stubs version: {last_released_version}")

    main_stubs_version = get_stubs_version("origin/main")
    print(f"Main stubs version: {main_stubs_version}")
    print()

    if this_branch_version != last_released_version:
        print(f"💡 Stub version change: {last_released_version} -> {this_branch_version}")

    stubs_changed_this_branch = get_stubs_changed(branch_base)
    if stubs_changed_this_branch:
        stub_list = "\n * ".join(("", *stubs_changed_this_branch))
        print(f"💡 Stub files changed:{stub_list}\n")
        if this_branch_version == last_released_version:
            print(
                "❌ Stubs version must be bumped using `poe bump_stubs` when"
                " .pyi files in stubs directory are changed."
            )
            sys.exit(1)
        elif this_branch_version != main_stubs_version:
            print("✅ Stub version updated.")
        else:
            print("💡 Stub version not updated in this branch, but has been updated in main.")
    else:
        print("✅ Stub files unchanged")

    print("✅ Stub check passed!")


if __name__ == "__main__":
    app()
