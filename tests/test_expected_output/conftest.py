from pathlib import Path

import pytest

from tests.test_expected_output.data import TestFile


# This function name is special to pytest.  See
# https://doc.pytest.org/en/latest/how-to/writing_plugins.html#collection-hooks
def pytest_collect_file(parent: pytest.Collector, file_path: Path) -> pytest.Collector | None:
    if file_path.suffix == ".test":
        return TestFile.from_parent(parent, path=file_path)
    return None


# This function name is special to pytest.  See
# https://doc.pytest.org/en/latest/how-to/writing_plugins.html#initialization-command-line-and-configuration-hooks
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--test-auto-update",
        action="store_true",
        default=False,
        help="Update .test files with expected error outputs, requires --dist no if using xdist",
    )

    parser.addoption(
        "--test-approval-suffix",
        action="store",
        default=None,
        help="File suffix to use when outputting expected outputs, "
        "defaults to None which overwrites the input file",
    )
