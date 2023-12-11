import argparse
from pathlib import Path

from puya.compile import compile_to_teal
from puya.logging_config import LogLevel, configure_logging
from puya.options import PuyaOptions


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="puya",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-g",  # -g chosen because it is the same option for debug in gcc
        "--debug-level",
        type=int,
        choices=[0, 1, 2],
        default=0,
        help="debug information level",
    )
    parser.add_argument(
        "-O",
        "--optimization-level",
        type=int,
        choices=[0, 1, 2],
        default=1,
        help="set optimization level",
    )
    parser.add_argument(
        "--output-teal",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Output TEAL",
    )
    parser.add_argument(
        "--output-arc32",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Output ARC32 application.json",
    )
    parser.add_argument(
        "--output-awst",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="output parsed result of AST",
    )
    parser.add_argument(
        "--output-ssa-ir",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="output IR in SSA form",
    )
    parser.add_argument(
        "--output-optimization-ir",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="output IR after each optimization",
    )
    parser.add_argument(
        "--output-final-ir",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="output IR before codegen",
    )
    parser.add_argument(
        "--output-cssa-ir",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="output IR in cssa form",
    )
    parser.add_argument(
        "--output-post-ssa-ir",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="output IR post ssa form",
    )
    parser.add_argument(
        "--output-parallel-copies-ir",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="output IR after parallel copy sequentialization",
    )
    parser.add_argument(
        "--out-dir", type=Path, help="path for outputting artefacts", default=False
    )
    parser.add_argument(
        "--log-level",
        type=LogLevel.from_string,
        choices=list(LogLevel),
    )

    parser.add_argument("paths", type=Path, nargs="+", metavar="PATH")
    options = PuyaOptions()
    parser.parse_args(namespace=options)
    configure_logging(min_log_level=options.log_level)
    compile_to_teal(options)


if __name__ == "__main__":
    main()
