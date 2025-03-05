import asyncio
import contextlib
import sys
import time
import typing
from collections.abc import Iterator, Sequence
from pathlib import Path

import attrs
from lsprotocol import types
from lsprotocol.types import DiagnosticSeverity
from pygls.lsp.server import LanguageServer

from puya.compile import awst_to_teal
from puya.errors import log_exceptions
from puya.log import Log, LoggingContext, LogLevel, get_logger, logging_context
from puya.parse import SourceLocation
from puyapy.awst_build.main import transform_ast
from puyapy.compile import determine_out_dir, parse_with_mypy
from puyapy.lsp import constants
from puyapy.options import PuyaPyOptions
from puyapy.parse import ParseResult

logger = get_logger(__name__)

_DEBOUNCE_INTERVAL = 0.6


class PuyaPyLanguageServer(LanguageServer):
    def __init__(self, name: str, version: str) -> None:
        super().__init__(name, version=version)
        logger.info(f"{name} - {version}")
        logger.debug(f"Server location: {__file__}")
        self.diagnostics = dict[str, tuple[int | None, list[types.Diagnostic]]]()
        self.analysis_prefix: Path | None = None
        self.current_refresh_token = object()

    def parse_all(self) -> None:
        # get all sources tracked by the workspace
        options = PuyaPyOptions(
            log_level=LogLevel.warning,
            paths=self._discover_algopy_paths(Path(self.workspace.root_path)),
            # don't need optimization for analysis
            optimization_level=0,
            prefix=self.analysis_prefix,
        )
        logs = self._parse_and_log(options)

        # need to include existing documents in diagnostics in case all errors are cleared
        diagnostics: dict[str, tuple[int | None, list[types.Diagnostic]]] = {
            uri: (self.workspace.get_text_document(uri).version, []) for uri in self.diagnostics
        }
        for log in logs:
            if log.location and log.location.file and log.level > LogLevel.info:
                uri = log.location.file.as_uri()
                doc = self.workspace.get_text_document(uri)
                version_diags = diagnostics.setdefault(uri, (doc.version, []))[1]
                range_ = self._resolve_location(log.location)
                version_diags.append(
                    _diag(
                        log.message,
                        log.level,
                        range_,
                        data=self._get_source_code_data(uri, range_),
                    )
                )
        self.diagnostics = diagnostics

    def _resolve_location(self, loc: SourceLocation) -> types.Range:
        if loc and loc.file:
            line = loc.line - 1
            column = loc.column or 0
            end_line = loc.end_line - 1
            end_column = loc.end_column
            if end_column is None:
                document = self.workspace.get_text_document(loc.file.as_uri())
                end_column = len(document.lines[end_line])
            return types.Range(
                start=types.Position(line=line, character=column),
                end=types.Position(line=end_line, character=end_column),
            )
        else:
            zero = types.Position(line=0, character=0)
            return types.Range(start=zero, end=zero)

    def _get_source_code_data(self, uri: str, range_: types.Range) -> object:
        document = self.workspace.get_text_document(uri)
        lines = document.lines[range_.start.line : range_.end.line + 1]
        # do end_column first in case line == end_line
        lines[-1] = lines[-1][: range_.end.character]
        lines[0] = lines[0][range_.start.character :]
        source_code = "\n".join(lines)
        return {"source_code": source_code}

    def _filter_parse_results(
        self, log_ctx: LoggingContext, parse_result: ParseResult
    ) -> ParseResult:
        files_with_errors = {
            log.location.file
            for log in log_ctx.logs
            if log.level == LogLevel.error and log.location and log.location.file
        }
        return attrs.evolve(
            parse_result,
            ordered_modules={
                p: m
                for p, m in parse_result.ordered_modules.items()
                if m.path not in files_with_errors
            },
        )

    def get_source(self, path: Path) -> Sequence[str] | None:
        uri = path.as_uri()
        try:
            source = self.workspace.text_documents[uri].source
        except KeyError:
            return None
        assert isinstance(source, str)
        return source.splitlines()

    def _parse_and_log(self, puyapy_options: PuyaPyOptions) -> Sequence[Log]:
        with logging_context() as log_ctx, log_exceptions():
            with _time_it("mypy parsing"):
                try:
                    parse_result = parse_with_mypy(
                        puyapy_options.paths, prefix=puyapy_options.prefix, source_provider=self
                    )
                except Exception as ex:
                    logger.debug(f"internal mypy error: {ex}")
                    return log_ctx.logs
                log_ctx.source_provider = parse_result.source_provider
            if log_ctx.num_errors:
                # if there were type checking errors
                # attempt to continue with any modules that don't have errors
                parse_result = self._filter_parse_results(log_ctx, parse_result)
            with _time_it("awst building"):
                awst, compilation_targets = transform_ast(parse_result)
            # if no errors, then attempt to lower further
            if not log_ctx.num_errors:
                awst_lookup = {n.id: n for n in awst}
                compilation_set = {
                    target_id: determine_out_dir(loc.file.parent, puyapy_options)
                    for target_id, loc in (
                        (t, awst_lookup[t].source_location) for t in compilation_targets
                    )
                    if loc.file
                }
                with _time_it("teal compilation"):
                    awst_to_teal(
                        log_ctx,
                        puyapy_options,
                        compilation_set,
                        parse_result.source_provider,
                        awst,
                    )
        return log_ctx.logs

    def _discover_algopy_paths(self, root_path: Path) -> list[Path]:
        """Discover all algopy paths in the workspace"""
        algopy_paths = []
        for path in root_path.rglob("*.py"):
            assert isinstance(path, Path)
            if self.analysis_prefix in path.parents:
                continue
            # not using get_text_document to avoid creating an entry
            try:
                source = self.workspace.text_documents[path.as_uri()].source
            except KeyError:
                source = path.read_text()
            # naive filtering of documents to anything that references algopy
            if "algopy" in source:
                algopy_paths.append(path)
        return algopy_paths


