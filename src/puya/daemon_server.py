import os
import signal
import sys
import time
import traceback
import logging
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from pygls.lsp.server import LanguageServer

from puya.log import get_logger
from puya.main import main

# Constants
DEFAULT_DAEMON_DIR = ".puya"
DEFAULT_PID_FILENAME = "daemon.pid"
COMPILATION_SEMAPHORE_VALUE = 10
PROCESS_GRACEFUL_TERMINATE_TIMEOUT = 3

# Import psutil for Windows
if sys.platform == "win32":
    try:
        import psutil
    except ImportError:
        psutil = None

# Configure standard logging to stderr for the daemon
# This ensures JSON responses on stdout don't get mixed with logs
handler = logging.StreamHandler(stream=sys.stderr)
formatter = logging.Formatter('%(levelname)s: %(message)s')
handler.setFormatter(formatter)
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
# Remove existing handlers
for h in root_logger.handlers[:]:
    root_logger.removeHandler(h)
root_logger.addHandler(handler)

# Get logger
logger = get_logger(__name__)


# Daemon utility functions
def get_pid_file_path(pid_file: Optional[Path] = None) -> Path:
    """Get the path to the PID file."""
    if pid_file:
        return pid_file

    default_dir = Path.home() / DEFAULT_DAEMON_DIR
    default_dir.mkdir(parents=True, exist_ok=True)

    return default_dir / DEFAULT_PID_FILENAME


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


def cleanup_zombie_daemon(pid_file: Optional[Path] = None) -> None:
    """Clean up any zombie daemon processes."""
    pid_file_path = get_pid_file_path(pid_file)

    if pid_file_path.exists():
        try:
            with Path(pid_file_path).open("r") as f:
                pid = int(f.read().strip())

            if check_process_running(pid):
                if terminate_process(pid):
                    logger.info(f"Terminated zombie daemon process with PID {pid}.")
                else:
                    logger.info(f"Failed to terminate zombie daemon process with PID {pid}.")

            pid_file_path.unlink()
            logger.info(f"Removed stale PID file at {pid_file_path}.")
        except (OSError, ValueError) as e:
            logger.info(f"Error reading or processing PID file: {e}")
            try:
                pid_file_path.unlink()
            except OSError:
                pass


