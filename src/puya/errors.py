import contextlib
import enum
import traceback
import typing
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


class ConfigurationError(PuyaError):
    """Indicates a problem with the requested compilation configuration or the puyapy install."""


@contextlib.contextmanager
def log_exceptions(fallback_location: SourceLocation | None = None) -> Iterator[None]:
    try:
        yield
    except* PuyaExitError as ex_exit:
        # should only be one exit code generally...
        exit_code = max(typing.cast(PuyaExitError, e).exit_code for e in ex_exit.exceptions)
        raise PuyaExitError(exit_code) from None
    except* (CodeError, ConfigurationError) as code_errors:
        for code_error in code_errors.exceptions:
            assert isinstance(code_error, CodeError | ConfigurationError)
            logger.error(code_error.msg, location=code_error.location or fallback_location)  # noqa: TRY400
    except* Exception as ex_group:
        for ex in ex_group.exceptions:
            traceback_lines = "".join(traceback.format_exception(ex))
            logger.debug(traceback_lines.rstrip("\n"))
            if isinstance(ex, InternalError):
                logger.critical(ex.msg, location=ex.location or fallback_location)
            else:
                logger.critical(f"{type(ex).__name__}: {ex}", location=fallback_location)
        raise PuyaExitError(ErrorExitCode.internal) from ex_group
