import contextlib
import functools
import io
import json
import logging
import os.path
import platform
import sys
import typing
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from contextvars import ContextVar
from enum import IntEnum, StrEnum, auto
from io import StringIO
from pathlib import Path

import attrs
import structlog

from puya.parse import SourceLocation


class LogFormat(StrEnum):
    default = auto()
    json = auto()


class LogLevel(IntEnum):
    notset = logging.NOTSET
    debug = logging.DEBUG
    info = logging.INFO
    warning = logging.WARNING
    error = logging.ERROR
    critical = logging.CRITICAL

    def __str__(self) -> str:
        return self.name


@attrs.frozen
class Log:
    level: LogLevel
    message: str
    location: SourceLocation | None

    @property
    def file(self) -> Path | None:
        return None if self.location is None else self.location.file

    @property
    def line(self) -> int | None:
        return None if self.location is None else self.location.line


@attrs.define
class LoggingContext:
    logs: list[Log] = attrs.field(factory=list)
    sources_by_path: Mapping[Path, Sequence[str] | None] | None = None

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


class PuyaJsonRender(structlog.processors.JSONRenderer):
    def __init__(self, *, base_path: str) -> None:
        super().__init__()
        self.base_path = base_path + os.path.sep

    def _location_json(
        self, location: SourceLocation | None
    ) -> Mapping[str, str | int | None] | None:
        if not location or not location.file:
            return None

        file = str(location.file)
        if file.startswith(self.base_path):
            file = file[len(self.base_path) :]

        return {
            "file": file,
            "line": location.line,
            "end_line": location.end_line,
            "column": location.column,
            "end_column": location.end_column,
        }

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

        important: bool = event_dict.pop("important", False)
        location: SourceLocation | None = event_dict.pop("location", None)
        level = event_dict.pop("level", LogLevel.info.name)

        return json.dumps(
            {
                "level": level,
                "location": self._location_json(location),
                "message": event,
                "important": important,
            }
        )


class PuyaConsoleRender(structlog.dev.ConsoleRenderer):
    def __init__(self, *, colors: bool, base_path: str):
        super().__init__(colors=colors)
        self.level_to_color = self.get_default_level_styles(colors)
        self.base_path = base_path
        if not self.base_path.endswith(
            os.path.sep
        ):  # TODO: can we always append the path seperator?
            self.base_path += os.path.sep

    def _location_as_link(self, location: SourceLocation | None) -> str:
        if not location or not location.file:
            return ""

        file = str(location.file)
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
        if location and location.file is None:
            location = None
        location_as_link = self._location_as_link(location) if location else ""
        level = event_dict.pop("level", LogLevel.info.name)

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
    *,
    min_log_level: LogLevel = LogLevel.notset,
    cache_logger: bool = True,
    log_format: LogFormat = LogFormat.default,
    reconfigure_stdio: bool = True,
) -> None:
    if reconfigure_stdio:
        configure_stdio()
    if cache_logger and structlog.is_configured():
        raise ValueError(
            "Logging can not be configured more than once if using cache_logger = True"
        )
    base_path = str(Path.cwd())  # TODO: don't assume this?
    match log_format:
        case LogFormat.json:
            log_renderer: structlog.typing.Processor = PuyaJsonRender(base_path=base_path)
        case LogFormat.default:
            # we handle NO_COLOR to prevent logging with colours on any platform,
            # otherwise we replicate the default colors value from structlog/dev.py,
            # which is only available as a module-private variable...
            if "NO_COLOR" in os.environ:
                colors = False
            elif sys.platform != "win32":
                colors = True
            else:
                try:
                    import colorama  # noqa: F401
                except ImportError:
                    colors = False
                else:
                    colors = True

            log_renderer = PuyaConsoleRender(colors=colors, base_path=base_path)
        case never:
            typing.assert_never(never)

    processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        log_renderer,
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
        self._report(LogLevel.error, event, *args, location=location, **kwargs)

    def exception(
        self,
        event: object,
        *args: typing.Any,
        location: SourceLocation | None = None,
        **kwargs: typing.Any,
    ) -> None:
        kwargs.setdefault("exc_info", True)
        self._report(LogLevel.critical, event, *args, location=location, **kwargs)

    def critical(
        self,
        event: object,
        *args: typing.Any,
        location: SourceLocation | None = None,
        **kwargs: typing.Any,
    ) -> None:
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
        log_ctx = _current_ctx.get(None)
        if (
            level >= LogLevel.error
            and location
            and log_ctx
            and log_ctx.sources_by_path
            and location.file
        ):
            file_source = log_ctx.sources_by_path.get(location.file)
            if file_source is not None:
                kwargs["related_lines"] = _get_pretty_source(file_source, location)
        self._logger.log(level, event, *args, location=location, **kwargs)
        if log_ctx:
            if isinstance(event, str) and args:
                message = event % args
            else:
                message = str(event)
            log_ctx.logs.append(Log(level, message, location))


def _get_pretty_source(
    file_source: Sequence[str], location: SourceLocation
) -> Sequence[str] | None:
    lines = file_source[location.line - 1 : location.end_line]
    if len(lines) != location.line_count:
        logger = get_logger(__name__)
        logger.warning(f"source length mismatch for {location}")
        return None
    try:
        (source_line,) = lines
    except ValueError:
        # source line is followed by additional lines, don't bother annotating columns
        return lines
    # Shifts column after tab expansion
    column = len(source_line[: location.column].expandtabs())
    end_column = len(source_line[: location.end_column].expandtabs())

    return [
        source_line.expandtabs(),
        " " * column + f"^{'~' * max(end_column - column - 1, 0)}",
    ]


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


@functools.cache  # only run this once
def configure_stdio() -> None:
    encoding = None  # keep the default
    if platform.system() == "Windows":
        encoding = "utf-8"  # force UTF-8
    # just to be safe, output a ? or similar when an encoding error still occurs
    on_encoding_error = "backslashreplace"
    # enable line buffering, making a flush implicit when a newline character occurs
    line_buffering = True
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer,
        encoding=encoding,
        errors=on_encoding_error,
        line_buffering=line_buffering,
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer,
        encoding=encoding,
        errors=on_encoding_error,
        line_buffering=line_buffering,
    )
