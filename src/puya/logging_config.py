from __future__ import annotations

import logging
import os.path
import sys
import typing
from enum import IntEnum
from io import StringIO
from pathlib import Path

import attrs
import structlog

if typing.TYPE_CHECKING:
    from puya.parse import SourceLocation

UNEXPECTED_SEVERITY = set[str]()
logger = structlog.get_logger()


class LogLevel(IntEnum):
    notset = logging.NOTSET
    debug = logging.DEBUG
    info = logging.INFO
    warning = logging.WARNING
    warn = logging.WARN
    error = logging.ERROR
    fatal = logging.FATAL
    critical = logging.CRITICAL

    def __str__(self) -> str:
        return self.name

    @staticmethod
    def from_string(s: str) -> LogLevel:
        try:
            return LogLevel[s]
        except KeyError as err:
            raise ValueError from err


def mypy_severity_to_loglevel(severity: str) -> int:
    match severity:
        case "error":
            return logging.ERROR
        case "warning":
            return logging.WARNING
        case "note":
            return logging.INFO
        case _:
            if severity not in UNEXPECTED_SEVERITY:
                logger.warning(f"Unexpected severity '{severity}', treating as error")
                UNEXPECTED_SEVERITY.add(severity)
            return logging.ERROR


class PuyaConsoleRender(structlog.dev.ConsoleRenderer):
    def __init__(self, *, colors: bool):
        super().__init__(colors=colors)
        self.level_to_color = self.get_default_level_styles(colors)
        self.base_path = str(Path.cwd())  # TODO: don't assume this?
        if not self.base_path.endswith(
            os.path.sep
        ):  # TODO: can we always append the path seperator?
            self.base_path += os.path.sep

    def _location_as_link(self, location: SourceLocation | None) -> str:
        if not location or not location.file:
            return ""

        file = str(Path(location.file).resolve())
        if file.startswith(self.base_path):
            file = file[len(self.base_path) :]

        line = str(location.line) if location.line else "1"
        col = f":{location.column + 1}" if location.column else ""
        return f"{file}:{line}{col}"

    def __call__(
        self,
        _logger: structlog.typing.WrappedLogger,
        _name: str,
        event_dict: structlog.typing.EventDict,
    ) -> str:
        # force event to str for compatibility with standard library
        event = event_dict.pop("event", None)
        if not isinstance(event, str):
            event = str(event)
        lines = [event]
        related_errors = event_dict.pop("related_lines", None)
        if related_errors:
            assert isinstance(related_errors, list)
            lines.extend(related_errors)
        location: SourceLocation | None = event_dict.pop("location", None)
        location_as_link = self._location_as_link(location) if location else ""
        level = event_dict.pop("level", "")

        align_related_lines = " " * (len(location_as_link) + 1 + len(level) + 2)
        sio = StringIO()
        for idx, line in enumerate(lines):
            if idx:
                sio.write("\n")
                sio.write(align_related_lines)
            else:
                if location:
                    sio.write(self._styles.logger_name)
                    location_link = self._location_as_link(location)
                    sio.write(location_link)
                    sio.write(" ")
                    sio.write(self._styles.reset)

                if level:
                    sio.write(self.level_to_color.get(level, ""))
                    sio.write(level)
                    sio.write(": ")
                    sio.write(self._styles.reset)
            sio.write(line)

        stack = event_dict.pop("stack", None)
        exc = event_dict.pop("exception", None)
        exc_info = event_dict.pop("exc_info", None)

        event_dict_keys: typing.Iterable[str] = event_dict.keys()
        if self._sort_keys:
            event_dict_keys = sorted(event_dict_keys)

        sio.write(
            " ".join(
                self._styles.kv_key
                + key
                + self._styles.reset
                + "="
                + self._styles.kv_value
                + self._repr(event_dict[key])
                + self._styles.reset
                for key in event_dict_keys
            )
        )

        if stack is not None:
            sio.write("\n" + stack)
            if exc_info or exc is not None:
                sio.write("\n\n" + "=" * 79 + "\n")

        if exc_info:
            exc_info = figure_out_exc_info(exc_info)

            self._exception_formatter(sio, exc_info)
        elif exc is not None:
            sio.write("\n" + exc)

        return sio.getvalue()


# copied from structlog.dev._figure_out_exc_info
def figure_out_exc_info(
    v: BaseException | structlog.typing.ExcInfo | bool,
) -> structlog.typing.ExcInfo | bool:
    """
    Depending on the Python version will try to do the smartest thing possible
    to transform *v* into an ``exc_info`` tuple.
    """
    if isinstance(v, BaseException):
        return type(v), v, v.__traceback__

    if isinstance(v, tuple):
        return v

    if v:
        return sys.exc_info()  # type: ignore[return-value]

    return v


@attrs.define
class FilterByLogLevel:
    min_log_level: LogLevel

    def __call__(
        self,
        _logger: structlog.typing.WrappedLogger,
        method: str,
        event_dict: structlog.typing.EventDict,
    ) -> structlog.typing.EventDict:
        if LogLevel[method] < self.min_log_level:
            raise structlog.DropEvent
        return event_dict


def configure_logging(
    *, min_log_level: LogLevel = LogLevel.notset, cache_logger: bool = True
) -> None:
    if cache_logger and structlog.is_configured():
        raise ValueError(
            "Logging can not be configured more than once if using cache_logger = True"
        )
    processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        PuyaConsoleRender(colors="NO_COLOR" not in os.environ),
    ]
    if min_log_level != LogLevel.notset:
        # filtering via a processor instead of via the logger like
        # structlog.make_filtering_bound_logger(min_log_level.value)
        # so that structlog.testing.capture_logs() still works in test cases
        processors.insert(0, FilterByLogLevel(min_log_level))
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=cache_logger,
    )
