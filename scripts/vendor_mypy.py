#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MYPY_REPO = "https://github.com/python/mypy.git"
VCS_ROOT = Path(__file__).parent.parent


def clone_branch(version: str) -> str:
    git_clone = f"git clone --depth=1 --branch={version} --single-branch {MYPY_REPO} ."
    print(f"Executing: {git_clone}")
    subprocess.run(git_clone.split(), check=True)

    git_hash = subprocess.run("git rev-parse HEAD".split(), capture_output=True, check=True).stdout
    assert git_hash is not None
    subprocess.run("rm -rf .git".split(), check=True)
    return git_hash.decode("utf8").strip()


def vendor_mypy(version: str) -> None:
    wyvern_src_dir = VCS_ROOT / "src" / "wyvern"
    vendor_dir = wyvern_src_dir / "_vendor"
    mypy_vendor = vendor_dir / "mypy"
    print(f"Vendoring mypy into: {mypy_vendor}")

    print("Removing existing mypy files...")
    shutil.rmtree(mypy_vendor, ignore_errors=True)

    print(f"Cloning mypy {version}...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.chdir(tmp_dir)
        git_hash = clone_branch(version)
        print(f"Checked out mypy {version} @ {git_hash}")

        print(f"Copying mypy into {mypy_vendor}...")
        shutil.copytree(Path(tmp_dir) / "mypy", mypy_vendor)
        (mypy_vendor / ".version").write_text(f"{version}: {git_hash}")
    print("Updating custom typeshed")
    update_wyvern_typeshed(mypy_vendor / "typeshed", wyvern_src_dir / "_typeshed")


def update_wyvern_typeshed(mypy_typeshed: Path, wyvern_typeshed: Path) -> None:
    shutil.rmtree(wyvern_typeshed, ignore_errors=True)

    stubs = Path("stubs")
    stdlib = Path("stdlib")
    relative_to_copy = [
        # hard coded in mpyy/modulefinder.py, minimum requirements for mypy
        stubs / "mypy-extensions",
        stdlib / "VERSIONS",
        # hard coded in mpyy/build.py, minimum requirements for mypy
        stdlib / "_typeshed",
        stdlib / "collections",
        stdlib / "_collections_abc.pyi",
        stdlib / "abc.pyi",
        stdlib / "builtins.pyi",
        stdlib / "sys.pyi",
        stdlib / "types.pyi",
        stdlib / "typing.pyi",
        stdlib / "typing_extensions.pyi",
        # needed for algopy
        stdlib / "enum.pyi",
    ]

    (wyvern_typeshed / stdlib).mkdir(exist_ok=True, parents=True)
    (wyvern_typeshed / stubs).mkdir(exist_ok=True, parents=True)
    for relative in relative_to_copy:
        copy_src = mypy_typeshed / relative
        copy_dst = wyvern_typeshed / relative
        if copy_src.is_dir():
            shutil.copytree(copy_src, copy_dst)
        else:
            shutil.copy(copy_src, copy_dst)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        vendor_mypy(version=sys.argv[1])
    else:
        print("Usage: python vendor_mypy.py <version>")
        print("e.g. python vendor_mypy.py v1.5.0")
