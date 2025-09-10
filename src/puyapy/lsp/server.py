import asyncio
import contextlib
import importlib.metadata
import sys
import typing
from collections.abc import Iterable, Sequence
from pathlib import Path

import attrs
from lsprotocol import types
from lsprotocol.types import DiagnosticSeverity
from pygls.lsp.server import LanguageServer

from puya.errors import ConfigurationError
from puya.log import Log, LogLevel, get_logger
from puya.parse import SourceLocation
from puya.service import PuyaClient
from puyapy.lsp import code_fixes
from puyapy.lsp.analyse import CodeAnalyser, DocumentAnalysis
from puyapy.lsp.code_fixes import CodeFix

logger = get_logger(__name__)

_DEFAULT_DEBOUNCE_INTERVAL: typing.Final = 0.5


class _HasTextDocument(typing.Protocol):
    @property
    def text_document(self) -> types.VersionedTextDocumentIdentifier: ...


def create_server() -> "PuyaPyLanguageServer":
    server = PuyaPyLanguageServer("puyapy", version=importlib.metadata.version("puyapy"))

    async def _queue_diagnostics(ls: PuyaPyLanguageServer, params: _HasTextDocument) -> None:
        await ls.queue_diagnostics(params)

    server.feature(types.TEXT_DOCUMENT_DID_OPEN)(_queue_diagnostics)
    server.feature(types.TEXT_DOCUMENT_DID_CHANGE)(_queue_diagnostics)

    @server.feature(types.INITIALIZE)
    def initialize(ls: PuyaPyLanguageServer, params: types.InitializeParams) -> None:
        options = params.initialization_options
        python_executable = None
        if isinstance(options, dict):
            with contextlib.suppress(KeyError):
                python_executable = options["pythonExecutable"]
            with contextlib.suppress(KeyError):
                ls.debounce_interval = options["debounceInterval"]
        if not python_executable:
            raise ConfigurationError("pythonExecutable not specified in initialization_options")
        # the following is to work around a deadlock issue in mypy.modulefinder.get_search_dirs
        # when mixing async code and mypy on windows.
        # by calling get_search_dirs here on initialization, the deadlock issue is avoided

        # NOTE: either initialize must remain synchronous, or get_search_dirs should be async
        from puyapy.parse import get_search_dirs

        # TODO: perhaps language server should cache SearchPaths itself
        get_search_dirs(python_executable)
        ls.python_executable = python_executable

    @server.feature(types.SHUTDOWN)
    async def shutdown(ls: PuyaPyLanguageServer, _params: None) -> None:
        await ls.stop_puya_service()

    @server.feature(
        types.TEXT_DOCUMENT_CODE_ACTION,
        types.CodeActionOptions(code_action_kinds=[types.CodeActionKind.QuickFix]),
    )
    async def code_actions(
        ls: PuyaPyLanguageServer, params: types.CodeActionParams
    ) -> list[types.CodeAction]:
        return await ls.get_code_actions(params.text_document.uri)

    return server


def _fix_to_code_action(analysis: DocumentAnalysis, uri: str, fix: CodeFix) -> types.CodeAction:
    loc = fix.loc
    edit = fix.edit
    match edit:
        case code_fixes.WrapWithSymbol(symbol=symbol):
            maybe_symbol_insert = analysis.get_alias_and_import_insert(symbol)
            symbol_alias, maybe_import_edit = _symbol_import_to_alias_and_edit(
                maybe_symbol_insert or symbol
            )
            edits = list[types.TextEdit]()
            if maybe_import_edit:
                edits.append(maybe_import_edit)

            assert loc.column is not None, "column must be set"
            assert loc.end_column is not None, "end_column must be set"
            wrap_start = types.Position(line=loc.line - 1, character=loc.column)
            wrap_end_insert = types.Position(line=loc.end_line - 1, character=loc.end_column + 1)
            edits.append(
                types.TextEdit(
                    range=types.Range(wrap_end_insert, wrap_end_insert),
                    new_text=")",
                )
            )
            edits.append(
                types.TextEdit(
                    range=types.Range(wrap_start, wrap_start),
                    new_text=f"{symbol_alias}(",
                )
            )
            return types.CodeAction(
                title=f"Use {symbol}",
                kind=types.CodeActionKind.QuickFix,
                edit=types.WorkspaceEdit(changes={uri: edits}),
            )
        case code_fixes.ReplaceWithSymbol(symbol=symbol):
            maybe_symbol_insert = analysis.get_alias_and_import_insert(symbol)
            symbol_alias, maybe_import_edit = _symbol_import_to_alias_and_edit(
                maybe_symbol_insert or symbol
            )
            edits = list[types.TextEdit]()
            if maybe_import_edit:
                edits.append(maybe_import_edit)
            types.TextEdit(
                range=_source_location_to_range(loc),
                new_text=symbol_alias,
            )
            return types.CodeAction(
                title=f"Use {symbol}",
                kind=types.CodeActionKind.QuickFix,
                edit=types.WorkspaceEdit(changes={uri: edits}),
            )
        case code_fixes.ReplaceWithMember(expr_location=expr_loc, member=member):
            remove = types.TextEdit(
                range=_source_location_to_range(loc),
                new_text="",
            )
            end = _source_location_to_range(expr_loc).end
            insert_at_end = attrs.evolve(end, character=end.character + 1)
            append = types.TextEdit(
                range=types.Range(insert_at_end, insert_at_end),
                new_text=f".{member}",
            )
            return types.CodeAction(
                title=f"Use .{member}",
                kind=types.CodeActionKind.QuickFix,
                edit=types.WorkspaceEdit(changes={uri: [append, remove]}),
            )
        case _:
            typing.assert_never(edit)


