"""
Daemon server implementation for Puya.

This module provides an asynchronous WebSocket server that implements JSON-RPC
for Puya compilation services.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional, Union, Callable

import websockets
from websockets.server import serve

from puya.log import LogFormat, LogLevel, configure_logging, get_logger
from puya.main import main

logger = get_logger(__name__)


class DaemonServer:
    """
    A daemon server that provides Puya compilation services via JSON-RPC over WebSockets.
    
    The server exposes a simple API with three methods:
    - compile: Compiles Algorand Python code
    - ping: Checks if the server is responsive
    - stop: Gracefully stops the server
    """
    def __init__(self, host: str, port: int, log_level: LogLevel, log_format: LogFormat):
        """
        Initialize the daemon server.
        
        Args:
            host: The host address to bind to
            port: The port to listen on
            log_level: The log level to use
            log_format: The log format to use
        """
        self.host = host
        self.port = port
        self.log_level = log_level
        self.log_format = log_format
        self.stop_event = asyncio.Event()
        self.server = None
        self.compile_semaphore = None
        self.start_time = None
    
    async def send_response(self, websocket, result: Any, request_id: Any) -> None:
        """
        Send a successful JSON-RPC response.
        
        Args:
            websocket: The WebSocket connection
            result: The result to send
            request_id: The request ID
        """
        response = {
            "jsonrpc": "2.0",
            "result": result,
            "id": request_id
        }
        await websocket.send(json.dumps(response))
    
    async def send_error(self, websocket, code: int, message: str, request_id: Any) -> None:
        """
        Send an error JSON-RPC response.
        
        Args:
            websocket: The WebSocket connection
            code: The error code
            message: The error message
            request_id: The request ID
        """
        error_response = {
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            "id": request_id
        }
        await websocket.send(json.dumps(error_response))
        logger.error(f"Error {code}: {message}")

    async def process_request(self, websocket) -> None:
        """
        Process incoming WebSocket requests.
        
        This method handles the JSON-RPC protocol and dispatches requests to
        the appropriate handlers.
        
        Args:
            websocket: The WebSocket connection
        """
        async for message in websocket:
            request = None
            try:
                request = json.loads(message)
                if not isinstance(request, dict):
                    await self.send_error(websocket, -32600, "Invalid Request", None)
                    continue
                
                # Define method handlers
                handlers = {
                    "compile": self.handle_compile,
                    "ping": lambda *args, **kwargs: {"status": "ok"},
                    "stop": lambda *args, **kwargs: self.handle_stop()
                }
                
                method = request.get("method")
                params = request.get("params", {})
                request_id = request.get("id")
                
                if method not in handlers:
                    await self.send_error(websocket, -32601, f"Method '{method}' not found", request_id)
                    continue
                
                # Call the appropriate handler
                if method == "compile":
                    result = await handlers[method](
                        params.get("options_json"),
                        params.get("awst_json"),
                        params.get("source_annotations_json")
                    )
                else:
                    result = handlers[method]()
                
                await self.send_response(websocket, result, request_id)
                
                # If stopping, break the loop after sending response
                if method == "stop":
                    break
                    
            except json.JSONDecodeError:
                await self.send_error(websocket, -32700, "Parse error", None)
            except Exception as e:
                request_id = request.get("id") if isinstance(request, dict) else None
                await self.send_error(websocket, -32603, f"Internal error: {str(e)}", request_id)
                logger.exception("Error processing request")

    def handle_stop(self) -> Dict[str, Any]:
        """
        Handle a stop request.
        
        Returns:
            A success message
        """
        self.stop_event.set()
        return {"success": True, "message": "Server stopping"}
    
    async def handle_compile(
        self, options_json: str, awst_json: str, source_annotations_json: Optional[str]
    ) -> Dict[str, Any]:
        """
        Handle a compile request.
        
        This method runs the compilation in a thread pool to prevent blocking the
        event loop. It also uses a semaphore to prevent multiple compilations from
        running concurrently.
        
        Args:
            options_json: JSON string containing compilation options
            awst_json: JSON string containing the AWST
            source_annotations_json: Optional JSON string containing source annotations
            
        Returns:
            The compilation result
        """
        if not self.compile_semaphore:
            # Lazy initialization of the semaphore
            self.compile_semaphore = asyncio.Semaphore(1)
            
        # Use semaphore to prevent multiple heavy compilations at once
        async with self.compile_semaphore:
            try:
                # Run CPU-intensive compilation in a thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: self._compile(options_json, awst_json, source_annotations_json)
                )
                return {"success": True, **result}
            except Exception as e:
                logger.exception("Compilation error")
                return {"success": False, "error": str(e)}
            
    def _compile(self, options_json: str, awst_json: str, source_annotations_json: Optional[str]) -> Dict[str, Any]:
        """
        Synchronous compilation function to run in thread pool.
        
        Args:
            options_json: JSON string containing compilation options
            awst_json: JSON string containing the AWST
            source_annotations_json: Optional JSON string containing source annotations
            
        Returns:
            Dictionary with compilation results
        """
        start_time = time.time()
        main(
            options_json=options_json,
            awst_json=awst_json,
            source_annotations_json=source_annotations_json,
        )
        end_time = time.time()
        return {"elapsed_time": end_time - start_time}

    def get_status(self) -> Dict[str, Any]:
        """
        Return daemon status information.
        
        Returns:
            Dictionary with status information
        """
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info().rss / (1024 * 1024)
            cpu_percent = process.cpu_percent()
        except ImportError:
            memory_info = None
            cpu_percent = None
            
        return {
            "status": "running",
            "uptime": time.time() - self.start_time if self.start_time else 0,
            "memory_usage_mb": memory_info,
            "cpu_percent": cpu_percent,
        }

    def setup_signal_handlers(self):
        """Set up graceful shutdown handlers."""
        loop = asyncio.get_event_loop()
        
        try:
            import signal
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(
                    sig,
                    lambda: asyncio.create_task(self.shutdown())
                )
            logger.info("Signal handlers set up")
        except (ImportError, NotImplementedError):
            # Windows doesn't support add_signal_handler
            logger.info("Signal handlers not supported on this platform")

    async def shutdown(self):
        """Graceful shutdown sequence."""
        logger.info("Initiating graceful shutdown...")
        
        # Wait for any pending compilation to finish (max 30 seconds)
        if self.compile_semaphore:
            try:
                await asyncio.wait_for(self.compile_semaphore.acquire(), timeout=30)
                self.compile_semaphore.release()
                logger.info("All pending compilations completed")
            except asyncio.TimeoutError:
                logger.warning("Timed out waiting for compilation to complete")
        
        # Signal stop
        self.stop_event.set()

    async def start(self) -> None:
        """
        Start the daemon server.
        
        This method configures logging, sets up signal handlers, starts the WebSocket server,
        and waits for the stop event.
        """
        self.start_time = time.time()
        configure_logging(min_log_level=self.log_level, log_format=self.log_format)
        logger.info(f"Starting Puya daemon server on {self.host}:{self.port}")
        
        # Set up signal handlers for graceful shutdown
        self.setup_signal_handlers()
        
        # Initialize resources
        self.compile_semaphore = asyncio.Semaphore(1)
        
        # Start the server
        self.server = await serve(self.process_request, self.host, self.port)
        logger.info(f"Puya daemon server started on {self.host}:{self.port}")
        
        # Wait for the stop event
        await self.stop_event.wait()
        
        # Clean up
        self.server.close()
        await self.server.wait_closed()
        logger.info("Puya daemon server stopped") 
