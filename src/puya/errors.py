import contextlib
import logging
import sys
import traceback
import typing
import typing as t
from collections.abc import Iterator

import structlog

from puya.parse import SourceLocation

logger = structlog.get_logger()


class PuyaError(Exception):
    def __init__(self, msg: str, location: SourceLocation | None = None):
        self._msg = msg
        super().__init__(msg)
        self.location = location


class ParseError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


class InternalError(PuyaError):
    """Base class for all exceptions that indicate a fault in the compiler."""


class CodeError(PuyaError):
    """Base class for all exceptions that indicate a fault in the code being compiled."""


class TodoError(CodeError):
    """Not a code error but it's not a crash either"""

    def __init__(self, location: SourceLocation | None, msg: str | None = None):
        super().__init__(msg or "TODO: support this thing", location=location)


class Errors:
    def __init__(self) -> None:
        self.num_errors = 0
        self.num_warnings = 0

    def _report(self, log_level: int, msg: str, location: SourceLocation | None) -> None:
        kwargs: dict[str, typing.Any] = {}
        if location:
            kwargs["location"] = location
        logger.log(log_level, msg, **kwargs)

    def error(self, msg: str, location: SourceLocation | None) -> None:
        self._report(logging.ERROR, msg, location)
        self.num_errors += 1

    def warning(self, msg: str, location: SourceLocation | None) -> None:
        self._report(logging.WARNING, msg, location)
        self.num_warnings += 1

    def note(self, msg: str, location: SourceLocation | None) -> None:
        self._report(logging.INFO, msg, location)


def crash_report(location: SourceLocation | None) -> t.Never:
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
    if location:
        print(f"{location.file}:{location.line}: {type(err).__name__}: {err}")
    raise SystemExit(2)


@contextlib.contextmanager
def log_exceptions(
    errors: Errors, fallback_location: SourceLocation | None = None
) -> Iterator[None]:
    try:
        yield
    except CodeError as ex:
        errors.error(str(ex), location=ex.location or fallback_location)
    except InternalError as ex:
        errors.error(f"FATAL {ex!s}", location=ex.location or fallback_location)
        crash_report(ex.location or fallback_location)
    except Exception as ex:
        errors.error(f"UNEXPECTED {ex!s}", location=fallback_location)
        crash_report(fallback_location)
