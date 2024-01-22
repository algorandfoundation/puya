import argparse
from pathlib import Path

from puya.algo_constants import MAINNET_TEAL_LANGUAGE_VERSION, SUPPORTED_TEAL_LANGUAGE_VERSIONS
from puya.compile import compile_to_teal
from puya.logging_config import LogLevel, configure_logging
from puya.options import LocalsCoalescingStrategy, PuyaOptions


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="puya",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
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
        "--out-dir", type=Path, help="path for outputting artefacts", default=False
    )
    parser.add_argument(
        "--log-level",
        type=LogLevel.from_string,
        choices=list(LogLevel),
        default=LogLevel.info,
        help="Minimum level to log to console",
    )
    parser.add_argument(
        "-g",  # -g chosen because it is the same option for debug in gcc
        "--debug-level",
        type=int,
        choices=[0, 1, 2],
        default=1,
        help="debug information level",
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
        "--output-destructured-ir",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="output IR after SSA destructuring and before codegen",
    )
    parser.add_argument(
        "--output-memory-ir",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="output MIR before lowering to TealOps",
    )
    parser.add_argument(
        "--target-avm-version",
        type=int,
        choices=SUPPORTED_TEAL_LANGUAGE_VERSIONS,
        default=MAINNET_TEAL_LANGUAGE_VERSION,
    )
    parser.add_argument(
        "--locals-coalescing-strategy",
        type=LocalsCoalescingStrategy,
        choices=list(LocalsCoalescingStrategy),
        default=LocalsCoalescingStrategy.root_operand,
        help=(
            "Strategy choice for out-of-ssa local variable coalescing. "
            "The best choice for your app is best determined through experimentation"
        ),
    )

    parser.add_argument("paths", type=Path, nargs="+", metavar="PATH")
    options = PuyaOptions()
    parser.parse_args(namespace=options)
    configure_logging(min_log_level=options.log_level)
    compile_to_teal(options)


if __name__ == "__main__":
    main()
