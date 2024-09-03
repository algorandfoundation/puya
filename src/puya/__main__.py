import argparse
from importlib.metadata import version
from pathlib import Path

import attrs

from puya.log import LogLevel, configure_logging
from puya.main import main


@attrs.define(kw_only=True)
class _PuyaCLIArgs:
    options: Path | None = None
    awst: Path | None = None
    source_annotations: Path | None = None
    log_level: LogLevel = LogLevel.info


def cli() -> None:
    parser = argparse.ArgumentParser(
        prog="puya", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    # TODO: use version of puya instead once package is split
    parser.add_argument("--version", action="version", version=f"%(prog)s {version('puyapy')}")
    parser.add_argument(
        "--log-level", type=LogLevel.from_string, choices=list(LogLevel), default=LogLevel.info
    )
    parser.add_argument("--options", type=Path, required=True)
    parser.add_argument("--awst", type=Path, required=True)
    parser.add_argument("--source-annotations", type=Path)
    parsed_args = _PuyaCLIArgs()
    parser.parse_args(namespace=parsed_args)
    configure_logging(min_log_level=parsed_args.log_level)

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
