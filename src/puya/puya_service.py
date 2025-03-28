import contextlib
import logging
import os
import signal
import sys
import time
import types
import typing
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path

import attrs
from pygls.protocol.json_rpc import JsonRPCProtocol
from pygls.server import JsonRPCServer

from puya.awst.nodes import AWST
from puya.awst.serialize import get_converter
from puya.compile import awst_to_teal
from puya.errors import PuyaExitError, log_exceptions
from puya.log import Log, LogLevel, logging_context
from puya.options import PuyaOptions
from puya.parse import DictSourceProvider

NAME = "puyad"
VERSION = version("puyapy")

# Set up logger
logger = logging.getLogger(__name__)


@attrs.frozen
class AnalyseParams:
    """Parameters for the analyse method."""

    awst: AWST
    compilation_set: dict[str, Path]


@attrs.frozen
class AnalyseResult:
    """Result of the analyse method."""

    logs: list[Log]


@attrs.frozen(kw_only=True)
class _RPCMessage:
    """Base RPC message structure."""

    id: int | str
    jsonrpc: str = attrs.field(default="2.0")


@attrs.frozen(kw_only=True)
class AnalyseRequest(_RPCMessage):
    """RPC request for analysis."""

    params: AnalyseParams
    method: typing.Literal["analyse"] = "analyse"


@attrs.frozen(kw_only=True)
class AnalyseResponse(_RPCMessage):
    """RPC response with analysis results."""

    result: AnalyseResult


# Map of method name to (request type, response type)
_TYPES: dict[str, tuple[type | None, type | None]] = {
    "analyse": (AnalyseRequest, AnalyseResponse),
}


class PuyaProtocol(JsonRPCProtocol):
    """Custom protocol implementation that adds type support for our methods."""

    def get_message_type(self, method: str) -> type | None:
        return _TYPES.get(method, (None, None))[0]

    def get_result_type(self, method: str) -> type | None:
        return _TYPES.get(method, (None, None))[1]


class PuyaServer(JsonRPCServer):
    """Extended JsonRPCServer with proper signal handling."""

    def __init__(
        self,
        protocol_cls: type[JsonRPCProtocol] = PuyaProtocol,
        converter_func: Callable[..., typing.Any] = get_converter,
        **kwargs: typing.Any,
    ) -> None:
        super().__init__(protocol_cls, converter_func, **kwargs)
        self._exit_handler_installed = False

    def install_signal_handlers(self) -> None:
        """Install signal handlers for clean shutdown."""
        if self._exit_handler_installed:
            return

        def handle_exit(sig: int, _frame: types.FrameType | None) -> typing.NoReturn:
            logger.info(f"Received signal {sig}, shutting down...")
            # Ensure all logging is flushed
            sys.stdout.flush()
            sys.stderr.flush()
            logging.shutdown()

            # Terminate the process
            os._exit(0)

        signal.signal(signal.SIGINT, handle_exit)
        signal.signal(signal.SIGTERM, handle_exit)
        self._exit_handler_installed = True

    def start_io(
        self,
        stdin: typing.BinaryIO | None = None,
        stdout: typing.BinaryIO | None = None,
    ) -> None:
        """Start the server with proper signal handling."""
        self.install_signal_handlers()
        logger.info(f"{NAME} server started (version {VERSION})")
        super().start_io(stdin, stdout)


def create_server(thread_count: int = 2) -> PuyaServer:
    """Create and configure a server with thread pooling."""
    server = PuyaServer(max_workers=thread_count)

    @server.feature("analyse")
    @server.thread()  # Thread decorator is necessary for concurrent handling
    def analyse(params: AnalyseParams) -> AnalyseResult:
        """Analyzes Python code to produce TEAL."""
        message_id = id(params)
        logger.debug(f"Starting analysis: {message_id}")

        start_time = time.time()
        options = PuyaOptions(optimization_level=0)

        # Initialize with default error result
        result = AnalyseResult(
            logs=[
                Log(
                    level=LogLevel.error,
                    message="Analysis did not complete properly",
                    location=None,
                )
            ],
        )

        with (
            logging_context() as log_ctx,
            contextlib.suppress(PuyaExitError),
            log_exceptions(),
        ):
            # Process the compilation
            awst_to_teal(
                log_ctx,
                options,
                params.compilation_set,  # type: ignore[arg-type]
                DictSourceProvider({}),
                params.awst,
            )

            elapsed = time.time() - start_time
            log_ctx.logs.append(
                Log(
                    level=LogLevel.info,
                    message=f"Analysis completed in {elapsed:.2f}s",
                    location=None,
                )
            )
            result = AnalyseResult(logs=log_ctx.logs)

        return result

    return server
