"""
Client module for interacting with the Puya daemon server.

This module provides a client interface for sending compilation requests to a running Puya daemon.
The daemon must be started separately using the --daemon flag.

Client functions generally have both asynchronous and synchronous versions, with the synchronous
versions using asyncio.run() internally.
"""

import asyncio
import json
import socket
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, Union, List

import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatusCode

from puya.log import get_logger

logger = get_logger(__name__)


class PuyaDaemonClient:
    """Client for interacting with the Puya daemon server."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        """
        Initialize the client with server connection details.
        
        Args:
            host: The host address of the daemon server
            port: The port number of the daemon server
        """
        self.host = host
        self.port = port
        self.uri = f"ws://{host}:{port}"
    
    async def _send_request(self, method: str, params: Dict[str, Any] = None, request_id: int = 1) -> Dict[str, Any]:
        """
        Send a JSON-RPC request to the daemon server.
        
        Args:
            method: The method name to call
            params: The parameters for the method (default: {})
            request_id: The request ID (default: 1)
            
        Returns:
            The JSON-RPC response
            
        Raises:
            ConnectionError: If the daemon is not running
            RuntimeError: If the server returns an error
            TimeoutError: If the request times out
        """
        params = params or {}
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id
        }
        
        try:
            async with websockets.connect(self.uri, open_timeout=5, close_timeout=5) as websocket:
                await websocket.send(json.dumps(request))
                response_text = await asyncio.wait_for(websocket.recv(), timeout=60)  # 60s timeout for compilation
                response = json.loads(response_text)
                
                if "error" in response:
                    error = response["error"]
                    raise RuntimeError(f"Server error: {error.get('message', 'Unknown error')}")
                
                return response.get("result", {})
        except (websockets.exceptions.ConnectionError, socket.gaierror) as e:
            logger.error(f"Connection error: {e}")
            raise ConnectionError(f"Cannot connect to Puya daemon at {self.uri}. Is the daemon running?")
        except ConnectionClosed as e:
            logger.error(f"Connection closed: {e}")
            raise ConnectionError(f"Connection to daemon at {self.uri} was closed unexpectedly")
        except InvalidStatusCode as e:
            logger.error(f"Invalid status code: {e}")
            raise ConnectionError(f"Invalid response from daemon at {self.uri}")
        except asyncio.TimeoutError:
            logger.error("Request timed out")
            raise TimeoutError(f"Request to daemon at {self.uri} timed out")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            raise RuntimeError(f"Invalid JSON response from daemon at {self.uri}")
        except Exception as e:
            logger.exception("Unexpected error")
            raise RuntimeError(f"Unexpected error: {e}")
    
    def is_running(self) -> bool:
        """
        Check if the daemon server is running.
        
        Returns:
            True if the server is running, False otherwise
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex((self.host, self.port))
                return result == 0
        except Exception as e:
            logger.error(f"Error checking if daemon is running: {e}")
            return False
    
    async def ping(self) -> Dict[str, Any]:
        """
        Ping the daemon server to check if it's responsive.
        
        Returns:
            The server response (e.g., {"status": "ok"})
            
        Raises:
            ConnectionError: If the daemon is not running
        """
        return await self._send_request("ping")
    
    async def compile(
        self, 
        options_json: str, 
        awst_json: str, 
        source_annotations_json: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a compilation request to the daemon.
        
        Args:
            options_json: JSON string containing compilation options
            awst_json: JSON string containing the AWST
            source_annotations_json: Optional JSON string containing source annotations
            
        Returns:
            The compilation result
            
        Raises:
            ConnectionError: If the daemon is not running
            RuntimeError: If compilation fails
            TimeoutError: If the compilation times out
        """
        params = {
            "options_json": options_json,
            "awst_json": awst_json,
        }
        if source_annotations_json is not None:
            params["source_annotations_json"] = source_annotations_json
            
        return await self._send_request("compile", params)
    
    async def stop_server(self) -> Dict[str, Any]:
        """
        Send a stop request to the daemon server.
        
        Returns:
            The server response
            
        Raises:
            ConnectionError: If the daemon is not running
        """
        return await self._send_request("stop")
    
    def compile_sync(
        self, 
        options_json: str, 
        awst_json: str, 
        source_annotations_json: Optional[str] = None,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        Synchronous version of compile.
        
        Args:
            options_json: JSON string containing compilation options
            awst_json: JSON string containing the AWST
            source_annotations_json: Optional JSON string containing source annotations
            timeout: Timeout in seconds for the request (default: 60)
            
        Returns:
            The compilation result
            
        Raises:
            ConnectionError: If the daemon is not running
            RuntimeError: If compilation fails
            TimeoutError: If the compilation times out
        """
        try:
            return asyncio.run(asyncio.wait_for(
                self.compile(options_json, awst_json, source_annotations_json),
                timeout=timeout
            ))
        except asyncio.TimeoutError:
            raise TimeoutError(f"Compilation timed out after {timeout} seconds")
    
    def stop_server_sync(self, timeout: int = 5) -> Dict[str, Any]:
        """
        Synchronous version of stop_server.
        
        Args:
            timeout: Timeout in seconds for the request (default: 5)
            
        Returns:
            The server response
            
        Raises:
            ConnectionError: If the daemon is not running
            TimeoutError: If the request times out
        """
        try:
            return asyncio.run(asyncio.wait_for(self.stop_server(), timeout=timeout))
        except asyncio.TimeoutError:
            raise TimeoutError(f"Stop request timed out after {timeout} seconds")
    
    def ping_sync(self, timeout: int = 2) -> Dict[str, Any]:
        """
        Synchronous version of ping.
        
        Args:
            timeout: Timeout in seconds for the request (default: 2)
            
        Returns:
            The server response
            
        Raises:
            ConnectionError: If the daemon is not running
            TimeoutError: If the request times out
        """
        try:
            return asyncio.run(asyncio.wait_for(self.ping(), timeout=timeout))
        except asyncio.TimeoutError:
            raise TimeoutError(f"Ping request timed out after {timeout} seconds")


def compile_with_daemon(
    options_json: str,
    awst_json: str,
    source_annotations_json: Optional[str] = None,
    host: str = "127.0.0.1",
    port: int = 8765,
    timeout: int = 60
) -> Dict[str, Any]:
    """
    Convenience function to compile using a daemon server.
    
    This function attempts to compile using a running daemon server.
    If no daemon is running, it raises a ConnectionError.
    
    Args:
        options_json: JSON string containing compilation options
        awst_json: JSON string containing the AWST
        source_annotations_json: Optional JSON string containing source annotations
        host: The host address of the daemon server (default: 127.0.0.1)
        port: The port number of the daemon server (default: 8765)
        timeout: Timeout in seconds for the compilation (default: 60)
        
    Returns:
        The compilation result
        
    Raises:
        ConnectionError: If the daemon is not running
        RuntimeError: If compilation fails
        TimeoutError: If the compilation times out
    """
    client = PuyaDaemonClient(host, port)
    return client.compile_sync(options_json, awst_json, source_annotations_json, timeout=timeout)


def ensure_daemon_running(
    host: str = "127.0.0.1", 
    port: int = 8765,
    log_level: str = "info",
    log_format: str = "default",
    pid_file: Optional[Union[str, Path]] = None,
    auto_start: bool = True,
    timeout: int = 10
) -> bool:
    """
    Ensure a daemon server is running, starting one if needed.
    
    Args:
        host: The host address for the daemon server (default: 127.0.0.1)
        port: The port number for the daemon server (default: 8765)
        log_level: The log level for the daemon (default: "info")
        log_format: The log format for the daemon (default: "default")
        pid_file: Optional path to the PID file
        auto_start: Whether to automatically start the daemon if it's not running (default: True)
        timeout: Timeout in seconds to wait for the daemon to start (default: 10)
        
    Returns:
        True if a daemon is now running (either it was already running or was started), 
        False if it couldn't be started
    """
    client = PuyaDaemonClient(host, port)
    
    # Check if daemon is already running
    if client.is_running():
        try:
            # Verify it's responsive
            client.ping_sync(timeout=2)
            logger.info(f"Daemon already running at {host}:{port}")
            return True
        except Exception as e:
            logger.warning(f"Daemon at {host}:{port} is not responsive: {e}")
            if not auto_start:
                return False
            # Continue to start a new daemon
    elif not auto_start:
        logger.info(f"Daemon not running at {host}:{port} and auto_start is False")
        return False
    
    # Try to start a new daemon
    logger.info(f"Starting daemon at {host}:{port}")
    
    # Import here to avoid circular imports
    from puya.daemon_utils import start_daemon_process, cleanup_zombie_daemon
    
    # First clean up any zombie daemon
    cleanup_zombie_daemon(host, port, pid_file)
    
    # Then start a new daemon
    success, error_msg, pid = start_daemon_process(
        host=host,
        port=port,
        log_level=log_level,
        log_format=log_format,
        pid_file=Path(pid_file) if pid_file else None,
        timeout=timeout
    )
    
    if success:
        logger.info(f"Started daemon at {host}:{port} with PID {pid}")
        return True
    else:
        logger.error(f"Failed to start daemon: {error_msg}")
        return False 
