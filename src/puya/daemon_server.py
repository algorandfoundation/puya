import asyncio
import json
import os
import signal
import socket
import sys
import time
from pathlib import Path
from typing import Any

import structlog
import websockets
from jsonrpcserver import Error, Result, Success, async_dispatch, method
from websockets.server import serve

from puya.log import get_logger
from puya.main import main

logger = get_logger(__name__)

# Constants
SERVER_STOP_TIMEOUT_ATTEMPTS = 10
SERVER_STOP_CHECK_INTERVAL = 0.5
PROCESS_GRACEFUL_TERMINATE_TIMEOUT = 3
DEFAULT_DAEMON_DIR = ".puya"
DEFAULT_PID_FILENAME = "daemon.pid"
JSON_RPC_VERSION = "2.0"
JSON_RPC_STOP_ID = 1
COMPILATION_SEMAPHORE_VALUE = 5  # at most 5 compilations can run concurrently
SHUTDOWN_COMPILATION_TIMEOUT = 30

# Import psutil for Windows
if sys.platform == "win32":
    try:
        import psutil
    except ImportError:
        psutil = None

# Get structlog logger
logger = structlog.get_logger("puya.daemon")


# Daemon utility functions
def get_pid_file_path(pid_file: Path | None = None) -> Path:
    """Get the path to the PID file."""
    if pid_file:
        return pid_file

    default_dir = Path.home() / DEFAULT_DAEMON_DIR
    default_dir.mkdir(parents=True, exist_ok=True)

    return default_dir / DEFAULT_PID_FILENAME


