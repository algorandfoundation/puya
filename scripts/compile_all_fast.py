#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
GIT_ROOT = SCRIPT_DIR.parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "limit_to",
        type=str,
        nargs=argparse.REMAINDER,
        metavar="LIMIT_TO",
        help="test cases to compile e.g. test_cases/arc4_types",
    )
    options = parser.parse_args()

    if options.limit_to:
        test_cases = [
            f"tests/test_compile.py::test_compile[{test_case}]" for test_case in options.limit_to
        ]
    else:
        test_cases = ["tests/test_compile.py", "tests/from_awst"]

    cmd = [
        "pytest",
        "--no-header",
        "--tb=no",
    ]
    subprocess.run(
        (*cmd, *test_cases),
        cwd=GIT_ROOT,
        check=False,  # don't need to raise an error if pytest fails
    )


if __name__ == "__main__":
    main()
