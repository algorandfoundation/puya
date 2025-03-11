import argparse
import asyncio
import os
import sys
from importlib.metadata import version
from pathlib import Path

import attrs

from puya.daemon_server import (
    DaemonServer,
    check_server_running,
    cleanup_zombie_daemon,
    get_pid_file_path,
    stop_daemon,
)
from puya.log import LogFormat, LogLevel, configure_logging, get_logger
from puya.main import main

logger = get_logger(__name__)


@attrs.define(kw_only=True)
class _GlobalArgs:
    """Global arguments for all commands."""

    log_level: LogLevel = LogLevel.info
    log_format: LogFormat = LogFormat.default


@attrs.define(kw_only=True)
class _CompileArgs:
    options: Path
    awst: Path
    source_annotations: Path | None = None


@attrs.define(kw_only=True)
class _DaemonArgs:
    command: str  # start, stop, status
    host: str = "127.0.0.1"
    port: int = 8765
    pid_file: Path | None = None


def start_daemon(daemon_args: _DaemonArgs) -> None:
    """Start the daemon server."""

    pid_file_path = get_pid_file_path(daemon_args.pid_file)

    if check_server_running(daemon_args.host, daemon_args.port):
        logger.info(f"A server is already running on {daemon_args.host}:{daemon_args.port}")
        return

    cleanup_zombie_daemon(daemon_args.host, daemon_args.port, daemon_args.pid_file)

    with Path(pid_file_path).open("w") as f:
        f.write(str(os.getpid()))

    daemon_server = DaemonServer(daemon_args.host, daemon_args.port)

    try:
        asyncio.run(daemon_server.start())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    finally:
        if pid_file_path.exists():
            pid_file_path.unlink()


def check_daemon_status(daemon_args: _DaemonArgs) -> None:
    """Check the status of the daemon server."""
    if check_server_running(daemon_args.host, daemon_args.port):
        logger.info(f"✅ Daemon is running on {daemon_args.host}:{daemon_args.port}")
    else:
        logger.info("❌ Daemon is not running")
        cleanup_zombie_daemon(daemon_args.host, daemon_args.port, daemon_args.pid_file)


def add_logging_arguments(parser: argparse.ArgumentParser) -> None:
    """Add logging arguments to a parser."""
    parser.add_argument(
        "--log-level",
        type=LogLevel.from_string,
        choices=list(LogLevel),
        default=LogLevel.info,
        help="Set the logging level",
    )
    parser.add_argument(
        "--log-format",
        type=LogFormat.from_string,
        choices=list(LogFormat),
        default=LogFormat.default,
        help="Set the logging format",
    )


def cli() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="puya", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {version('puyapy')}")

    add_logging_arguments(parser)

    subparsers = parser.add_subparsers(dest="mode", help="Operation mode")

    compile_parser = subparsers.add_parser(
        "compile",
        help="Compile Algorand Python code",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    compile_parser.add_argument(
        "--options", type=Path, required=True, help="Path to options JSON file"
    )
    compile_parser.add_argument("--awst", type=Path, required=True, help="Path to AWST JSON file")
    compile_parser.add_argument(
        "--source-annotations", type=Path, help="Path to source annotations JSON file"
    )

    daemon_parser = subparsers.add_parser(
        "daemon",
        help="Daemon server commands",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    daemon_subparsers = daemon_parser.add_subparsers(
        dest="command", required=True, help="Daemon command"
    )

    common_daemon_args = argparse.ArgumentParser(add_help=False)
    common_daemon_args.add_argument("--host", default="127.0.0.1", help="Host address for daemon")
    common_daemon_args.add_argument("--port", type=int, default=8765, help="Port for daemon")
    common_daemon_args.add_argument("--pid-file", type=Path, help="Path to PID file for daemon")

    daemon_subparsers.add_parser(
        "start",
        parents=[common_daemon_args],
        help="Start the daemon server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    daemon_subparsers.add_parser(
        "stop",
        parents=[common_daemon_args],
        help="Stop the daemon server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    daemon_subparsers.add_parser(
        "status",
        parents=[common_daemon_args],
        help="Check the status of the daemon server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    args = parser.parse_args()
    if not hasattr(args, "mode") or args.mode is None:
        # Default to compile
        parser.print_help()
        sys.exit(1)

    global_args = _GlobalArgs(
        log_level=args.log_level,
        log_format=args.log_format,
    )

    configure_logging(min_log_level=global_args.log_level, log_format=global_args.log_format)

    if args.mode == "compile":
        compile_args = _CompileArgs(
            options=args.options,
            awst=args.awst,
            source_annotations=args.source_annotations,
        )
        run_compile(compile_args)
    elif args.mode == "daemon":
        daemon_args = _DaemonArgs(
            command=args.command,
            host=args.host,
            port=args.port,
            pid_file=args.pid_file,
        )
        run_daemon_command(daemon_args)


def run_compile(compile_args: _CompileArgs) -> None:
    """Run the compiler with the given arguments."""
    options_json = compile_args.options.read_text("utf8")
    awst_json = compile_args.awst.read_text("utf8")

    source_annotations_json = None
    if compile_args.source_annotations:
        source_annotations_json = compile_args.source_annotations.read_text("utf8")

    main(
        options_json=options_json,
        awst_json=awst_json,
        source_annotations_json=source_annotations_json,
    )


def run_daemon_command(daemon_args: _DaemonArgs) -> None:
    """Run the specified daemon command."""
    if daemon_args.command == "start":
        start_daemon(daemon_args)
    elif daemon_args.command == "stop":
        stop_daemon(daemon_args.host, daemon_args.port, daemon_args.pid_file)
    elif daemon_args.command == "status":
        check_daemon_status(daemon_args)


if __name__ == "__main__":
    cli()
