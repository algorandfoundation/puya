#!/usr/bin/env python3

import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
VCS_ROOT = SCRIPTS_DIR.parent
LIB_NAME = "_puya_lib"


def main() -> None:
    # compile puya lib
    # normalize source_location.path
    # save
    subprocess.run(["puyapy", "--output-awst-json", f"src/{LIB_NAME}"], check=True, cwd=VCS_ROOT)
    awst_path = VCS_ROOT / "module.awst.json"
    puya_lib_path = VCS_ROOT / "src" / LIB_NAME
    output_path = VCS_ROOT / "src" / "puya" / "ir" / "_puya_lib.awst.json"
    find_str = f'"source_location": {{"file": "{puya_lib_path}'
    replace_str = f'"source_location": {{"file": "{LIB_NAME}'
    replace_awst = awst_path.read_text().replace(find_str, replace_str)
    output_path.write_text(replace_awst)
    awst_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()