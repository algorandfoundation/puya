#!/usr/bin/env python3
"""
Example demonstrating how to use Puya daemon mode for efficient compilation.

This example shows:
1. How to start a daemon if not already running
2. How to send compilation requests to the daemon
3. How to stop the daemon when done
"""

import json
import sys
import time
from pathlib import Path

from puya.daemon_client import PuyaDaemonClient, ensure_daemon_running
from puya.daemon_utils import check_daemon_health, terminate_daemon
from puya.main import compile_with_daemon_if_available


def read_json_file(path: Path) -> str:
    """Read a JSON file as a string."""
    return path.read_text("utf8")


def example_direct_daemon_usage():
    """Example of direct daemon interaction using PuyaDaemonClient."""
    # Check if daemon is already running
    client = PuyaDaemonClient()
    
    # Ensure daemon is running (starts it if not)
    if not ensure_daemon_running():
        print("Failed to start daemon")
        return
    
    print("Daemon is running")
    
    # Get some sample files to compile
    # In a real application, these would be your actual files
    options_path = Path("examples/hello_world/out/options.json")
    awst_path = Path("examples/hello_world/out/awst.json")
    
    if not options_path.exists() or not awst_path.exists():
        print("Sample files not found. Run `algokit compile py examples/hello_world/contract.py` first.")
        return
    
    # Read the files
    options_json = read_json_file(options_path)
    awst_json = read_json_file(awst_path)
    
    # Send compilation request to daemon
    print("Sending compilation request to daemon...")
    start_time = time.time()
    
    try:
        result = client.compile_sync(options_json, awst_json)
        end_time = time.time()
        
        print(f"Compilation completed in {end_time - start_time:.2f} seconds")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error compiling: {e}")
    
    # Optionally stop the daemon when done
    print("Stopping daemon...")
    try:
        client.stop_server_sync()
        print("Daemon stopped")
    except:
        print("Daemon could not be stopped gracefully")


def example_high_level_api():
    """Example using the high-level API that handles daemon management automatically."""
    # Get some sample files to compile
    options_path = Path("examples/hello_world/out/options.json")
    awst_path = Path("examples/hello_world/out/awst.json")
    
    if not options_path.exists() or not awst_path.exists():
        print("Sample files not found. Run `algokit compile py examples/hello_world/contract.py` first.")
        return
    
    # Read the files
    options_json = read_json_file(options_path)
    awst_json = read_json_file(awst_path)
    
    # Compile using daemon if available
    print("Compiling with daemon if available...")
    start_time = time.time()
    
    result = compile_with_daemon_if_available(
        options_json=options_json,
        awst_json=awst_json,
        use_daemon=True,
        auto_start_daemon=True
    )
    
    end_time = time.time()
    
    print(f"Compilation completed in {end_time - start_time:.2f} seconds")
    print(f"Used daemon: {result.get('used_daemon', False)}")
    print(f"Success: {result.get('success', False)}")
    
    if not result.get('success', False):
        print(f"Error: {result.get('error', 'Unknown error')}")
        
    # Check daemon health
    health = check_daemon_health()
    print(f"Daemon health: {json.dumps(health, indent=2)}")
    
    # Terminate daemon if running
    if health['responsive']:
        success, message = terminate_daemon(force=True)
        print(f"Daemon terminated: {success}, {message}")


if __name__ == "__main__":
    # Run one of the examples
    if len(sys.argv) > 1 and sys.argv[1] == "--direct":
        example_direct_daemon_usage()
    else:
        example_high_level_api() 
