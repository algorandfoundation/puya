from __future__ import annotations

import contextlib
import logging
import os.path
import sys
import typing
from collections import Counter
from contextvars import ContextVar
from enum import IntEnum
from io import StringIO
from pathlib import Path

import attrs
import structlog

if typing.TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

    from puya.parse import SourceLocation


class LogLevel(IntEnum):
    notset = logging.NOTSET
    debug = logging.DEBUG
    info = logging.INFO
    warning = logging.WARNING
    error = logging.ERROR
    critical = logging.CRITICAL

    def __str__(self) -> str:
        return self.name

    @staticmethod
    def from_string(s: str) -> LogLevel:
        try:
            return LogLevel[s]
        except KeyError as err:
            raise ValueError from err


@attrs.frozen
class Log:
    level: LogLevel
    message: str
    location: SourceLocation | None

    @property
    def file(self) -> str | None:
        return None if self.location is None else self.location.file

    @property
    def line(self) -> int | None:
        return None if self.location is None else self.location.line


@attrs.define
class LoggingContext:
    logs: list[Log] = attrs.field(factory=list)

    def _log_level_counts(self) -> Mapping[LogLevel, int]:
        return Counter(log.level for log in self.logs)

    @property
    def num_errors(self) -> int:
        level_counts = self._log_level_counts()
        return sum(count for level, count in level_counts.items() if level >= LogLevel.error)

    def exit_if_errors(self) -> None:
        level_counts = self._log_level_counts()
        if level_counts[LogLevel.critical]:
            sys.exit(2)
        elif level_counts[LogLevel.error]:
            sys.exit(1)


_current_ctx: ContextVar[LoggingContext] = ContextVar("current_ctx")


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
        important: bool = event_dict.pop("important", False)
        location: SourceLocation | None = event_dict.pop("location", None)
        location_as_link = self._location_as_link(location) if location else ""
        level = event_dict.pop("level", "info")

        align_related_lines = " " * (len(location_as_link) + 1 + len(level) + 1)
        sio = StringIO()
        reset_colour = self._styles.reset
        if important:
            sio.write(self._styles.bright)
            reset_colour += self._styles.bright
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
                    sio.write(reset_colour)

                sio.write(self.level_to_color.get(level, ""))
                sio.write(level)
                sio.write(": ")
                sio.write(reset_colour)
            sio.write(line)
        sio.write(self._styles.reset)

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


class _Logger:
    def __init__(self, name: str, initial_values: dict[str, typing.Any]):
        self._logger = structlog.get_logger(name, **initial_values)

    def debug(
        self,
        event: object,
        *args: typing.Any,
        location: SourceLocation | None = None,
        **kwargs: typing.Any,
    ) -> None:
        self._report(LogLevel.debug, event, *args, location=location, **kwargs)

    def info(
        self,
        event: object,
        *args: typing.Any,
        location: SourceLocation | None = None,
        **kwargs: typing.Any,
    ) -> None:
        self._report(LogLevel.info, event, *args, location=location, **kwargs)

    def warning(
        self,
        event: object,
        *args: typing.Any,
        location: SourceLocation | None = None,
        **kwargs: typing.Any,
    ) -> None:
        self._report(LogLevel.warning, event, *args, location=location, **kwargs)

    def error(
        self,
        event: object,
        *args: typing.Any,
        location: SourceLocation | None = None,
        **kwargs: typing.Any,
    ) -> None:
        _add_source_context(kwargs, location)
        self._report(LogLevel.error, event, *args, location=location, **kwargs)

    def exception(
        self,
        event: object,
        *args: typing.Any,
        location: SourceLocation | None = None,
        **kwargs: typing.Any,
    ) -> None:
        _add_source_context(kwargs, location)
        kwargs.setdefault("exc_info", True)
        self._report(LogLevel.critical, event, *args, location=location, **kwargs)

    def critical(
        self,
        event: object,
        *args: typing.Any,
        location: SourceLocation | None = None,
        **kwargs: typing.Any,
    ) -> None:
        _add_source_context(kwargs, location)
        self._report(LogLevel.critical, event, *args, location=location, **kwargs)

    def log(
        self,
        level: LogLevel,
        event: object,
        *args: typing.Any,
        location: SourceLocation | None = None,
        **kwargs: typing.Any,
    ) -> None:
        self._report(level, event, *args, location=location, **kwargs)

    def _report(
        self,
        level: LogLevel,
        event: object,
        *args: typing.Any,
        location: SourceLocation | None = None,
        **kwargs: typing.Any,
    ) -> None:
        self._logger.log(level, event, *args, location=location, **kwargs)
        try:
            ctx = _current_ctx.get()
        except LookupError:
            return
        if isinstance(event, str) and args:
            message = event % args
        else:
            message = str(event)
        ctx.logs.append(Log(level, message, location))


def _add_source_context(kwargs: dict[str, typing.Any], location: SourceLocation | None) -> None:
    if not location:
        return

    from puya.parse import read_source

    file_source = read_source(location.file)
    if file_source and location.line <= len(file_source):
        kwargs["related_lines"] = _get_pretty_source(file_source, location)


def _get_pretty_source(file_source: Sequence[str], location: SourceLocation) -> Sequence[str]:
    start_line_idx = location.line - 1
    end_line_idx = (location.end_line or location.line) - 1
    # find first line that isn't a comment
    for source_line_idx in range(start_line_idx, end_line_idx + 1):
        if not file_source[source_line_idx].lstrip().startswith("#"):
            break
    else:
        source_line_idx = start_line_idx
    # source line is followed by additional lines, don't bother annotating columns
    if source_line_idx != end_line_idx:
        return file_source[start_line_idx : end_line_idx + 1]
    source_line = file_source[source_line_idx]
    column = location.column
    end_column = len(source_line)
    if (location.end_line is None or location.end_line == location.line) and location.end_column:
        end_column = location.end_column
    # Shifts column after tab expansion
    column = len(source_line[:column].expandtabs())
    end_column = len(source_line[:end_column].expandtabs())

    lines_before_source = file_source[start_line_idx:source_line_idx]

    return [
        *lines_before_source,
        source_line.expandtabs(),
        " " * column + f"^{'~' * max(end_column - column - 1, 0)}",
    ]


def get_num_errors() -> int:
    return _current_ctx.get().num_errors


def get_logger(name: str, **initial_values: typing.Any) -> _Logger:
    return _Logger(name, initial_values)


@contextlib.contextmanager
def logging_context() -> Iterator[LoggingContext]:
    ctx = LoggingContext()
    restore = _current_ctx.set(ctx)
    try:
        yield ctx
    finally:
        _current_ctx.reset(restore)
