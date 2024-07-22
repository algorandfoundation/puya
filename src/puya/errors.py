from __future__ import annotations

import contextlib
import enum
import sys
import traceback
import typing

import mypy.errors

from puya import log

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class ErrorExitCode(enum.IntEnum):
    code = 1
    internal = 2


class PuyaError(Exception):
    def __init__(self, msg: str, location: SourceLocation | None = None):
        super().__init__(msg)
        self.msg = msg
        self.location = location


class InternalError(PuyaError):
    """Base class for all exceptions that indicate a fault in the compiler."""


class CodeError(PuyaError):
    """Base class for all exceptions that indicate a fault in the code being compiled."""


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
    logger.debug("\n".join(output))


@contextlib.contextmanager
def log_exceptions(fallback_location: SourceLocation | None = None) -> Iterator[None]:
    try:
        yield
    except CodeError as ex:
        logger.error(ex.msg, location=ex.location or fallback_location)  # noqa: TRY400
    except mypy.errors.CompileError:
        # errors related to this should have already been logged
        sys.exit(ErrorExitCode.code)
    except InternalError as ex:
        logger.critical(ex.msg, location=ex.location or fallback_location)
        sys.exit(ErrorExitCode.internal)
    except Exception as ex:
        _crash_report()
        logger.critical(f"{type(ex).__name__}: {ex}", location=fallback_location)
        sys.exit(ErrorExitCode.internal)
