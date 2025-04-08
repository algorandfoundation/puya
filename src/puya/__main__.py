import argparse
import sys
from importlib.metadata import version
from multiprocessing import freeze_support
from pathlib import Path

import attrs

from puya.errors import PuyaExitError
from puya.log import LogFormat, LogLevel, configure_logging, get_logger
from puya.main import main

# Required to support multiprocessing in pyinstaller binaries
freeze_support()
logger = get_logger(__name__)


@attrs.define(kw_only=True)
class _PuyaCLIArgs:
    command: str | None = None
    options: Path | None = None
    awst: Path | None = None
    source_annotations: Path | None = None
    log_level: LogLevel = LogLevel.info
    log_format: LogFormat = LogFormat.default


def cli() -> None:
    parser = argparse.ArgumentParser(
        prog="puya", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    # TODO: use version of puya instead once package is split
    parser.add_argument("--version", action="version", version=f"%(prog)s {version('puyapy')}")
    parser.add_argument(
        "--log-level", type=LogLevel.__getitem__, choices=list(LogLevel), default=LogLevel.info
    )
    parser.add_argument(
        "--log-format",
        type=LogFormat,
        choices=list(LogFormat),
        default=LogFormat.default,
    )

    # Add main arguments to the main parser
    parser.add_argument("--options", type=Path, required=False)
    parser.add_argument("--awst", type=Path, required=False)
    parser.add_argument("--source-annotations", type=Path)

    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Service command
    subparsers.add_parser("serve", help="Run in service mode")

    parsed_args = _PuyaCLIArgs()
    parser.parse_args(namespace=parsed_args)

    if parsed_args.command == "serve":
        from puya.puya_service import create_server

        log_file = sys.stderr
        configure_logging(min_log_level=parsed_args.log_level, file=log_file)

        logger.info("Starting puyad server...")
        puyad_server = create_server(thread_count=2)  # Using default thread count

        puyad_server.start_io()
        return
    else:
        # Regular execution requires options and awst
        if not parsed_args.options or not parsed_args.awst:
            parser.error("--options and --awst are required when not running in service mode")

        configure_logging(min_log_level=parsed_args.log_level, log_format=parsed_args.log_format)

    options_json = parsed_args.options.read_text("utf8")
    awst_json = parsed_args.awst.read_text("utf8")
    source_annotations_json = None
    if parsed_args.source_annotations:
        source_annotations_json = parsed_args.source_annotations.read_text("utf8")
    try:
        main(
            options_json=options_json,
            awst_json=awst_json,
            source_annotations_json=source_annotations_json,
        )
    except PuyaExitError as ex:
        sys.exit(ex.exit_code)


if __name__ == "__main__":
    cli()