class PuyaDaemonServer(LanguageServer):
    """
    A daemon server that provides Puya compilation services via JSON-RPC over stdio.
    """
    
    CONFIGURATION_SECTION = "puya"
    
    def __init__(self):
        """Initialize the daemon server."""
        # Fix parameter passing - pass max_workers as a keyword argument to JsonRPCServer
        # The correct initialization based on PyGLS inheritance chain
        super().__init__(
            name="puya", 
            version="v1.0",
            # Don't pass max_workers here - it should be passed via **kwargs
        )
        
        # Set max_workers on the thread_pool after initialization
        self._max_workers = COMPILATION_SEMAPHORE_VALUE
        
        self.start_time = time.time()
        self.shutting_down = False
        self._shutdown_lock = threading.Lock()  # Lock for thread-safe shutdown
        
        # Register RPC methods
        self._register_methods()
        
        # Log initialization
        logger.info("PuyaDaemonServer initialized")

    def _register_methods(self) -> None:
        """Register custom JSON-RPC methods with the server."""

        @self.feature("puya/stop")
        def _stop(params: Optional[Any] = None) -> Dict[str, Any]:
            """Stop the server."""
            logger.info("Received stop request")
            return self.stop(params)

        @self.feature("puya/status")
        @self.thread()  # Run in a thread to avoid blocking
        def _status(params: Optional[Any] = None) -> Dict[str, Any]:
            """Get server status."""
            logger.info("Received status request")
            # The sleep is included in the status method
            return self.status(params)

        @self.feature("puya/compile")
        @self.thread()  # Compilation should run in a thread
        def _compile_awst(params: Dict[str, Any]) -> Dict[str, Any]:
            """Compile Algorand Python code."""
            logger.info("Received compile request")
            return self.compile_awst(params)
        
    def stop(self, params: Optional[Any] = None) -> Dict[str, Any]:
        """Stop the server."""
        try:
            # Schedule shutdown to happen after response is sent
            # Use the built-in thread pool
            self.thread_pool.submit(self.shutdown)
            return {"success": True, "message": "Server stopping"}
        except Exception as e:
            logger.exception("Error handling stop request")
            return {"success": False, "error": str(e)}
        
    def status(self, params: Optional[Any] = None) -> Dict[str, Any]:
        """Get server status."""
        try:
            time.sleep(2)  # Simulate work
            status_info = self.get_status()
            # Add thread information for debugging
            status_info["thread_id"] = threading.get_ident()
            return status_info
        except Exception as e:
            logger.exception("Error handling status request")
            return {"status": "error", "error": str(e)}
        
    def compile_awst(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Compile Algorand Python code."""
        try:
            # Extract parameters
            options_json = params.get("options_json", "")
            if not options_json:
                return {"success": False, "error": "Missing options_json parameter"}
                
            awst_json = params.get("awst_json", "")
            if not awst_json:
                return {"success": False, "error": "Missing awst_json parameter"}
                
            source_annotations_json = params.get("source_annotations_json")
            
            # Log compilation attempt
            logger.info(f"Compiling AWST code (options size: {len(options_json)}, AWST size: {len(awst_json)})")
            
            # Run compilation directly (no need for executor.submit, PyGLS handles it)
            result = self._compile(options_json, awst_json, source_annotations_json)
            
            # Add thread information for debugging
            result["thread_id"] = threading.get_ident()
            
            # Return success result
            return {"success": True, **result}
        except Exception as e:
            # Detailed error logging
            logger.exception("Compilation error")
            error_details = {
                "message": str(e),
                "traceback": traceback.format_exc()
            }
            return {"success": False, "error": str(e), "error_details": error_details}

    def _compile(
        self, options_json: str, awst_json: str, source_annotations_json: Optional[str] = None
    ) -> Dict[str, Any]:
        """Synchronous compilation function."""
        start_time = time.time()
        main(
            options_json=options_json,
            awst_json=awst_json,
            source_annotations_json=source_annotations_json,
        )
        end_time = time.time()
        return {"elapsed_time": end_time - start_time}

    def get_status(self) -> Dict[str, Any]:
        """Return daemon status information."""
        return {
            "status": "running",
            "uptime": time.time() - self.start_time,
            "pid": os.getpid(),
            "worker_count": self._max_workers
        }

    def setup_signal_handlers(self) -> None:
        """Set up graceful shutdown handlers."""
        self._last_signal_time = 0
        self._force_exit_threshold = 1.0  # Seconds
        
        def signal_handler(sig, frame):
            current_time = time.time()
            
            if self.shutting_down:
                # If shutdown is already in progress, check if this is a repeated signal
                if current_time - self._last_signal_time < self._force_exit_threshold:
                    logger.warning("Multiple interrupts detected, forcing immediate exit...")
                    os._exit(1)  # Force exit
                else:
                    logger.info(f"Shutdown already in progress, ignoring signal {sig}...")
                self._last_signal_time = current_time
                return
                
            logger.info(f"Received signal {sig}, shutting down...")
            self._last_signal_time = current_time
            self.shutdown()
            
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            logger.info("Signal handlers set up")
        except (ImportError, NotImplementedError):
            logger.info("Signal handlers not supported on this platform")

    def shutdown(self) -> None:
        """Graceful shutdown sequence."""
        with self._shutdown_lock:
            if self.shutting_down:
                return
                
            self.shutting_down = True
        
        logger.info("Initiating graceful shutdown...")
        
        # Set a timer to force kill if graceful shutdown takes too long
        def force_exit():
            logger.warning("Shutdown taking too long, forcing exit...")
            os._exit(1)  # Hard exit that can't be caught
            
        # Set up a timer to force exit after 5 seconds
        force_timer = threading.Timer(5.0, force_exit)
        force_timer.daemon = True
        force_timer.start()
        
        try:
            # Log that we're shutting down
            logger.info("Shutting down thread pool")
            
            # The super().shutdown() will handle the thread pool
            super().shutdown()
            logger.info("Thread pool shutdown complete")
            
            # Cancel the force exit timer since we've completed normally
            force_timer.cancel()
            
            logger.info("Puya daemon server stopped")
            
            # Exit after a small delay to allow logs to be written
            time.sleep(0.1)
            os._exit(0)  # Use os._exit to ensure we exit even if threads are hanging
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            # Don't cancel the force timer - let it exit for us
        
    def start(self) -> None:
        """Start the daemon server over stdio."""
        self.setup_signal_handlers()
        logger.info("Starting Puya daemon server over stdio")
        
        try:
            # Set up a watchdog to force exit if something goes wrong
            def watchdog():
                # Wait for server to start
                time.sleep(0.5)
                
                while not self.shutting_down:
                    time.sleep(1.0)
                    
                # If we're shutting down, set a timeout to force exit
                time.sleep(5.0)
                if threading.current_thread().is_alive():  # If still running
                    logger.error("Shutdown watchdog triggered - forcing exit")
                    os._exit(1)
                    
            watchdog_thread = threading.Thread(target=watchdog)
            watchdog_thread.daemon = True
            watchdog_thread.start()
            
            # Start the server
            self.start_io()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            self.shutdown()
        except Exception as e:
            logger.exception(f"Error running server: {e}")
            # Force exit on unhandled exceptions
            os._exit(1)
