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
from puyapy import code_fixes, interpreter_data
from puyapy.lsp.analyse import (
    CodeAnalyser,
    DocumentAnalysis,
)
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
            diagnostics = list(map(_log_to_diagnostic, analysis.logs))

            logger.debug(f"Publish {len(diagnostics)} diagnostics for {uri=}, {version=}")
            self._ls.text_document_publish_diagnostics(
                types.PublishDiagnosticsParams(
                    uri=uri,
                    version=version,
                    diagnostics=diagnostics,
                )
            )


def _fix_to_code_action(
    doc: TextDocument, analysis: DocumentAnalysis, uri: URI, fix: code_fixes.CodeFix
) -> types.CodeAction:
    range_ = _source_location_to_range(fix.location)
    edit = fix.edit
    title = ""
    edits = list[types.TextEdit]()
    match edit:
        case code_fixes.WrapWithSymbol(symbol=symbol):
            title = f"Use {symbol}"

            symbol_alias = _get_symbol_alias(analysis.symbols, symbol, edits)
            edits.extend(
                (
                    types.TextEdit(
                        range=types.Range(range_.end, range_.end),
                        new_text=")",
                    ),
                    types.TextEdit(
                        range=types.Range(range_.start, range_.start),
                        new_text=f"{symbol_alias}(",
                    ),
                )
            )
        case code_fixes.ReplaceWithSymbol(symbol=symbol):
            title = f"Use {symbol}"

            symbol_alias = _get_symbol_alias(analysis.symbols, symbol, edits)
            edits.append(
                types.TextEdit(
                    range=range_,
                    new_text=symbol_alias,
                )
            )
        case code_fixes.DecorateFunction(symbol=symbol):
            title = f"Use @{symbol}"

            symbol_alias = _get_symbol_alias(analysis.symbols, symbol, edits)
            func_start = range_.start
            insert_position = types.Position(line=func_start.line - 1, character=0)

            # use the same whitespace as function for consistent indentation
            whitespace = doc.lines[func_start.line][: func_start.character]
            edits.append(
                types.TextEdit(
                    range=types.Range(insert_position, insert_position),
                    new_text=f"\n{whitespace}@{symbol_alias}",
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
    symbols: dict[str, str | int], full_name: str, edits: list[types.TextEdit]
) -> str:
    """
    Give the algopy import symbols in a document, return the appropriate alias for a
    fully qualified symbol in that document, will add an import stmt to edits if required"""
    # if full symbol has an alias return that
    try:
        import_symbol = symbols[full_name]
    except KeyError:
        pass
    else:
        assert isinstance(import_symbol, str), "expected a symbol"
        return import_symbol

    # otherwise split full_name into its module and symbol
    try:
        symbol_module, symbol = full_name.rsplit(".", maxsplit=1)
    except ValueError:
        # symbols should be scoped to a module, give up
        return full_name

    # if symbol module is available, then resolve symbol relative to that
    try:
        module = symbols[symbol_module]
    except KeyError:
        return full_name
    match module:
        case "":
            # if everything from a module was * imported, then can just use the symbol
            return symbol
        case str():
            # if module itself was imported then reference symbol relative to that
            return f"{module}.{symbol}"
        case int(line_after_import):
            # if just siblings of the parent module were imported then use symbol
            # and also add an edit to add the appropriate import importing from the same module
            insert_at = types.Position(line_after_import - 1, 0)
            text_edit = types.TextEdit(
                range=types.Range(insert_at, insert_at),
                new_text=f"from {symbol_module} import {symbol}\n",
            )
            edits.append(text_edit)
            return symbol
        case _:
            typing.assert_never(module)


def _log_to_diagnostic(log: Log) -> types.Diagnostic:
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
        # positions are 0-indexed while SourceLocation are 1-indexed
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
