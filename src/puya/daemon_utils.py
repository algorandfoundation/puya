"""
Utility functions for managing and interacting with the Puya daemon.

This module provides functions for checking daemon health, starting/stopping
daemons, and other utility operations.
"""

import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, Union, Tuple, List

from puya.log import LogLevel, LogFormat, get_logger

logger = get_logger(__name__)


def get_pid_file_path(pid_file: Optional[Path] = None) -> Path:
    """
    Get the path to the PID file, creating directories if needed.
    
    Args:
        pid_file: Optional custom path to the PID file
        
    Returns:
        Path to the PID file
    """
    if pid_file:
        pid_file_path = pid_file
    else:
        # Default location based on user's home directory
        home_dir = Path.home()
        config_dir = home_dir / ".puya"
        config_dir.mkdir(exist_ok=True)
        pid_file_path = config_dir / "daemon.pid"
    
    # Ensure parent directory exists
    pid_file_path.parent.mkdir(exist_ok=True, parents=True)
    return pid_file_path


def is_pid_running(pid: int) -> bool:
    """
    Check if a process with the given PID is running.
    
    Args:
        pid: Process ID to check
        
    Returns:
        True if the process is running, False otherwise
    """
    try:
        if sys.platform == 'win32':
            # On Windows, check using tasklist
            output = subprocess.check_output(['tasklist', '/FI', f'PID eq {pid}', '/NH'])
            return str(pid) in output.decode()
        else:
            # On Unix-like systems, check by sending signal 0
            os.kill(pid, 0)
            return True
    except (subprocess.CalledProcessError, OSError, ProcessLookupError):
        return False


def check_server_running(host: str, port: int) -> bool:
    """
    Check if a server is already running on the specified host and port.
    
    Args:
        host: The host address to check
        port: The port to check
        
    Returns:
        True if a server is running on the specified host and port
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return result == 0
    except Exception as e:
        logger.error(f"Error checking if server is running: {e}")
        return False


def check_daemon_health(
    host: str = "127.0.0.1", 
    port: int = 8765,
    pid_file: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Check the health of the daemon.
    
    This function checks if:
    1. The PID file exists and contains a valid PID
    2. A process with that PID is running
    3. The daemon is listening on the specified host/port
    4. The daemon responds to ping requests
    
    Args:
        host: The host address of the daemon
        port: The port number of the daemon
        pid_file: Path to the PID file (None for default location)
        
    Returns:
        A dictionary with health check information
    """
    result = {
        "pid_file_exists": False,
        "pid_running": False,
        "port_open": False,
        "responsive": False,
        "pid": None,
    }
    
    # Check PID file
    pid_file_path = pid_file or get_pid_file_path()
    if pid_file_path.exists():
        result["pid_file_exists"] = True
        try:
            pid = int(pid_file_path.read_text().strip())
            result["pid"] = pid
            result["pid_running"] = is_pid_running(pid)
        except (ValueError, OSError) as e:
            logger.warning(f"Error reading PID file: {e}")
            result["pid_running"] = False
    
    # Check if port is open
    result["port_open"] = check_server_running(host, port)
    
    # Check if daemon is responsive
    if result["port_open"]:
        try:
            # Import here to avoid circular imports
            from puya.daemon_client import PuyaDaemonClient
            client = PuyaDaemonClient(host, port)
            client.ping_sync()
            result["responsive"] = True
        except Exception as e:
            logger.warning(f"Daemon not responsive: {e}")
            result["responsive"] = False
    
    return result


