import importlib.metadata
import threading
import time
import typing
from collections.abc import Mapping

import attrs
from lsprotocol import types
from lsprotocol.types import DiagnosticSeverity
from pygls.lsp.server import LanguageServer
from pygls.workspace import TextDocument

from puya.log import Log, LogLevel, get_logger
from puya.parse import SourceLocation
from puya.utils import StableSet
from puyapy import interpreter_data
from puyapy.lsp import code_fixes
from puyapy.lsp.analyse import CodeAnalyser, DocumentAnalysis
from puyapy.lsp.code_fixes import CodeFix
from puyapy.parse import get_sys_path

logger = get_logger(__name__)

_DEFAULT_DEBOUNCE_INTERVAL: typing.Final = 0.5


def create_server() -> LanguageServer:
    server = LanguageServer("puyapy", version=importlib.metadata.version("puyapy"))
    logger.info(f"{server.name} - {server.version}")
    logger.debug(f"Server location: {__file__}")

    server.feature(types.INITIALIZE)(_initialize_language_server)
    return server


def _initialize_language_server(ls: LanguageServer, init_params: types.InitializeParams) -> None:
    logger.debug("initializing server")
    options = init_params.initialization_options or {}
    python_executable = options.get("pythonExecutable")
    debounce_interval = options.get("debounceInterval", _DEFAULT_DEBOUNCE_INTERVAL)
    # note: ideally, search_paths would be updated whenever the venv is modified
    #       however, there are two things that make that tricky
    #       1.) Detecting when it's modified
    #       2.) Calling get_sys_path outside the initialize phase on Windows seems to block until
    #           the async event loop used by LanguageServer ends
    if python_executable is None:
        logger.debug("no python executable defined, using current search paths")
        search_paths = interpreter_data.get_sys_path()
    else:
        logger.debug(f"using {python_executable} to discover search paths")
        search_paths = get_sys_path(python_executable)
    logger.debug(f"using search paths: {search_paths}")
    puyapy_ls = PuyaPyLanguageServer(
        ls=ls,
        debounce_interval=debounce_interval,
        analyser=CodeAnalyser(
            workspace=ls.workspace,
            package_search_paths=search_paths,
        ),
    )

    @ls.feature(types.TEXT_DOCUMENT_DID_OPEN)
    def text_document_did_open(
        _ls: LanguageServer, params: types.DidOpenTextDocumentParams
    ) -> None:
        puyapy_ls.queue_diagnostics(params.text_document.uri)

    @ls.feature(types.TEXT_DOCUMENT_DID_CHANGE)
    def text_document_did_change(
        _ls: LanguageServer, params: types.DidChangeTextDocumentParams
    ) -> None:
        puyapy_ls.queue_diagnostics(params.text_document.uri)

    @ls.feature(
        types.TEXT_DOCUMENT_CODE_ACTION,
        types.CodeActionOptions(code_action_kinds=[types.CodeActionKind.QuickFix]),
    )
    def code_actions(
        _ls: LanguageServer, params: types.CodeActionParams
    ) -> list[types.CodeAction]:
        return puyapy_ls.get_code_actions(params.text_document.uri, params.range)


URI: typing.TypeAlias = str


@attrs.define
class PuyaPyLanguageServer:
    _debounce_interval: float
    _ls: LanguageServer
    _analyser: CodeAnalyser
    _analysis: dict[URI, DocumentAnalysis] = attrs.field(factory=dict, init=False)
    _changed_uris: StableSet[URI] = attrs.field(factory=StableSet, init=False)
    _work_available: threading.Event = attrs.field(factory=threading.Event, init=False)
    _analysis_lock: threading.Lock = attrs.field(factory=threading.Lock, init=False)
    _last_trigger: float = attrs.field(default=0.0, init=False)
    _analysis_thread: threading.Thread = attrs.field(init=False)

    @_analysis_thread.default
    def _analysis_thread_factory(self) -> threading.Thread:
        thread = threading.Thread(target=self._analysis_worker_loop, daemon=True)
        thread.start()
        return thread

    def queue_diagnostics(self, uri: URI) -> None:
        logger.debug(f"queue_diagnostics: {uri}")
        with self._analysis_lock:
            self._changed_uris.add(uri)
            self._last_trigger = time.time()
            self._work_available.set()

    def get_code_actions(self, document_uri: URI, range_: types.Range) -> list[types.CodeAction]:
        try:
            analysis = self._analysis[document_uri]
        except KeyError:
            logger.debug(f"no analysis found for {document_uri}")
            return []
        logger.debug(f"found {len(analysis.fixes)} fixes for {document_uri}")

        fixes = [fix for fix in analysis.fixes if _loc_in_range(fix.location, range_)]
        doc = self._ls.workspace.get_text_document(document_uri)
        return [_fix_to_code_action(doc, analysis, document_uri, fix) for fix in fixes]

    def _analysis_worker_loop(self) -> None:
        logger.debug("analysis loop started")
        # loop indefinitely, thread is a daemon and will be killed when the process is terminated
        while True:
            self._work_available.wait()
            logger.debug("analysis work available")
            while (time_remaining := self._time_to_wait_for_debounce()) > 0:
                logger.debug(f"waiting for debounce interval to expire: {time_remaining=:.2f}s")
                time.sleep(time_remaining)
            logger.debug("debounce interval elapsed, performing analysis")
            with self._analysis_lock:
                changed = list(self._changed_uris)
                self._changed_uris.clear()
                self._work_available.clear()
            start = time.time()
            analysis = self._analyser.analyse(changed)
            duration = time.time() - start
            logger.debug(f"analysis took {duration:.2f}s")
            self._analysis.update(analysis)
            self._publish_diagnostics(analysis)

    def _time_to_wait_for_debounce(self) -> float:
        return self._last_trigger + self._debounce_interval - time.time()

    def _publish_diagnostics(self, uris: Mapping[URI, DocumentAnalysis]) -> None:
        for uri, analysis in uris.items():
            version = analysis.version
            diagnostics = list(map(_log_to_diag, analysis.logs))

            logger.debug(f"Publish {len(diagnostics)} diagnostics for {uri=}, {version=}")
            self._ls.text_document_publish_diagnostics(
                types.PublishDiagnosticsParams(
                    uri=uri,
                    version=version,
                    diagnostics=diagnostics,
                )
            )


