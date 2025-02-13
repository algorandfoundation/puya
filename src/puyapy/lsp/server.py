import asyncio
import sys
import typing
from collections.abc import Sequence
from importlib.metadata import version

from lsprotocol import types
from lsprotocol.types import DiagnosticSeverity
from pygls.lsp.server import LanguageServer

from puya.log import LogLevel, get_logger
from puya.parse import SourceLocation
from puya.service import PuyaClient
from puyapy.lsp.analyse import CodeAnalyticTracker
from puyapy.parse import get_python_executable

logger = get_logger(__name__)

_DEBOUNCE_INTERVAL = 0.5


class PuyaPyLanguageServer(LanguageServer):
    def __init__(self, name: str, version: str) -> None:
        super().__init__(name, version=version)
        logger.info(f"{name} - {version}")
        logger.debug(f"Server location: {__file__}")
        self.diagnostics = dict[str, tuple[int | None, list[types.Diagnostic]]]()
        self._current_refresh_token = object()
        self._to_analyse = dict[str, None]()
        self.tracker: CodeAnalyticTracker | None = None

    async def analyse_and_publish(self, changed_uris: Sequence[str]) -> None:
        assert self.tracker is not None, "server not initialized"
        uri_logs = await self.tracker.parse(changed_uris)
        uri_diagnostics = dict[str, tuple[int | None, list[types.Diagnostic]]]()

        # convert logs to diagnostics
        for uri, logs in uri_logs.items():
            for log in logs:
                assert log.location is not None, "expected only logs with locations"
                doc = self.workspace.get_text_document(uri)
                _, version_diags = uri_diagnostics.setdefault(uri, (doc.version, []))
                range_ = self._resolve_location(log.location)
                version_diags.append(
                    _diag(
                        log.message,
                        log.level,
                        range_,
                        data=self._get_diag_data(uri, range_),
                    )
                )
        # publish diagnostics
        for uri in uri_logs:
            try:
                version, diagnostics = uri_diagnostics[uri]
            except KeyError:
                version = self.workspace.get_text_document(uri).version
                diagnostics = []
            self.diagnostics[uri] = (version, diagnostics)
            logger.debug(f"Publish {len(diagnostics)} diagnostics for {uri=}, {version=}")
            self.text_document_publish_diagnostics(
                types.PublishDiagnosticsParams(
                    uri=uri,
                    version=version,
                    diagnostics=diagnostics,
                )
            )

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

    def _get_diag_data(self, uri: str, range_: types.Range) -> object:
        document = self.workspace.get_text_document(uri)
        lines = list(document.lines[range_.start.line : range_.end.line + 1])
        # do end_column first in case line == end_line
        lines[-1] = lines[-1][: range_.end.character]
        lines[0] = lines[0][range_.start.character :]
        src = "\n".join(lines)
        return {"source": src}

    async def queue_diagnostics(self, params: "_HasTextDocument") -> None:
        logger.debug(f"queue_diagnostics: {params.text_document.uri}")
        self._to_analyse[params.text_document.uri] = None
        token = self._current_refresh_token = object()
        await asyncio.sleep(_DEBOUNCE_INTERVAL)
        # if no other refreshes have been received, then proceed to update diagnostics
        if self._current_refresh_token is token:
            to_analyse = list(self._to_analyse)
            self._to_analyse.clear()
            await self.analyse_and_publish(to_analyse)


class _HasTextDocument(typing.Protocol):
    @property
    def text_document(self) -> types.VersionedTextDocumentIdentifier: ...


def create_server() -> PuyaPyLanguageServer:
    server = PuyaPyLanguageServer("puyapy", version=version("puyapy"))

    async def _queue_diagnostics(ls: PuyaPyLanguageServer, params: _HasTextDocument) -> None:
        await ls.queue_diagnostics(params)

    server.feature(types.TEXT_DOCUMENT_DID_OPEN)(_queue_diagnostics)
    server.feature(types.TEXT_DOCUMENT_DID_CHANGE)(_queue_diagnostics)

    @server.feature(types.INITIALIZE)
    async def _initialization(ls: PuyaPyLanguageServer, params: types.InitializeParams) -> None:
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
        puya_service = await _puya_service()

        # the following is to work around a deadlock issue in mypy.modulefinder.get_search_dirs
        # when mixing async code and mypy on windows.
        # by calling get_search_dirs here on initialization, the deadlock issue is avoided
        from mypy.modulefinder import get_search_dirs

        python_executable = get_python_executable(analysis_prefix)
        get_search_dirs(python_executable)
        ls.tracker = CodeAnalyticTracker(
            python_executable=python_executable,
            puya_service=puya_service,
            workspace=ls.workspace,
        )

    @server.feature(
        types.TEXT_DOCUMENT_CODE_ACTION,
        types.CodeActionOptions(code_action_kinds=[types.CodeActionKind.QuickFix]),
    )
    def code_actions(
        ls: PuyaPyLanguageServer, params: types.CodeActionParams
    ) -> list[types.CodeAction]:
        items = []
        document_uri = params.text_document.uri
        logger.debug(f"received code action request {document_uri}")
        try:
            _, diagnostics = ls.diagnostics[document_uri]
        except KeyError:
            logger.debug(f"code actions not found for {document_uri}")
            diagnostics = []
        else:
            logger.debug(f"found {len(diagnostics)} for {document_uri}")

        for diag in diagnostics:
            if diag.severity in (DiagnosticSeverity.Warning, DiagnosticSeverity.Error):
                # POC - fix an int
                if diag.message == "a Python literal is not valid at this location" and isinstance(
                    diag.data, dict
                ):
                    src = diag.data.get("source", "")
                    # TODO: resolve algopy.UInt64 to correct alias in document
                    #       fall back to fully qualified type name if unknown
                    uint64_symbol = "UInt64"
                    fix = types.TextEdit(
                        range=diag.range,
                        new_text=f"{uint64_symbol}({src})",
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

    return server


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
        source="puyapy",
        data=data,
    )


def _map_severity(log_level: LogLevel) -> DiagnosticSeverity:
    if log_level == LogLevel.error:
        return DiagnosticSeverity.Error
    if log_level == LogLevel.warning:
        return DiagnosticSeverity.Warning
    return DiagnosticSeverity.Information


async def _puya_service() -> PuyaClient:
    # Find the puya executable path
    python_path = sys.executable
    client = PuyaClient()
    # start the server
    await client.start_io(python_path, "-m", "puya", "serve")
    return client
