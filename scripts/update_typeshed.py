#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

from scripts.script_utils import VCS_ROOT

MYPY_REPO = "https://github.com/python/mypy.git"
TYPESHED_README = """
This is PuyaPy's custom typeshed, which is a curated subset of the official MyPy typeshed.
It only includes the required stubs used by PuyaPy as this speeds up MyPy's parsing speed
significantly.

However this means certain python modules such as `enum` or `dataclasses` cannot be used in
PuyaPy stubs unless this typeshed is updated.

The contents of the typeshed are populated by the `scripts/update_typeshed.py` script, so to
support additional stubs, update that script and rerun.
""".strip()


def clone_branch(version: str) -> str:
    git_clone = f"git clone --depth=1 --branch={version} --single-branch {MYPY_REPO} ."
    print(f"Executing: {git_clone}")
    subprocess.run(git_clone.split(), check=True)

    git_hash = subprocess.run("git rev-parse HEAD".split(), capture_output=True, check=True).stdout
    assert git_hash is not None
    subprocess.run("rm -rf .git".split(), check=True)
    return git_hash.decode("utf8").strip()


def run(mypy_version: str) -> None:
    puya_src_dir = VCS_ROOT / "src" / "puyapy"

    print(f"Cloning mypy {mypy_version}...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.chdir(tmp_dir)
        git_hash = clone_branch(mypy_version)
        print(f"Checked out mypy {mypy_version} @ {git_hash}")

        print("Updating custom typeshed")
        mypy_typeshed = Path(tmp_dir) / "mypy" / "typeshed"
        puya_typeshed = puya_src_dir / "_typeshed"
        update_puya_typeshed(mypy_typeshed, puya_typeshed)
        print("Update complete")


def update_puya_typeshed(mypy_typeshed: Path, puya_typeshed: Path) -> None:
    shutil.rmtree(puya_typeshed, ignore_errors=True)

    stubs = Path("stubs")
    stdlib = Path("stdlib")
    relative_to_copy = [
        # hard coded in mpyy/modulefinder.py, minimum requirements for mypy
        stubs / "mypy-extensions" / "mypy_extensions.pyi",
        stdlib / "VERSIONS",
        # hard coded in mpyy/build.py, minimum requirements for mypy
        stdlib / "builtins.pyi",
        stdlib / "typing.pyi",
        stdlib / "types.pyi",
        stdlib / "typing_extensions.pyi",
        stdlib / "_typeshed" / "__init__.pyi",
        stdlib / "_collections_abc.pyi",
        stdlib / "collections" / "abc.pyi",
        stdlib / "sys" / "__init__.pyi",
        stdlib / "abc.pyi",
        # needed for puyapy
        # stdlib / "enum.pyi"
    ]

    (puya_typeshed / stdlib).mkdir(exist_ok=True, parents=True)
    (puya_typeshed / stubs).mkdir(exist_ok=True, parents=True)
    for relative in relative_to_copy:
        copy_src = mypy_typeshed / relative
        copy_dst = puya_typeshed / relative
        if copy_src.is_dir():
            shutil.copytree(copy_src, copy_dst)
        else:
            copy_dst.parent.mkdir(exist_ok=True, parents=True)
            shutil.copy(copy_src, copy_dst)
    (puya_typeshed / stdlib / "collections" / "__init__.pyi").touch()
    (puya_typeshed / "README.md").write_text(TYPESHED_README, encoding="utf8")


def main() -> None:
    if len(sys.argv) > 1:
        run(mypy_version=sys.argv[1])
    else:
        with (VCS_ROOT / "pyproject.toml").open(mode="rb") as fp:
            pp = tomllib.load(fp)
        for dep_spec in pp["project"]["dependencies"]:
            if dep_spec.startswith("mypy=="):
                version = dep_spec.removeprefix("mypy==")
                run("v" + version)
                break
        else:
            print("unable to determine mypy version from pyproject.toml")


if __name__ == "__main__":
    main()
