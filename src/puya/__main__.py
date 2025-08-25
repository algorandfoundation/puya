import contextlib
import gzip
import sys
from collections.abc import Iterator
from importlib.metadata import version
from multiprocessing import freeze_support
from pathlib import Path

import cyclopts

from puya.errors import PuyaExitError
from puya.log import LogFormat, LogLevel, configure_logging, get_logger
from puya.main import main
from puya.service import start_puya_service

# Required to support multiprocessing in pyinstaller binaries
freeze_support()
logger = get_logger(__name__)

app = cyclopts.App(help="Puya backend", version=version("puyapy"), help_on_error=True)


@app.command
def serve(*, log_level: LogLevel = LogLevel.info) -> None:
    """
    Run in service mode, for use by Puya Language Servers

    Arguments:
        log_level (LogLevel): The minimum log level to be used for logging.
    """
    with _handle_puya_exit():
        start_puya_service(log_level=log_level)


@app.default()
def cli(
    *,
    awst: Path,
    options: Path,
    source_annotations: Path | None = None,
    log_level: LogLevel = LogLevel.info,
    log_format: LogFormat = LogFormat.default,
) -> None:
    """
    Compiles AWST

    Arguments:
        awst (Path): Path to the AWST JSON file. The file may be compressed.
        options (Path): Path to the options JSON file.
        source_annotations (Path | None): Optional path to a source annotations JSON file.
        log_level (LogLevel): The minimum log level to be used for logging.
        log_format (LogFormat): The format in which log messages will be output.
    """
    configure_logging(min_log_level=log_level, log_format=log_format)
    awst_json = _read_text_from_maybe_compressed_file(awst)
    options_json = options.read_text("utf8")
    source_annotations_json = None
    if source_annotations:
        source_annotations_json = source_annotations.read_text("utf8")
    with _handle_puya_exit():
        main(
            options_json=options_json,
            awst_json=awst_json,
            source_annotations_json=source_annotations_json,
        )


@contextlib.contextmanager
def _handle_puya_exit() -> Iterator[None]:
    try:
        yield
    except PuyaExitError as ex:
        sys.exit(ex.exit_code)


def _read_text_from_maybe_compressed_file(path: Path) -> str:
    if path.suffix in (".gz", ".gzip"):
        with gzip.open(path, mode="rt", encoding="utf8") as fp:
            return fp.read()
    else:
        return path.read_text("utf8")


if __name__ == "__main__":
    app()