def _symbol_import_to_alias_and_edit(
    symbol_import: str | tuple[str, str, SourceLocation],
) -> tuple[str, types.TextEdit | None]:
    text_edit = None
    if isinstance(symbol_import, str):
        symbol_alias = symbol_import
    else:
        symbol_alias, import_stmt, insert_at = symbol_import
        assert insert_at.column is not None, "column must be set"
        import_insert = types.Position(insert_at.line - 1, insert_at.column)
        text_edit = types.TextEdit(
            range=types.Range(import_insert, import_insert),
            new_text=f"{import_stmt}\n",
        )
    return symbol_alias, text_edit


class PuyaPyLanguageServer(LanguageServer):
    def __init__(self, name: str, version: str) -> None:
        super().__init__(name, version=version)
        logger.info(f"{name} - {version}")
        logger.debug(f"Server location: {__file__}")
        self.debounce_interval = _DEFAULT_DEBOUNCE_INTERVAL
        self.python_executable: Path | None = None
        self._analysis = dict[str, DocumentAnalysis]()
        self._analyser: CodeAnalyser | None = None
        self._analyser_lock = asyncio.Lock()
        self._puya_service: PuyaClient | None = None
        self._current_refresh_token = object()
        self._to_analyse = dict[str, None]()

    async def queue_diagnostics(self, params: "_HasTextDocument") -> None:
        logger.debug(f"queue_diagnostics: {params.text_document.uri}")
        self._to_analyse[params.text_document.uri] = None
        token = self._current_refresh_token = object()
        if self.debounce_interval:
            await asyncio.sleep(self.debounce_interval)
        # if no other refreshes have been received, then proceed to update diagnostics
        if self._current_refresh_token is token:
            to_analyse = list(self._to_analyse)
            self._to_analyse.clear()
            await self._analyse_and_publish(to_analyse)

    async def _analyse_and_publish(self, changed_uris: Sequence[str]) -> None:
        analyser = await self._get_analyser()
        analysis = await analyser.analyse(changed_uris)
        self._analysis.update(analysis)
        self._publish_diagnostics(analysis.keys())

    def _publish_diagnostics(self, uris: Iterable[str]) -> None:
        for uri in uris:
            uri_analysis = self._analysis[uri]
            version = uri_analysis.version
            diagnostics = list(map(_log_to_diag, uri_analysis.logs))

            logger.debug(f"Publish {len(diagnostics)} diagnostics for {uri=}, {version=}")
            self.text_document_publish_diagnostics(
                types.PublishDiagnosticsParams(
                    uri=uri,
                    version=version,
                    diagnostics=diagnostics,
                )
            )

    async def stop_puya_service(self) -> None:
        if self._puya_service:
            logger.debug("stopping puya service")
            await self._puya_service.shutdown_async()
            await self._puya_service.stop()  # type: ignore[no-untyped-call]

    async def get_code_actions(self, document_uri: str) -> list[types.CodeAction]:
        try:
            analysis = self._analysis[document_uri]
        except KeyError:
            return []
        logger.debug(f"found {len(analysis.fixes)} fixes for {document_uri}")

        return [_fix_to_code_action(analysis, document_uri, fix) for fix in analysis.fixes]

    async def _get_analyser(self) -> CodeAnalyser:
        async with self._analyser_lock:
            # the analyser is lazily constructed as it needs python_executable received
            # during language server initialization.
            # Additionally, initialization cannot contain asynchronous code due to a deadlock
            # issue on windows with get_search_paths
            if not self.python_executable:
                raise ConfigurationError("language server is not initialized")
            if not self._puya_service:
                self._puya_service = await _puya_service()
            if not self._analyser:
                self._analyser = CodeAnalyser(
                    python_executable=Path(self.python_executable),
                    puya_service=self._puya_service,
                    workspace=self.workspace,
                )
            return self._analyser


def _log_to_diag(log: Log) -> types.Diagnostic:
    assert log.location, "expected non none locations when converting to a diagnostic"
    return types.Diagnostic(
        message=log.message,
        severity=_log_level_to_severity(log.level),
        range=_source_location_to_range(log.location),
        source="puyapy",
    )


def _log_level_to_severity(log_level: LogLevel) -> DiagnosticSeverity:
    if log_level == LogLevel.error:
        return DiagnosticSeverity.Error
    if log_level == LogLevel.warning:
        return DiagnosticSeverity.Warning
    return DiagnosticSeverity.Information


def _source_location_to_range(loc: SourceLocation) -> types.Range:
    if loc and loc.file:
        line = loc.line - 1
        column = loc.column or 0
        end_line = loc.end_line - 1
        end_column = loc.end_column
        if end_column is None:
            end_line += 1
            end_column = 0
        return types.Range(
            start=types.Position(line=line, character=column),
            end=types.Position(line=end_line, character=end_column),
        )
    else:
        zero = types.Position(line=0, character=0)
        return types.Range(start=zero, end=zero)


async def _puya_service() -> PuyaClient:
    # Find the puya executable path
    python_path = sys.executable
    client = PuyaClient()
    # start the server
    await client.start_io(python_path, "-m", "puya", "serve")
    return client
