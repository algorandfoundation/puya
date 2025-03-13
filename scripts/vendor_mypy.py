#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MYPY_REPO = "https://github.com/python/mypy.git"
VCS_ROOT = Path(__file__).parent.parent
TYPESHED_README = """
This is PuyaPy's custom typeshed, which is a curated subset of the official MyPy typeshed.
It only includes the required stubs used by PuyaPy as this speeds up MyPy's parsing speed
significantly.

However this means certain python modules such as `enum` or `dataclasses` cannot be used in
PuyaPy stubs unless this typeshed is updated.

The contents of the typeshed are populated by the `scripts/vendor_mypy.py` script, which is used
to vendor new versions of MyPy or to update the stubs included in this typeshed. So to add new
stubs, update that script and rerun.
""".strip()


def clone_branch(version: str) -> str:
    git_clone = f"git clone --depth=1 --branch={version} --single-branch {MYPY_REPO} ."
    print(f"Executing: {git_clone}")
    subprocess.run(git_clone.split(), check=True)

    git_hash = subprocess.run("git rev-parse HEAD".split(), capture_output=True, check=True).stdout
    assert git_hash is not None
    subprocess.run("rm -rf .git".split(), check=True)
    return git_hash.decode("utf8").strip()


def vendor_mypy(version: str) -> None:
    puya_src_dir = VCS_ROOT / "src" / "puyapy"
    vendor_dir = puya_src_dir / "_vendor"
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
        (mypy_vendor / ".version").write_text(f"{version}: {git_hash}", encoding="utf8")
    print("Updating custom typeshed")
    update_puya_typeshed(mypy_vendor / "typeshed", puya_src_dir / "_typeshed")


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


if __name__ == "__main__":
    if len(sys.argv) > 1:
        vendor_mypy(version=sys.argv[1])
    else:
        print("Usage: python vendor_mypy.py <version>")
        print("e.g. python vendor_mypy.py v1.5.0")
