import typing
from collections.abc import Sequence

import attrs
import structlog

from puya import log
from puya.parse import SourceLocation
from puya.utils import get_cwd
from puyapy import code_fixes
from puyapy.lsp.analyse import get_code_fix_context
from puyapy.lsp.server import LogToClient


def configure_logging(
    *,
    min_log_level: log.LogLevel,
    file: typing.TextIO,
) -> "LogToClient":
    """
    Configures logging for the language server, which happens before the language server is
    available, so also returns an interface that can be used to provide language server instance
    and configured log level for client
    """
    log.configure_stdio()

    log_to_client = LogToClient()
    processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        _capture_fixes,  # capture fixes before filtering output to lsp log messages
        _filter_loggers_to_lsp,  # dont output log output outside puyapy.lsp namespace
        log_to_client,
        log.FilterByLogLevel(min_log_level),  # min_log_level from CLI is just for stdio output
        log.PuyaConsoleRender(colors=False, base_path=str(get_cwd())),
    ]
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=_NamedPrintLoggerFactory(file=file),
        cache_logger_on_first_use=True,
    )
    return log_to_client


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
