import contextlib
import enum
import sys
import traceback
from collections.abc import Iterator

from puya import log
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


@contextlib.contextmanager
def log_exceptions(fallback_location: SourceLocation | None = None) -> Iterator[None]:
    try:
        yield
    except CodeError as ex:
        logger.error(ex.msg, location=ex.location or fallback_location)  # noqa: TRY400
    except InternalError as ex:
        _log_traceback()
        logger.critical(ex.msg, location=ex.location or fallback_location)
        sys.exit(ErrorExitCode.internal)
    except Exception as ex:
        _log_traceback()
        logger.critical(f"{type(ex).__name__}: {ex}", location=fallback_location)
        sys.exit(ErrorExitCode.internal)


def _log_traceback() -> None:
    traceback_lines = traceback.format_exc()
    logger.debug(traceback_lines.rstrip("\n"))
