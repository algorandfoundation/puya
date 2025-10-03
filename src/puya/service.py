import contextlib
import typing
from collections.abc import Mapping, Sequence
from pathlib import Path

import attrs
from immutabledict import immutabledict
from pygls.protocol.json_rpc import JsonRPCProtocol
from pygls.server import JsonRPCServer

from puya.awst import nodes as awst_nodes
from puya.awst.serialize import get_converter
from puya.compile import awst_to_teal
from puya.errors import PuyaExitError, log_exceptions
from puya.log import Log, LogLevel, get_logger, logging_context
from puya.main import PuyaOptionsWithCompilationSet, match_compilation_set
from puya.options import PuyaOptions
from puya.utils import pushd

logger = get_logger(__name__)


def start_puya_service() -> None:
    logger.info("Starting puya server, Ctrl+C and Enter to exit...")
    puya_server = create_server(max_workers=1)
    puya_server.start_io()


@attrs.frozen
class AnalyseParams:
    awst: awst_nodes.AWST


@attrs.frozen
class AnalyseResult:
    logs: list[Log]


@attrs.frozen
class CompileParams:
    awst: awst_nodes.AWST
    options: PuyaOptionsWithCompilationSet
    """compilation options"""
    base_path: Path
    """base path to use when making paths relative"""
    log_level: LogLevel = LogLevel.info
    """logs at and above this level will be in the response"""
    source_annotations: Mapping[Path, Sequence[str] | None] = immutabledict()
    """absolute paths mapped to their source lines"""


@attrs.frozen
class CompileResult:
    logs: list[Log]


@attrs.frozen(kw_only=True)
class AnyRequest:
    id: int | str
    method: str
    # leave the request params as untyped, so we can defer deserialization (and thus validation)
    # until we're inside a "feature" handler, so that there is a logging context for error capture
    params: typing.Any
    jsonrpc: str = attrs.field(default="2.0")


@attrs.frozen(kw_only=True)
class Response[T]:
    id: int | str
    result: T
    jsonrpc: str = attrs.field(default="2.0")


# Map of method name to (request type, response type)
_REQUEST_TYPES: dict[str, tuple[type | None, type | None]] = {
    "analyse": (AnyRequest, Response[AnalyseResult]),
    "compile": (AnyRequest, Response[CompileResult]),
}


class PuyaProtocol(JsonRPCProtocol):
    """Custom protocol implementation that adds type support for our methods."""

    def get_message_type(self, method: str) -> type | None:
        try:
            return _REQUEST_TYPES[method][0]
        except KeyError:
            return None

    def get_result_type(self, method: str) -> type | None:
        try:
            return _REQUEST_TYPES[method][1]
        except KeyError:
            return None


def create_server(max_workers: int | None) -> JsonRPCServer:
    converter = get_converter()
    server = JsonRPCServer(PuyaProtocol, get_converter, max_workers=max_workers)

    @server.feature("shutdown")
    def shutdown(ls: JsonRPCServer, _params: object) -> None:
        ls.shutdown()

    @server.feature("analyse")
    def analyse(params: typing.Any) -> AnalyseResult:  # noqa: ANN401
        options = PuyaOptions(
            # options chosen to make analysis as fast as possible
            optimization_level=0,
            debug_level=0,
            optimizations_override={
                "perform_subroutine_inlining": False,
                "merge_chained_aggregate_reads": True,
                "replace_aggregate_box_ops": True,
            },
        )

        # path is not required for analysis, as nothing is output
        # and all results are returned with absolute paths
        dummy_path = Path.cwd()
        with (
            logging_context() as log_ctx,
            contextlib.suppress(PuyaExitError),
            log_exceptions(),
            pushd(dummy_path),
        ):
            request = converter.structure(params, AnalyseParams)
            awst = request.awst
            compilation_set = {
                a.id: dummy_path
                for a in awst
                if isinstance(a, awst_nodes.Contract | awst_nodes.LogicSignature)
            }
            awst_to_teal(
                log_ctx,
                options,
                compilation_set,
                {},
                awst,
            )

        result = AnalyseResult(
            logs=[log for log in log_ctx.logs if log.level >= LogLevel.info],
        )
        return result

    @server.feature("compile")
    def compile_(params: typing.Any) -> CompileResult:  # noqa: ANN401
        log_level = LogLevel.info
        with (
            logging_context() as log_ctx,
            contextlib.suppress(PuyaExitError),
            log_exceptions(),
        ):
            request = converter.structure(params, CompileParams)

            log_level = request.log_level
            with pushd(request.base_path):
                awst = request.awst
                options = request.options
                compilation_set = match_compilation_set(options.compilation_set, awst)
                # Process the compilation
                awst_to_teal(
                    log_ctx,
                    options,
                    compilation_set,
                    request.source_annotations,
                    awst,
                )

        result = CompileResult(logs=[log for log in log_ctx.logs if log.level >= log_level])
        return result

    return server
