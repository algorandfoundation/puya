#!/usr/bin/env python3
import argparse
import os
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
GIT_ROOT = SCRIPT_DIR.parent
ENV_WITH_NO_COLOR = dict(os.environ) | {
    "NO_COLOR": "1",  # disable colour output
}


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
        "--no-summary",
    ]
    subprocess.run(
        (*cmd, *test_cases),
        cwd=GIT_ROOT,
        check=False,
        env=ENV_WITH_NO_COLOR,
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
