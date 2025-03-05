import argparse
import asyncio
import shlex
import sys
from collections.abc import Awaitable
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version
from pathlib import Path
from typing import BinaryIO

import attrs

from puya.log import LogFormat, LogLevel, configure_logging
from puya.main import main


@attrs.define(kw_only=True)
class _PuyaCLIArgs:
    options: Path | None = None
    awst: Path | None = None
    source_annotations: Path | None = None
    log_level: LogLevel = LogLevel.info
    log_format: LogFormat = LogFormat.default


def cli(input_str: str) -> None:
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
    parser.add_argument("--options", type=Path, required=True)
    parser.add_argument("--awst", type=Path, required=True)
    parser.add_argument("--source-annotations", type=Path)
    parsed_args = _PuyaCLIArgs()

    try:
        # Split the input string into args and parse
        args = shlex.split(input_str)
        parser.parse_args(args, namespace=parsed_args)

        configure_logging(min_log_level=parsed_args.log_level, log_format=parsed_args.log_format)

        assert parsed_args.options
        options_json = parsed_args.options.read_text("utf8")
        assert parsed_args.awst
        awst_json = parsed_args.awst.read_text("utf8")
        source_annotations_json = None
        if parsed_args.source_annotations:
            source_annotations_json = parsed_args.source_annotations.read_text("utf8")

        main(
            options_json=options_json,
            awst_json=awst_json,
            source_annotations_json=source_annotations_json,
        )
    except SystemExit:
        # Catch and ignore SystemExit from argparse
        pass
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201


class StdinAsyncReader:
    """Read from stdin asynchronously."""

    def __init__(self, stdin: BinaryIO, executor: ThreadPoolExecutor | None = None):
        self.stdin = stdin
        self._loop: asyncio.AbstractEventLoop | None = None
        self.executor = executor

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = asyncio.get_running_loop()

        return self._loop

    def readline(self) -> Awaitable[bytes]:
        return self.loop.run_in_executor(self.executor, self.stdin.readline)

    def readexactly(self, n: int) -> Awaitable[bytes]:
        return self.loop.run_in_executor(self.executor, self.stdin.read, n)


async def run_async(
    reader: StdinAsyncReader,
) -> None:
    """Run a main message processing loop, asynchronously"""

    while True:
        line = await reader.readline()
        if not line:
            break

        input_str = line.rstrip().decode()
        cli(input_str)


if __name__ == "__main__":
    reader = StdinAsyncReader(sys.stdin.buffer)
    asyncio.run(run_async(reader))
