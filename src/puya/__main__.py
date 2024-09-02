import argparse
from importlib.metadata import version
from pathlib import Path

import attrs

from puya.log import LogLevel, configure_logging


@attrs.define(kw_only=True)
class _PuyaCLIArgs:
    options: Path | None = None
    awst: Path | None = None
    source_annotations: Path | None = None
    log_level: LogLevel = LogLevel.info


def main() -> None:
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


if __name__ == "__main__":
    main()
