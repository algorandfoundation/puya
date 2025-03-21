import contextlib
import enum
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


class PuyaExitError(Exception):
    def __init__(self, exit_code: ErrorExitCode):
        self.exit_code = exit_code


class InternalError(PuyaError):
    """Base class for all exceptions that indicate a fault in the compiler."""


class CodeError(PuyaError):
    """Base class for all exceptions that indicate a fault in the code being compiled."""


@contextlib.contextmanager
def log_exceptions(fallback_location: SourceLocation | None = None) -> Iterator[None]:
    try:
        yield
    except PuyaExitError:
        raise
    except CodeError as ex:
        logger.error(ex.msg, location=ex.location or fallback_location)  # noqa: TRY400
    except InternalError as ex:
        _log_traceback()
        logger.critical(ex.msg, location=ex.location or fallback_location)
        raise PuyaExitError(ErrorExitCode.internal) from ex
    except Exception as ex:
        _log_traceback()
        logger.critical(f"{type(ex).__name__}: {ex}", location=fallback_location)
        raise PuyaExitError(ErrorExitCode.internal) from ex


def _log_traceback() -> None:
    traceback_lines = traceback.format_exc()
    logger.debug(traceback_lines.rstrip("\n"))