async def _send_json_rpc_request(host: str, port: int, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Send a JSON-RPC request to the daemon.
    
    Args:
        host: The host address of the daemon
        port: The port number of the daemon
        method: The method to call
        params: The parameters to pass to the method
        
    Returns:
        The response from the daemon
    
    Raises:
        ConnectionError: If the daemon is not running or not responsive
    """
    import websockets
    
    params = params or {}
    try:
        async with websockets.connect(f"ws://{host}:{port}") as websocket:
            await websocket.send(json.dumps({
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": 1
            }))
            response_text = await websocket.recv()
            response = json.loads(response_text)
            
            if "error" in response:
                error = response["error"]
                raise RuntimeError(f"Error {error.get('code')}: {error.get('message')}")
                
            return response.get("result", {})
    except (websockets.exceptions.ConnectionError, socket.gaierror) as e:
        raise ConnectionError(f"Cannot connect to daemon at {host}:{port}: {e}")


def stop_daemon(host: str, port: int, pid_file: Optional[Path] = None) -> None:
    """
    Send a stop command to the daemon server and clean up the PID file.
    
    Args:
        host: The host address of the daemon
        port: The port number of the daemon
        pid_file: Path to the PID file (None for default location)
    """
    pid_file_path = get_pid_file_path(pid_file)
    
    # Check if server is running
    if not check_server_running(host, port):
        print("No Puya daemon appears to be running")
        if pid_file_path.exists():
            pid_file_path.unlink()
        return
    
    # Try to send stop command via websocket
    async def stop_request():
        try:
            result = await _send_json_rpc_request(host, port, "stop")
            print(f"Daemon stopping: {result.get('message', 'OK')}")
        except Exception as e:
            print(f"Error stopping daemon: {e}")
            # If stopping via JSON-RPC fails, try to terminate forcefully
            force_terminate(host, port, pid_file)
    
    asyncio.run(stop_request())
    
    # Wait for the daemon to actually stop
    for _ in range(10):  # Wait up to 5 seconds
        if not check_server_running(host, port):
            break
        time.sleep(0.5)
    
    # Clean up PID file if it exists
    if pid_file_path.exists():
        pid_file_path.unlink()
    
    print("Puya daemon stopped")


def force_terminate(host: str, port: int, pid_file: Optional[Path] = None) -> None:
    """
    Forcefully terminate the daemon process.
    
    Args:
        host: The host address of the daemon
        port: The port number of the daemon
        pid_file: Path to the PID file (None for default location)
    """
    health = check_daemon_health(host, port, pid_file)
    pid = health["pid"]
    
    if pid and is_pid_running(pid):
        print(f"Forcefully terminating daemon process with PID {pid}")
        try:
            if sys.platform == 'win32':
                subprocess.call(['taskkill', '/F', '/PID', str(pid)])
            else:
                os.kill(pid, 9)  # SIGKILL
            return
        except OSError as e:
            print(f"Error killing process: {e}")
    
    # If we can't kill by PID, try to find process listening on port
    try:
        if sys.platform == 'win32':
            output = subprocess.check_output(['netstat', '-ano'], universal_newlines=True)
            for line in output.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    if len(parts) > 4:
                        try:
                            pid = int(parts[-1])
                            subprocess.call(['taskkill', '/F', '/PID', str(pid)])
                            return
                        except (ValueError, subprocess.CalledProcessError) as e:
                            print(f"Error killing process: {e}")
        else:
            # On Unix-like systems
            try:
                output = subprocess.check_output(['lsof', '-i', f':{port}'], universal_newlines=True)
                for line in output.splitlines()[1:]:  # Skip header
                    parts = line.strip().split()
                    if len(parts) > 1:
                        try:
                            pid = int(parts[1])
                            os.kill(pid, 9)  # SIGKILL
                            return
                        except (ValueError, OSError) as e:
                            print(f"Error killing process: {e}")
            except subprocess.CalledProcessError:
                # lsof command failed - port might not be open
                pass
    except Exception as e:
        print(f"Error forcefully terminating daemon: {e}")


def cleanup_zombie_daemon(
    host: str = "127.0.0.1",
    port: int = 8765,
    pid_file: Optional[Path] = None
) -> bool:
    """
    Clean up a zombie daemon process.
    
    This function checks if:
    1. There is a PID file but the process is not running
    2. The port is open but the daemon is not responsive
    
    Args:
        host: The host address of the daemon
        port: The port number of the daemon
        pid_file: Path to the PID file (None for default location)
        
    Returns:
        True if cleanup was needed and successful, False otherwise
    """
    health = check_daemon_health(host, port, pid_file)
    pid_file_path = pid_file or get_pid_file_path()
    
    # If PID file exists but process is not running, clean up PID file
    if health["pid_file_exists"] and not health["pid_running"]:
        try:
            pid_file_path.unlink(missing_ok=True)
            logger.info("Cleaned up stale PID file")
        except Exception as e:
            logger.error(f"Error cleaning up PID file: {e}")
    
    # If port is open but daemon is not responsive, try to kill the process
    if health["port_open"] and not health["responsive"]:
        logger.info("Found zombie daemon process, attempting to terminate")
        force_terminate(host, port, pid_file)
        
        # Check if it worked
        time.sleep(1)
        if not check_server_running(host, port):
            logger.info("Successfully terminated zombie daemon")
            return True
        else:
            logger.warning("Failed to terminate zombie daemon")
    
    return False


def start_daemon_process(
    host: str = "127.0.0.1",
    port: int = 8765,
    log_level: Union[str, LogLevel] = LogLevel.info,
    log_format: Union[str, LogFormat] = LogFormat.default,
    pid_file: Optional[Path] = None,
    timeout: int = 5,
) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Start a daemon process.
    
    Args:
        host: Host address for the daemon to listen on
        port: Port for the daemon to listen on
        log_level: Log level for the daemon
        log_format: Log format for the daemon
        pid_file: Path to PID file (None for default location)
        timeout: Timeout in seconds to wait for daemon to start
        
    Returns:
        Tuple of (success, error_message, pid)
    """
    # Check if daemon is already running
    health = check_daemon_health(host, port, pid_file)
    if health["port_open"] and health["responsive"]:
        return True, "Daemon already running", health["pid"]
    
    # Clean up any zombie daemon
    cleanup_zombie_daemon(host, port, pid_file)
    
    # Prepare command
    cmd = [sys.executable, "-m", "puya", "--daemon", f"--host={host}", f"--port={port}"]
    
    if log_level:
        if isinstance(log_level, LogLevel):
            cmd.append(f"--log-level={log_level.name}")
        else:
            cmd.append(f"--log-level={log_level}")
            
    if log_format:
        if isinstance(log_format, LogFormat):
            cmd.append(f"--log-format={log_format.name}")
        else:
            cmd.append(f"--log-format={log_format}")
    
    if pid_file:
        cmd.append(f"--pid-file={pid_file}")
    
    # Start daemon
    try:
        logger.info(f"Starting daemon with command: {' '.join(cmd)}")
        
        if sys.platform == 'win32':
            # On Windows, use CREATE_NO_WINDOW flag to hide console window
            from subprocess import CREATE_NO_WINDOW
            process = subprocess.Popen(cmd, creationflags=CREATE_NO_WINDOW)
        else:
            # On Unix-like systems, start in background
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                start_new_session=True
            )
        
        # Wait for the daemon to start
        pid = process.pid
        logger.info(f"Started daemon process with PID {pid}")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(0.5)
            health = check_daemon_health(host, port, pid_file)
            if health["port_open"] and health["responsive"]:
                logger.info("Daemon is now responsive")
                return True, None, pid
        
        # Timed out waiting for daemon to start
        logger.error(f"Timed out waiting for daemon to start after {timeout}s")
        force_terminate(host, port, pid_file)  # Clean up the process
        return False, f"Timed out waiting for daemon to start after {timeout}s", pid
    except Exception as e:
        logger.exception("Error starting daemon")
        return False, str(e), None


