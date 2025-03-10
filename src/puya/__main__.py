import argparse
import asyncio
import json
import os
import signal
import sys
from importlib.metadata import version
from pathlib import Path
import socket
from typing import Any, Dict, Optional, Union

import attrs

from puya.log import LogFormat, LogLevel, configure_logging
from puya.main import main
from puya.daemon_server import DaemonServer
from puya.daemon_utils import get_pid_file_path, check_server_running, stop_daemon, cleanup_zombie_daemon


@attrs.define(kw_only=True)
class _PuyaCLIArgs:
    options: Path | None = None
    awst: Path | None = None
    source_annotations: Path | None = None
    log_level: LogLevel = LogLevel.info
    log_format: LogFormat = LogFormat.default
    daemon: bool = False
    daemon_stop: bool = False
    host: str = "127.0.0.1"
    port: int = 8765
    pid_file: Path | None = None


def start_daemon(args: _PuyaCLIArgs) -> None:
    """Start the daemon server.
    
    Args:
        args: Command line arguments
    """
    pid_file_path = get_pid_file_path(args.pid_file)
    
    # Check if a server is already running
    if check_server_running(args.host, args.port):
        print(f"A server is already running on {args.host}:{args.port}")
        return
    
    # First try to clean up any zombie daemon
    cleanup_zombie_daemon(args.host, args.port, args.pid_file)
    
    # Save PID to file
    with open(pid_file_path, "w") as f:
        f.write(str(os.getpid()))
    
    # Start the daemon server
    daemon_server = DaemonServer(args.host, args.port, args.log_level, args.log_format)
    
    try:
        asyncio.run(daemon_server.start())
    except KeyboardInterrupt:
        print("Keyboard interrupt received, shutting down...")
    finally:
        # Clean up PID file
        if pid_file_path.exists():
            pid_file_path.unlink()


def cli() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="puya", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    # TODO: use version of puya instead once package is split
    parser.add_argument("--version", action="version", version=f"%(prog)s {version('puyapy')}")
    parser.add_argument(
        "--log-level", type=LogLevel.from_string, choices=list(LogLevel), default=LogLevel.info
    )
    parser.add_argument(
        "--log-format",
        type=LogFormat.from_string,
        choices=list(LogFormat),
        default=LogFormat.default,
    )
    
    # Daemon mode arguments
    parser.add_argument("--daemon", action="store_true", help="Start in daemon mode")
    parser.add_argument("--daemon-stop", action="store_true", help="Stop the daemon")
    parser.add_argument("--host", default="127.0.0.1", help="Host address for daemon mode")
    parser.add_argument("--port", type=int, default=8765, help="Port for daemon mode")
    parser.add_argument("--pid-file", type=Path, help="Path to PID file for daemon")
    
    # Standard compilation arguments - only required if not in daemon mode
    if "--daemon" not in sys.argv and "--daemon-stop" not in sys.argv:
        parser.add_argument("--options", type=Path, required=True)
        parser.add_argument("--awst", type=Path, required=True)
        parser.add_argument("--source-annotations", type=Path)
    else:
        parser.add_argument("--options", type=Path)
        parser.add_argument("--awst", type=Path)
        parser.add_argument("--source-annotations", type=Path)
    
    parsed_args = _PuyaCLIArgs()
    parser.parse_args(namespace=parsed_args)
    
    if parsed_args.daemon_stop:
        stop_daemon(parsed_args.host, parsed_args.port, parsed_args.pid_file)
        return
    
    if parsed_args.daemon:
        start_daemon(parsed_args)
        return
    
    # Standard non-daemon mode operation
    configure_logging(min_log_level=parsed_args.log_level, log_format=parsed_args.log_format)

    assert parsed_args.options, "Options file is required for compilation"
    options_json = parsed_args.options.read_text("utf8")
    assert parsed_args.awst, "AWST file is required for compilation"
    awst_json = parsed_args.awst.read_text("utf8")
    source_annotations_json = None
    if parsed_args.source_annotations:
        source_annotations_json = parsed_args.source_annotations.read_text("utf8")
    main(
        options_json=options_json,
        awst_json=awst_json,
        source_annotations_json=source_annotations_json,
    )


if __name__ == "__main__":
    cli()
