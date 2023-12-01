import logging
import sys
import traceback
import typing as t

import structlog

from wyvern.parse import SourceLocation

logger = structlog.get_logger()


class WyvernError(Exception):
    def __init__(self, msg: str, location: SourceLocation | None = None):
        self._msg = msg
        super().__init__(msg)
        self.location = location


class ParseError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


class InternalError(WyvernError):
    """Base class for all exceptions that indicate a fault in the compiler."""


class CodeError(WyvernError):
    """Base class for all exceptions that indicate a fault in the code being compiled."""


class TodoError(CodeError):
    """Not a code error but it's not a crash either"""

    def __init__(self, location: SourceLocation | None, msg: str | None = None):
        super().__init__(msg or "TODO: support this thing", location=location)


class Errors:
    def __init__(self) -> None:
        self.num_errors = 0
        self.num_warnings = 0

    def _report(self, log_level: int, msg: str, location: SourceLocation) -> None:
        logger.log(
            log_level,
            msg,
            location=location,
        )

    def error(self, msg: str, location: SourceLocation) -> None:
        self._report(logging.ERROR, msg, location)
        self.num_errors += 1

    def warning(self, msg: str, location: SourceLocation) -> None:
        self._report(logging.WARNING, msg, location)
        self.num_warnings += 1

    def note(self, msg: str, location: SourceLocation) -> None:
        self._report(logging.INFO, msg, location)


def crash_report(location: SourceLocation) -> t.Never:
    # Adapted from report_internal_error in mypy
    err = sys.exc_info()[1]
    tb = traceback.extract_stack()[:-4]
    # Excise all the traceback from the test runner
    for i, x in enumerate(tb):
        if x.name == "pytest_runtest_call":
            tb = tb[i + 1 :]
            break
    *_, tb_type = sys.exc_info()
    tb2 = traceback.extract_tb(tb_type)[1:]
    print("Traceback (most recent call last):")
    for s in traceback.format_list(tb + tb2):
        print(s.rstrip("\n"))
    print(f"{location.file}:{location.line}: {type(err).__name__}: {err}")
    raise SystemExit(2)
