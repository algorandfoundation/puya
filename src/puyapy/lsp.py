import argparse
import logging
import sys
import typing
from importlib.metadata import version
from pathlib import Path

from lsprotocol import types
from lsprotocol.types import DiagnosticSeverity
from pygls.lsp.server import LanguageServer
from pygls.workspace import TextDocument

from puya.compile import awst_to_teal
from puya.errors import log_exceptions
from puya.log import LoggingContext, LogLevel, logging_context
from puya.parse import SourceLocation
from puyapy.awst_build.main import transform_ast
from puyapy.compile import get_mypy_options, parse_with_mypy
from puyapy.options import PuyaPyOptions
from puyapy.utils import determine_out_dir

_NAME = "puyapy-lsp"
_VERSION = version("puyapy")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog=_NAME,
        description="puyapy language server, defaults to listening on localhost:8888",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s ({_VERSION})")
    parser.add_argument("--stdio", action="store_true", help="start a stdio server")
    parser.add_argument("--host", default="localhost", help="bind to this address")
    parser.add_argument("--socket", type=int, default=8888, help="bind to this port")

    arguments = parser.parse_args(sys.argv[1:])
    if arguments.stdio:
        server.start_io()
    else:
        server.start_tcp(arguments.host, arguments.socket)


class PuyaPyLanguageServer(LanguageServer):

    def __init__(self, name: str, version: str) -> None:
        super().__init__(name, version=version)
        self.diagnostics = dict[str, tuple[int, list[types.Diagnostic]]]()
        self.analysis_prefix: Path | None = None

    def parse(self, document: TextDocument) -> None:
        diagnostics = list[types.Diagnostic]()

        src_path = Path(document.path)
        options = PuyaPyOptions(log_level=LogLevel.warning, paths=[src_path], sources={src_path: document.source}, prefix=self.analysis_prefix)
        with logging_context() as log_ctx:
            _parse_and_log(log_ctx, options)
        logs = log_ctx.logs

        diagnostics.extend(
            _diag(log.message, log.level, log.location)
            for log in logs
            if log.location and log.location.file == src_path
        )
        self.diagnostics[document.uri] = (document.version or 0, diagnostics)


server = PuyaPyLanguageServer(_NAME, version=_VERSION)


def _parse_and_log(log_ctx: LoggingContext, puyapy_options: PuyaPyOptions) -> None:
    with log_exceptions():
        parse_result = parse_with_mypy(puyapy_options.paths, puyapy_options.sources, prefix=puyapy_options.prefix)

        log_ctx.sources_by_path = parse_result.sources_by_path
        if log_ctx.num_errors:
            return
        awst, compilation_targets = transform_ast(parse_result)
        if log_ctx.num_errors:
            return
        awst_lookup = {n.id: n for n in awst}
        compilation_set = {
            target_id: determine_out_dir(loc.file.parent, puyapy_options)
            for target_id, loc in (
                (t, awst_lookup[t].source_location) for t in compilation_targets
            )
            if loc.file
        }
        awst_to_teal(log_ctx, puyapy_options, compilation_set, parse_result.sources_by_path, awst)


class _HasTextDocument(typing.Protocol):
    @property
    def text_document(self) -> types.VersionedTextDocumentIdentifier: ...


def _refresh_diagnostics(ls: PuyaPyLanguageServer, params: _HasTextDocument) -> None:
    """Parse each document when it is changed"""
    doc = ls.workspace.get_text_document(params.text_document.uri)
    ls.parse(doc)

    for uri, (doc_version, diagnostics) in ls.diagnostics.items():
        ls.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(
                uri=uri,
                version=doc_version,
                diagnostics=diagnostics,
            )
        )
@server.feature(types.INITIALIZE)
def _initialization(ls: PuyaPyLanguageServer, params: types.InitializeParams) -> None:
    options = params.initialization_options
    analysis_prefix = options.get("analysisPrefix")
    if not analysis_prefix:
        analysis_prefix = sys.prefix
        ls.window_log_message(
            types.LogMessageParams(
                type=types.MessageType.Warning,
                message=f"No analysis prefix provided, using {analysis_prefix}",
            )
        )
    ls.analysis_prefix = Path(analysis_prefix)


server.feature(types.TEXT_DOCUMENT_DID_SAVE)(_refresh_diagnostics)
server.feature(types.TEXT_DOCUMENT_DID_OPEN)(_refresh_diagnostics)
server.feature(types.TEXT_DOCUMENT_DID_CHANGE)(_refresh_diagnostics)

def _diag(
    message: str, level: LogLevel = LogLevel.info, loc: SourceLocation | None = None
) -> types.Diagnostic:
    if loc:
        line = loc.line - 1
        column = loc.column or 0
        end_line = loc.end_line - 1
        end_column = loc.end_column
        if end_column is None:
            end_column = 0
            end_line = loc.line + 1
        range_ = types.Range(
            start=types.Position(line=line, character=column),
            end=types.Position(line=end_line, character=end_column),
        )
    else:
        zero = types.Position(line=0, character=0)
        range_ = types.Range(start=zero, end=zero)

    return types.Diagnostic(
        message=message, severity=_map_severity(level), range=range_, source=_NAME
    )


def _map_severity(log_level: LogLevel) -> DiagnosticSeverity:
    if log_level == LogLevel.error:
        return DiagnosticSeverity.Error
    if log_level == LogLevel.warning:
        return DiagnosticSeverity.Warning
    return DiagnosticSeverity.Information


if __name__ == "__main__":
    main()