def _fix_to_code_action(
    doc: TextDocument, analysis: DocumentAnalysis, uri: URI, fix: CodeFix
) -> types.CodeAction:
    range_ = _source_location_to_range(fix.location)
    edit = fix.edit
    title = ""
    edits = list[types.TextEdit]()
    match edit:
        case code_fixes.WrapWithSymbol(symbol=symbol):
            title = f"Use {symbol}"

            symbol_alias = _get_symbol_alias(analysis, symbol, edits)
            wrap_start = range_.start
            wrap_end_insert = range_.end
            edits.extend(
                (
                    types.TextEdit(
                        range=types.Range(wrap_end_insert, wrap_end_insert),
                        new_text=")",
                    ),
                    types.TextEdit(
                        range=types.Range(wrap_start, wrap_start),
                        new_text=f"{symbol_alias}(",
                    ),
                )
            )
        case code_fixes.ReplaceWithSymbol(symbol=symbol):
            title = f"Use {symbol}"

            symbol_alias = _get_symbol_alias(analysis, symbol, edits)
            edits.append(
                types.TextEdit(
                    range=range_,
                    new_text=symbol_alias,
                )
            )
        case code_fixes.ReplaceWithMember(expr_location=expr_loc, member=member):
            title = f"Use .{member}"

            end = _source_location_to_range(expr_loc).end
            insert_at_end = attrs.evolve(end, character=end.character + 1)
            edits.extend(
                (
                    types.TextEdit(
                        range=types.Range(insert_at_end, insert_at_end),
                        new_text=f".{member}",
                    ),
                    types.TextEdit(
                        range=range_,
                        new_text="",
                    ),
                )
            )
        case code_fixes.DecorateFunction(symbol=symbol):
            title = f"Use @{symbol}"

            symbol_alias = _get_symbol_alias(analysis, symbol, edits)
            func_start = range_.start
            insert_position = types.Position(line=func_start.line - 1, character=0)

            whitespace = doc.lines[func_start.line][: func_start.character]
            edits.append(
                types.TextEdit(
                    range=types.Range(insert_position, insert_position),
                    new_text=f"{whitespace}@{symbol_alias}",
                )
            )
        case _:
            typing.assert_never(edit)
    return types.CodeAction(
        title=title,
        kind=types.CodeActionKind.QuickFix,
        edit=types.WorkspaceEdit(changes={uri: edits}),
    )


def _get_symbol_alias(
    analysis: DocumentAnalysis,
    symbol: str,
    edits: list[types.TextEdit],
) -> str:
    maybe_symbol_insert = analysis.get_alias_and_import_insert(symbol) or symbol
    if isinstance(maybe_symbol_insert, str):
        alias = maybe_symbol_insert
    else:
        alias = maybe_symbol_insert.alias
        insert_line = maybe_symbol_insert.import_line - 1
        import_insert = types.Position(insert_line, 0)
        text_edit = types.TextEdit(
            range=types.Range(import_insert, import_insert),
            new_text=f"{maybe_symbol_insert.import_stmt}\n",
        )
        edits.append(text_edit)
    return alias


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


def _loc_in_range(loc: SourceLocation, range_: types.Range) -> bool:
    loc_as_range = _source_location_to_range(loc)
    if loc_as_range.end < range_.start:
        return False
    return loc_as_range.start <= range_.end
