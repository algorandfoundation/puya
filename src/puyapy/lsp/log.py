import typing
from collections.abc import Sequence

import attrs
import structlog

from puya import log
from puya.parse import SourceLocation
from puya.utils import get_cwd
from puyapy import code_fixes
from puyapy.lsp.analyse import get_code_fix_context


def configure_logging(
    *,
    min_log_level: log.LogLevel,
    file: typing.TextIO,
) -> None:
    log.configure_stdio()

    processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        _capture_fixes,  # capture fixes before filtering output to lsp log messages
        _filter_loggers_to_lsp,  # dont output log output outside puyapy.lsp namespace
        log.PuyaConsoleRender(colors=False, base_path=str(get_cwd())),
    ]
    processors.insert(0, log.FilterByLogLevel(min_log_level))
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=_NamedPrintLoggerFactory(file=file),
        cache_logger_on_first_use=True,
    )


@attrs.frozen
class _NamedPrintLoggerFactory:
    file: typing.TextIO

    def __call__(self, name: str, *_args: typing.Any) -> structlog.PrintLogger:
        return _NamedPrintLogger(name, self.file)


class _NamedPrintLogger(structlog.PrintLogger):
    def __init__(self, name: str, file: typing.TextIO):
        self.name = name
        super().__init__(file)


def _capture_fixes(
    _logger: structlog.typing.WrappedLogger,
    _name: str,
    event_dict: structlog.typing.EventDict,
) -> structlog.typing.EventDict:
    """Stores any fixes logged on the fix context"""
    code_edits = event_dict.get("edits", None)
    if code_edits:
        ctx = get_code_fix_context()
        if ctx is not None:
            location = event_dict.get("location")
            if location and isinstance(location, SourceLocation):
                if isinstance(code_edits, code_fixes.CodeEdit):
                    ctx.append(code_fixes.CodeFix(code_edits, location))
                elif isinstance(code_edits, Sequence):
                    ctx.extend(code_fixes.CodeFix(f, location) for f in code_edits)

    return event_dict


def _filter_loggers_to_lsp(
    logger: _NamedPrintLogger,
    _name: str,
    event_dict: structlog.typing.EventDict,
) -> structlog.typing.EventDict:
    if not logger.name.startswith("puyapy.lsp"):
        raise structlog.DropEvent
    return event_dict