def check_server_running(host: str, port: int) -> bool:
    """Check if a server is already running on the specified host and port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


async def _send_stop_request(host: str, port: int) -> bool:
    """Send a stop request to the server."""
    uri = f"ws://{host}:{port}"
    try:
        async with websockets.connect(uri) as websocket:
            stop_request = json.dumps(
                {"jsonrpc": JSON_RPC_VERSION, "method": "stop", "id": JSON_RPC_STOP_ID}
            )
            await websocket.send(stop_request)
            await websocket.recv()
            logger.info("Server stopped")
            return True
    except (ConnectionRefusedError, websockets.exceptions.ConnectionClosedError):
        logger.info("Server is not responding.")
        return False


def stop_daemon(host: str, port: int, pid_file: Path | None = None) -> None:
    """Stop the daemon server."""
    if not check_server_running(host, port):
        logger.info("No server is running.")
        cleanup_zombie_daemon(host, port, pid_file)
        return

    try:
        asyncio.run(_send_stop_request(host, port))

        for _ in range(SERVER_STOP_TIMEOUT_ATTEMPTS):
            if not check_server_running(host, port):
                break
            time.sleep(SERVER_STOP_CHECK_INTERVAL)

        if check_server_running(host, port):
            logger.info("Warning: Server did not stop properly.")
        else:
            logger.info("Server stopped successfully.")

        cleanup_zombie_daemon(host, port, pid_file)
    except ImportError:
        logger.info("Error: websockets library not available. Cannot stop daemon.")


def check_process_running(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    if sys.platform == "win32" and psutil is not None:
        return psutil.pid_exists(pid)
    else:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        else:
            return True


def terminate_process(pid: int) -> bool:
    """Terminate a process with the given PID."""
    try:
        if sys.platform == "win32" and psutil is not None:
            process = psutil.Process(pid)
            process.terminate()
            gone, still_alive = psutil.wait_procs(
                [process], timeout=PROCESS_GRACEFUL_TERMINATE_TIMEOUT
            )
            if still_alive:
                process.kill()
        else:
            os.kill(pid, signal.SIGTERM)
    except (OSError, AttributeError) as e:
        logger.warning(f"Error terminating process {pid}: {e}")
        return False
    else:
        return True


def cleanup_zombie_daemon(host: str, port: int, pid_file: Path | None = None) -> None:
    """Clean up any zombie daemon processes."""
    pid_file_path = get_pid_file_path(pid_file)

    if pid_file_path.exists():
        try:
            with Path(pid_file_path).open("r") as f:
                pid = int(f.read().strip())

            if check_process_running(pid) and not check_server_running(host, port):
                if terminate_process(pid):
                    logger.info(f"Terminated zombie daemon process with PID {pid}.")
                else:
                    logger.info(f"Failed to terminate zombie daemon process with PID {pid}.")

            if not check_server_running(host, port):
                pid_file_path.unlink()
                logger.info(f"Removed stale PID file at {pid_file_path}.")
        except (OSError, ValueError) as e:
            logger.info(f"Error reading or processing PID file: {e}")
            pid_file_path.unlink()


class DaemonServer:
    """
    A daemon server that provides Puya compilation services via JSON-RPC over WebSockets.
    """

    def __init__(self, host: str, port: int):
        """Initialize the daemon server."""
        self.host = host
        self.port = port
        self.stop_event = asyncio.Event()
        self.server: websockets.WebSocketServer | None = None
        self.compile_semaphore = asyncio.Semaphore(COMPILATION_SEMAPHORE_VALUE)
        self.start_time: float | None = None

        # Register RPC methods
        self._register_methods()

    def _register_methods(self) -> None:
        """Register JSON-RPC methods with the server."""

        # Define the methods
        @method
        async def ping() -> Result:
            """Check if the server is responsive."""
            return Success({"status": "ok"})

        @method
        async def stop() -> Result:
            """Stop the server."""
            result = self.handle_stop()
            return Success(result)

        @method
        async def status() -> Result:
            """Get server status."""
            result = self.get_status()
            return Success(result)

        @method
        async def compile_awst(
            options_json: str, awst_json: str, source_annotations_json: str | None = None
        ) -> Result:
            """Compile Algorand Python code."""
            result = await self.handle_compile(options_json, awst_json, source_annotations_json)
            return Success(result)

    async def process_request(self, websocket: websockets.WebSocketServerProtocol) -> None:
        """Process incoming WebSocket requests using jsonrpcserver."""
        try:
            async for message in websocket:
                if self.stop_event.is_set():
                    break

                try:
                    response = await async_dispatch(message)
                    if response:
                        await websocket.send(str(response))
                except Exception as e:
                    logger.exception("Error processing request")
                    error_response = Error(-32603, f"Internal error: {e!s}")
                    await websocket.send(str(error_response))
        except websockets.exceptions.ConnectionClosedError:
            logger.info("Connection closed")
        except Exception:
            logger.exception("Unexpected error in websocket handler")

    def handle_stop(self) -> dict[str, Any]:
        """Handle a stop request."""
        logger.info("Received stop request")
        self._shutdown_task = asyncio.create_task(self.shutdown())
        return {"success": True, "message": "Server stopping"}

    async def handle_compile(
        self, options_json: str, awst_json: str, source_annotations_json: str | None
    ) -> dict[str, Any]:
        """Handle a compile request."""
        logger.info("Received compile request")
        async with self.compile_semaphore:
            try:
                # Use ThreadPoolExecutor to run CPU-bound compilation in a separate thread
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None, lambda: self._compile(options_json, awst_json, source_annotations_json)
                )
            except Exception as e:
                logger.exception("Compilation error")
                return {"success": False, "error": str(e)}
            else:
                return {"success": True, **result}

    def _compile(
        self, options_json: str, awst_json: str, source_annotations_json: str | None
    ) -> dict[str, Any]:
        """Synchronous compilation function to run in thread pool."""
        start_time = time.time()
        main(
            options_json=options_json,
            awst_json=awst_json,
            source_annotations_json=source_annotations_json,
        )
        end_time = time.time()
        return {"elapsed_time": end_time - start_time}

    def get_status(self) -> dict[str, Any]:
        """Return daemon status information."""
        return {
            "status": "running",
            "uptime": time.time() - self.start_time if self.start_time else 0,
        }

    def setup_signal_handlers(self) -> None:
        """Set up graceful shutdown handlers."""
        loop = asyncio.get_event_loop()

        try:
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
            logger.info("Signal handlers set up")
        except (ImportError, NotImplementedError):
            logger.info("Signal handlers not supported on this platform")

    async def shutdown(self) -> None:
        """Graceful shutdown sequence."""
        if self.stop_event.is_set():
            return  # Prevent multiple shutdown attempts

        logger.info("Initiating graceful shutdown...")
        self.stop_event.set()

        # Wait for ongoing compilations to complete with timeout
        try:
            if not self.compile_semaphore.locked():
                logger.info("No pending compilations")
            else:
                logger.info("Waiting for pending compilations to complete...")
                await asyncio.wait_for(
                    self.compile_semaphore.acquire(), timeout=SHUTDOWN_COMPILATION_TIMEOUT
                )
                self.compile_semaphore.release()
                logger.info("All pending compilations completed")
        except TimeoutError:
            logger.warning("Timed out waiting for compilation to complete")

        # Close the server
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        logger.info("Puya daemon server stopped")

    async def start(self) -> None:
        """Start the daemon server."""
        self.start_time = time.time()
        logger.info(f"Starting Puya daemon server on {self.host}:{self.port}")

        self.setup_signal_handlers()

        # Start the websocket server
        self.server = await serve(self.process_request, self.host, self.port)
        logger.info(f"Puya daemon server started on {self.host}:{self.port}")

        # Wait for stop event
        await self.stop_event.wait()
