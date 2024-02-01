import contextlib
import enum
import logging
import sys
import traceback
import typing
import typing as t
from collections.abc import Callable, Iterator
from pathlib import Path

import attrs
import structlog

from puya.parse import SourceLocation

logger = structlog.get_logger()
_VALID_SEVERITY = ("error", "note", "warning")


class ErrorExitCode(enum.IntEnum):
    code = 1
    internal = 2
    unexpected = 3


class PuyaError(Exception):
    def __init__(self, msg: str, location: SourceLocation | None = None):
        super().__init__(msg)
        self._msg = msg
        self.location = location


@attrs.frozen(kw_only=True)
class MyPyErrorData:
    message: str
    severity: str | None = None
    location: SourceLocation | None = None

    @classmethod
    def parse(cls, error_str: str) -> "MyPyErrorData":
        error_parts = error_str.split(":", maxsplit=3)
        if len(error_parts) == 4:  # parse error that might contain file and line details
            file_str, line_str, severity, message = error_parts
            severity = severity.strip()
            if Path(file_str).exists() and severity in _VALID_SEVERITY:
                try:
                    line = int(line_str)
                except ValueError:
                    pass
                else:
                    location = SourceLocation(file=file_str, line=line)
                    return cls(message=message[1:], severity=severity, location=location)
            error_parts = error_str.split(":", maxsplit=1)
        if len(error_parts) == 2:  # otherwise attempt to parse severity and message
            severity, message = error_parts
            severity = severity.strip()
            if severity in _VALID_SEVERITY:
                return cls(message=message[1:], severity=severity)
        # fallback to just the error message
        return cls(message=error_str)


class ParseError(Exception):
    """Encapsulate parse/type errors from MyPy"""

    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = list(map(MyPyErrorData.parse, errors))


class InternalError(PuyaError):
    """Base class for all exceptions that indicate a fault in the compiler."""


class CodeError(PuyaError):
    """Base class for all exceptions that indicate a fault in the code being compiled."""


class TodoError(CodeError):
    """Not a code error but it's not a crash either"""

    def __init__(self, location: SourceLocation | None, msg: str | None = None):
        super().__init__(msg or "TODO: support this thing", location=location)


def _get_pretty_source(file_source: list[str], location: SourceLocation) -> list[str]:
    source_line = file_source[location.line - 1]
    column = location.column
    end_column = len(source_line)
    if (location.end_line is None or location.end_line == location.line) and location.end_column:
        end_column = location.end_column
    source_line_expanded = source_line.expandtabs()

    # Shifts column after tab expansion
    column = len(source_line[:column].expandtabs())
    end_column = len(source_line[:end_column].expandtabs())

    marker = "^"
    if end_column > column:
        marker += "~" * (end_column - column - 1)
    return [
        source_line_expanded,
        " " * column + marker,
    ]


class Errors:
    def __init__(self, read_source: Callable[[str], list[str] | None]) -> None:
        self.num_errors = 0
        self.num_warnings = 0
        self.read_source = read_source

    def _report(self, log_level: int, msg: str, location: SourceLocation | None) -> None:
        kwargs: dict[str, typing.Any] = {}
        if location:
            kwargs["location"] = location
            if log_level == logging.ERROR:
                file_source = self.read_source(location.file)
                if file_source and location.line <= len(file_source):
                    kwargs["related_lines"] = _get_pretty_source(file_source, location)
        logger.log(log_level, msg, **kwargs)

    def error(self, msg: str, location: SourceLocation | None) -> None:
        self._report(logging.ERROR, msg, location)
        self.num_errors += 1

    def warning(self, msg: str, location: SourceLocation | None) -> None:
        self._report(logging.WARNING, msg, location)
        self.num_warnings += 1

    def note(self, msg: str, location: SourceLocation | None) -> None:
        self._report(logging.INFO, msg, location)


def crash_report(location: SourceLocation | None, exit_code: ErrorExitCode) -> t.Never:
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
    raise SystemExit(exit_code.value)


@contextlib.contextmanager
def log_exceptions(
    errors: Errors,
    fallback_location: SourceLocation | None = None,
    *,
    exit_on_failure: bool = False,
) -> Iterator[None]:
    try:
        yield
    except CodeError as ex:
        errors.error(str(ex), location=ex.location or fallback_location)
        if exit_on_failure:
            raise SystemExit(ErrorExitCode.code) from ex
    except InternalError as ex:
        errors.error(f"FATAL {ex!s}", location=ex.location or fallback_location)
        crash_report(ex.location or fallback_location, ErrorExitCode.internal)
    except Exception as ex:
        errors.error(f"UNEXPECTED {ex!s}", location=fallback_location)
        crash_report(fallback_location, ErrorExitCode.unexpected)
