import argparse
import contextlib
import logging
import sys
import time
from importlib.metadata import version
from pathlib import Path
from typing import Literal, cast

import attrs
from pygls.exceptions import JsonRpcInternalError
from pygls.protocol.json_rpc import JsonRPCProtocol
from pygls.server import JsonRPCServer

from puya.awst.nodes import AWST
from puya.awst.serialize import get_converter
from puya.compile import awst_to_teal
from puya.errors import PuyaExitError, log_exceptions
from puya.log import Log, LogLevel, configure_logging, logging_context
from puya.options import PuyaOptions
from puya.parse import DictSourceProvider

NAME = "puyad"
VERSION = version("puyapy")

# Set up logger
logger = logging.getLogger(__name__)


@attrs.frozen
class AnalyseParams:
    awst: AWST
    compilation_set: dict[str, Path]
    request_id: str | int | None = None


@attrs.frozen
class CancelParams:
    message_id: int | str


@attrs.frozen
class AnalyseResult:
    logs: list[Log]
    cancelled: bool = False


@attrs.frozen(kw_only=True)
class _RPCMessage:
    id: int | str
    jsonrpc: str = attrs.field(default="2.0")


@attrs.frozen(kw_only=True)
class AnalyseRequest(_RPCMessage):
    params: AnalyseParams
    method: Literal["analyse"] = "analyse"


@attrs.frozen(kw_only=True)
class CancelRequest(_RPCMessage):
    params: CancelParams
    method: Literal["cancel"] = "cancel"


@attrs.frozen(kw_only=True)
class AnalyseResponse(_RPCMessage):
    result: AnalyseResult


# Map of method name to (request type, response type)
_TYPES: dict[str, tuple[type | None, type | None]] = {
    "analyse": (AnalyseRequest, AnalyseResponse),
    "cancel": (CancelRequest, None),
}


class PuyaProtocol(JsonRPCProtocol):
    """Custom protocol implementation that adds type support for our methods."""

    def get_message_type(self, method: str) -> type | None:
        return _TYPES.get(method, (None, None))[0]

    def get_result_type(self, method: str) -> type | None:
        return _TYPES.get(method, (None, None))[1]

    def structure_message(self, data: dict[str, object]) -> dict[str, object]:
        """Override the default structure_message to inject request_id into params if needed."""
        if "jsonrpc" not in data:
            return data

        try:
            # If this is an "analyse" request, we need to add the request_id to params
            if (
                "id" in data
                and "method" in data
                and data["method"] == "analyse"
                and "params" in data
                and isinstance(data["params"], dict)
            ):
                data["params"]["request_id"] = data["id"]

            # Call the parent implementation to handle the actual structuring
            return cast(dict[str, object], super().structure_message(data))  # type: ignore[no-untyped-call]

        except Exception as exc:
            logger.exception("Unable to deserialize message")
            raise JsonRpcInternalError(str(exc)) from exc  # type: ignore[no-untyped-call]


class MessageRegistry:
    """Registry for tracking and cancelling long-running operations."""

    def __init__(self) -> None:
        self.active_messages: set[int | str] = set()
        self.cancelled_messages: set[int | str] = set()

    def register(self, message_id: int | str) -> None:
        """Register a message as active and remove it from cancelled if present."""
        self.active_messages.add(message_id)
        self.cancelled_messages.discard(message_id)  # Ensure it's not in cancelled set

    def unregister(self, message_id: int | str) -> None:
        """Remove a message from both active and cancelled sets."""
        self.active_messages.discard(message_id)
        self.cancelled_messages.discard(message_id)

    def cancel(self, message_id: int | str) -> bool:
        """Mark a message for cancellation.

        Returns True if the message was found and marked for cancellation,
        False if the message was not found (already completed or never existed).
        """
        logger.debug(f"Message {message_id}: Attempting to cancel")
        logger.debug(f"Current active messages: {self.active_messages}")
        logger.debug(f"Current cancelled messages: {self.cancelled_messages}")

        # Check if the message exists in the active set
        if message_id in self.active_messages:
            self.cancelled_messages.add(message_id)
            logger.debug(f"Message {message_id}: Marked for cancellation")
            return True
        else:
            logger.debug(f"Message {message_id} not found or already completed")
            return False

    def is_cancelled(self, message_id: int | str) -> bool:
        """Check if a message has been marked for cancellation."""
        return message_id in self.cancelled_messages


