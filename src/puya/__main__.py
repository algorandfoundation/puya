import gzip
from importlib.metadata import version
from multiprocessing import freeze_support
from pathlib import Path

import cyclopts

from puya.log import LogFormat, LogLevel, configure_logging, get_logger
from puya.main import main

# Required to support multiprocessing in pyinstaller binaries
freeze_support()
logger = get_logger(__name__)

app = cyclopts.App(version=f"puya {version("puyapy")}", help_on_error=True)


@app.default()
def puya(
    *,
    awst: cyclopts.types.ExistingFile,
    options: cyclopts.types.ExistingFile,
    source_annotations: cyclopts.types.ExistingFile | None = None,
    log_level: LogLevel = LogLevel.info,
    log_format: LogFormat = LogFormat.default,
) -> None:
    """
    Compiles AWST

    Arguments:
        awst: Path to the AWST JSON file. The file may be compressed.
        optionsPath to the options JSON file.
        source_annotations: Optional path to a source annotations JSON file.
        log_level: The minimum log level to be used for logging.
        log_format: The format in which log messages will be output.
    """
    configure_logging(min_log_level=log_level, log_format=log_format)
    awst_json = _read_text_from_maybe_compressed_file(awst)
    options_json = options.read_text("utf8")
    source_annotations_json = None
    if source_annotations:
        source_annotations_json = source_annotations.read_text("utf8")
    main(
        options_json=options_json,
        awst_json=awst_json,
        source_annotations_json=source_annotations_json,
    )


def _read_text_from_maybe_compressed_file(path: Path) -> str:
    if path.suffix in (".gz", ".gzip"):
        with gzip.open(path, mode="rt", encoding="utf8") as fp:
            return fp.read()
    else:
        return path.read_text("utf8")


if __name__ == "__main__":
    app()