def terminate_daemon(
    host: str = "127.0.0.1",
    port: int = 8765,
    pid_file: Optional[Path] = None,
    force: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Terminate a running daemon.
    
    Args:
        host: The host address of the daemon
        port: The port number of the daemon
        pid_file: Path to the PID file (None for default location)
        force: Whether to forcefully terminate the daemon if graceful shutdown fails
        
    Returns:
        Tuple of (success, error_message)
    """
    health = check_daemon_health(host, port, pid_file)
    pid_file_path = pid_file or get_pid_file_path()
    
    # If daemon is not running, just clean up PID file
    if not health["port_open"] or not health["responsive"]:
        pid_file_path.unlink(missing_ok=True)
        if health["pid"] and health["pid_running"]:
            # PID is running but not responsive, forcefully terminate
            force_terminate(host, port, pid_file)
        return True, "Daemon was not running"
    
    # Try graceful shutdown first
    try:
        # Use _send_json_rpc_request to avoid circular imports
        async def stop_request():
            return await _send_json_rpc_request(host, port, "stop")
            
        asyncio.run(stop_request())
        
        # Wait for daemon to stop
        for i in range(10):  # Try for 5 seconds
            time.sleep(0.5)
            if not check_server_running(host, port):
                # Daemon stopped successfully
                pid_file_path.unlink(missing_ok=True)
                return True, "Daemon stopped gracefully"
        
        # If daemon didn't stop and force is True, forcefully terminate
        if force:
            force_terminate(host, port, pid_file)
            pid_file_path.unlink(missing_ok=True)
            return True, "Daemon forcefully terminated"
        else:
            return False, "Daemon did not stop gracefully"
    except Exception as e:
        logger.exception("Error terminating daemon")
        if force:
            # Try forceful termination
            force_terminate(host, port, pid_file)
            pid_file_path.unlink(missing_ok=True)
            return True, f"Error in graceful shutdown, forcefully terminated: {str(e)}"
        else:
            return False, str(e) 
