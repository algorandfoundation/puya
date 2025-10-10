import functools
import importlib.metadata
import sys
import threading
import time
import typing
from collections.abc import Mapping

import attrs
from cattrs.preconf.json import make_converter
from lsprotocol import types
from pygls.lsp.server import LanguageServer

from puya import log
from puya.utils import StableSet
from puyapy.lsp.analyse import (
    CodeAnalyser,
    DocumentAnalysis,
)
from puyapy.lsp.log import LogToClient
from puyapy.parse import get_sys_path

logger = log.get_logger(__name__)


URI: typing.TypeAlias = str


@attrs.frozen
class ClientConfiguration:
    """Configuration comes from JSON so uses JSON naming conventions"""

    logLevel: typing.Literal["Debug", "Info", "Warning", "Error"] = "Info"  # noqa: N815
    debounceInterval: float = 0.5  # noqa: N815


def create_server(log_to_client: LogToClient) -> LanguageServer:
    server = LanguageServer("puyapy", version=importlib.metadata.version("puyapy"))
    logger.info(f"{server.name} - {server.version}")
    logger.debug(f"Server location: {__file__}")

    server.feature(types.INITIALIZE)(functools.partial(_initialize_language_server, log_to_client))
    return server


def _initialize_language_server(
    log_to_client: LogToClient, ls: LanguageServer, init_params: types.InitializeParams
) -> None:
    # only set language server once protocol is up and running
    log_to_client.server = ls
    logger.debug("initializing server")
    options = init_params.initialization_options or {}
    python_executable = options.get("pythonExecutable")
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
        analyser=CodeAnalyser(
            workspace=ls.workspace,
            package_search_paths=search_paths,
        ),
    )

    converter = make_converter(detailed_validation=False)

    @ls.feature(types.WORKSPACE_DID_CHANGE_CONFIGURATION)
    def did_change_configuration(
        _ls: LanguageServer, params: types.DidChangeConfigurationParams
    ) -> None:
        if params.settings is not None:
            config = converter.structure(params.settings, ClientConfiguration)
            log_to_client.log_level = types.MessageType[config.logLevel]
            puyapy_ls.debounce_interval = config.debounceInterval
        logger.debug(f"did_change_configuration: {params.settings}")

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


@attrs.define
class PuyaPyLanguageServer:
    _ls: LanguageServer
    _analyser: CodeAnalyser
    _analysis: dict[URI, DocumentAnalysis] = attrs.field(factory=dict, init=False)
    _changed_uris: StableSet[URI] = attrs.field(factory=StableSet, init=False)
    _work_available: threading.Event = attrs.field(factory=threading.Event, init=False)
    _analysis_lock: threading.Lock = attrs.field(factory=threading.Lock, init=False)
    _last_trigger: float = attrs.field(default=0.0, init=False)
    _analysis_thread: threading.Thread = attrs.field(init=False)
    debounce_interval: float = 0.5

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
            logger.info(f"analysis took {duration:.2f}s")
            self._analysis.update(analysis)
            self._publish_diagnostics(analysis)

    def _time_to_wait_for_debounce(self) -> float:
        return self._last_trigger + self.debounce_interval - time.time()

    def _publish_diagnostics(self, uris: Mapping[URI, DocumentAnalysis]) -> None:
        for uri, analysis in uris.items():
            version = analysis.version
            diagnostics = analysis.diagnostics

            logger.info(f"publish {len(diagnostics)} diagnostics for {uri=}, {version=}")
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
