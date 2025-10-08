import importlib.metadata
import sys
import threading
import time
import typing
from collections.abc import Mapping

import attrs
from lsprotocol import types
from pygls.lsp.server import LanguageServer

from puya.log import get_logger
from puya.utils import StableSet
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
        logger.debug("no python executable provided, using current executable")
        python_executable = sys.executable
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
        logger.debug(f"found {len(analysis.actions)} actions for {document_uri}")

        return [
            action
            for action_range, action in analysis.actions
            if _range_overlaps(action_range, range_)
        ]

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
            diagnostics = analysis.diagnostics

            logger.debug(f"Publish {len(diagnostics)} diagnostics for {uri=}, {version=}")
            self._ls.text_document_publish_diagnostics(
                types.PublishDiagnosticsParams(
                    uri=uri,
                    version=version,
                    diagnostics=diagnostics,
                )
            )


def _range_overlaps(a: types.Range, b: types.Range) -> bool:
    if a.end < b.start:
        return False
    return a.start <= b.end