server = PuyaPyLanguageServer(constants.NAME, version=constants.VERSION)


class _HasTextDocument(typing.Protocol):
    @property
    def text_document(self) -> types.VersionedTextDocumentIdentifier: ...


async def _queue_diagnostics(ls: PuyaPyLanguageServer, _params: _HasTextDocument) -> None:
    token = ls.current_refresh_token = object()
    await asyncio.sleep(_DEBOUNCE_INTERVAL)
    # if no other refreshes have been received then proceed to update diagnostics
    if ls.current_refresh_token is token:
        # note: this runs on the main thread and will block further messages until it is complete
        #       currently this desirable to provide a consistent state
        _refresh_diagnostics(ls)


def _refresh_diagnostics(ls: PuyaPyLanguageServer) -> None:
    """Refresh all diagnostics when a document changes"""
    with _time_it("parsing workspace"):
        ls.parse_all()

    # currently publishes for all documents, ideally only publishes for documents that have changes
    for uri, (doc_version, diagnostics) in ls.diagnostics.items():
        ls.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(
                uri=uri,
                version=doc_version,
                diagnostics=diagnostics,
            )
        )


server.feature(types.TEXT_DOCUMENT_DID_SAVE)(_queue_diagnostics)
server.feature(types.TEXT_DOCUMENT_DID_OPEN)(_queue_diagnostics)
server.feature(types.TEXT_DOCUMENT_DID_CHANGE)(_queue_diagnostics)


@server.feature(types.INITIALIZE)
def _initialization(ls: PuyaPyLanguageServer, params: types.InitializeParams) -> None:
    options = params.initialization_options
    if options and isinstance(options, dict):
        analysis_prefix = options.get("analysisPrefix")
    else:
        analysis_prefix = ""
    if not analysis_prefix:
        analysis_prefix = sys.prefix
        ls.window_log_message(
            types.LogMessageParams(
                type=types.MessageType.Warning,
                message=f"No analysis prefix provided, using {analysis_prefix}",
            )
        )
    ls.analysis_prefix = Path(analysis_prefix)


@server.feature(
    types.TEXT_DOCUMENT_CODE_ACTION,
    types.CodeActionOptions(code_action_kinds=[types.CodeActionKind.QuickFix]),
)
def code_actions(
    ls: PuyaPyLanguageServer, params: types.CodeActionParams
) -> list[types.CodeAction]:
    items = []
    document_uri = params.text_document.uri
    try:
        _, diagnostics = ls.diagnostics[document_uri]
    except KeyError:
        diagnostics = []
    for diag in diagnostics:
        if diag.severity in (DiagnosticSeverity.Warning, DiagnosticSeverity.Error):
            # POC - fix an int
            if diag.message == "a Python literal is not valid at this location" and isinstance(
                diag.data, dict
            ):
                source_code = diag.data.get("source_code", "")
                # TODO: resolve algopy.UInt64 to correct alias in document
                #       fall back to fully qualified type name if unknown
                uint64_symbol = "UInt64"
                fix = types.TextEdit(
                    range=diag.range,
                    new_text=f"{uint64_symbol}({source_code})",
                )
                action = types.CodeAction(
                    title="Use algopy.UInt64",
                    kind=types.CodeActionKind.QuickFix,
                    edit=types.WorkspaceEdit(changes={document_uri: [fix]}),
                )
                items.append(action)
            else:
                pass
    return items


def _diag(
    message: str,
    level: LogLevel,
    range_: types.Range,
    data: object = None,
) -> types.Diagnostic:
    return types.Diagnostic(
        message=message,
        severity=_map_severity(level),
        range=range_,
        source=constants.NAME,
        data=data,
    )


def _map_severity(log_level: LogLevel) -> DiagnosticSeverity:
    if log_level == LogLevel.error:
        return DiagnosticSeverity.Error
    if log_level == LogLevel.warning:
        return DiagnosticSeverity.Warning
    return DiagnosticSeverity.Information


@contextlib.contextmanager
def _time_it(name: str) -> Iterator[None]:
    start = time.perf_counter()
    yield
    duration = time.perf_counter() - start
    logger.info(f"{name} took {duration:.3f}s")