def create_server(thread_count: int = 2) -> JsonRPCServer:
    """Create and configure a server with thread pooling."""
    server = JsonRPCServer(PuyaProtocol, get_converter, max_workers=thread_count)

    # Create message registry for tracking and cancellation
    message_registry = MessageRegistry()

    @server.feature("cancel")
    def cancel_task(params: CancelParams) -> bool:
        """Cancel a message by ID."""
        return message_registry.cancel(params.message_id)

    @server.feature("analyse")
    @server.thread()  # Thread decorator is necessary for concurrent handling
    def analyse(params: AnalyseParams) -> AnalyseResult:
        """Analyzes Python code to produce TEAL with cancellation support."""
        message_id = params.request_id or f"msg-{id(params)}"
        logger.debug("Starting analysis: %s", message_id)

        message_registry.register(message_id)
        start_time = time.time()
        options = PuyaOptions(optimization_level=0)
        # Initialize with default error result in case something unexpected happens
        result = AnalyseResult(
            logs=[
                Log(
                    level=LogLevel.error,
                    message="Analysis did not complete properly",
                    location=None,
                )
            ],
            cancelled=False,
        )

        try:
            with (
                logging_context() as log_ctx,
                contextlib.suppress(PuyaExitError),
                log_exceptions(),
            ):
                if message_registry.is_cancelled(message_id):
                    log_ctx.logs.append(
                        Log(
                            level=LogLevel.warning,
                            message="Analysis cancelled before it started",
                            location=None,
                        )
                    )
                    return AnalyseResult(logs=log_ctx.logs, cancelled=True)

                # Create a cancellation check callback
                def check_if_cancelled() -> bool:
                    cancelled = message_registry.is_cancelled(message_id)
                    if cancelled:
                        log_ctx.logs.append(
                            Log(
                                level=LogLevel.warning,
                                message="Analysis cancelled during processing",
                                location=None,
                            )
                        )
                    return cancelled

                # Process the compilation with cancellation support
                awst_to_teal(
                    log_ctx,
                    options,
                    params.compilation_set,  # type: ignore[arg-type]
                    DictSourceProvider({}),
                    params.awst,
                    cancellation_callback=check_if_cancelled,
                )

                # Check if cancelled after compilation
                if check_if_cancelled():
                    result = AnalyseResult(logs=log_ctx.logs, cancelled=True)
                else:
                    elapsed = time.time() - start_time
                    log_ctx.logs.append(
                        Log(
                            level=LogLevel.info,
                            message=f"Analysis completed in {elapsed:.2f}s",
                            location=None,
                        )
                    )
                    result = AnalyseResult(logs=log_ctx.logs, cancelled=False)

        except Exception as e:
            logger.exception("Analysis error")
            return AnalyseResult(
                logs=[Log(level=LogLevel.error, message=f"Error: {e}", location=None)],
                cancelled=message_registry.is_cancelled(message_id),
            )
        finally:
            message_registry.unregister(message_id)

        return result

    return server


def main() -> None:
    """Main entry point for the Puya daemon."""
    parser = argparse.ArgumentParser(
        prog=NAME,
        description=NAME,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s ({VERSION})")
    parser.add_argument("--threads", type=int, default=2, help="Worker thread count")
    args = parser.parse_args()

    # Configure logging to stderr (stdout used for LSP protocol)
    configure_logging(min_log_level=LogLevel.info, file=sys.stderr)

    # Create server with configured thread count
    server = create_server(thread_count=args.threads)

    # Start server (will handle its own cleanup in start_io)
    server.start_io()


if __name__ == "__main__":
    main()
