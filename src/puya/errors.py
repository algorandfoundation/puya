import contextlib
import enum
import sys
import traceback
from collections.abc import Iterator, Sequence
from pathlib import Path

import attrs

from puya import log
from puya.parse import SourceLocation

logger = log.get_logger(__name__)
_VALID_SEVERITY = ("error", "note", "warning")


class ErrorExitCode(enum.IntEnum):
    code = 1
    internal = 2


class PuyaError(Exception):
    def __init__(self, msg: str, location: SourceLocation | None = None):
        super().__init__(msg)
        self.msg = msg
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


def _get_pretty_source(file_source: Sequence[str], location: SourceLocation) -> list[str]:
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


def _crash_report() -> None:
    # Adapted from report_internal_error in mypy
    tb = traceback.extract_stack()[:-4]
    # Excise all the traceback from the test runner
    for i, x in enumerate(tb):
        if x.name == "pytest_runtest_call":
            tb = tb[i + 1 :]
            break
    *_, tb_type = sys.exc_info()
    tb2 = traceback.extract_tb(tb_type)[1:]
    output = ["Traceback (most recent call last):"]
    output.extend(s.rstrip("\n") for s in traceback.format_list(tb + tb2))
    logger.critical("\n".join(output))

@contextlib.contextmanager
def log_exceptions(fallback_location: SourceLocation | None = None) -> Iterator[None]:
    try:
        yield
    except CodeError as ex:
        logger.error(ex.msg, location=ex.location or fallback_location)  # noqa: TRY400
    except InternalError as ex:
        logger.critical(ex.msg, location=ex.location or fallback_location)
        sys.exit(ErrorExitCode.internal)
    except Exception as ex:
        _crash_report()
        logger.critical(f"{type(ex).__name__}: {ex}", location=fallback_location)
        sys.exit(ErrorExitCode.internal)
