import argparse
from importlib.metadata import version
from pathlib import Path

from puya.algo_constants import MAINNET_TEAL_LANGUAGE_VERSION, SUPPORTED_TEAL_LANGUAGE_VERSIONS
from puya.compile import compile_to_teal
from puya.log import LogLevel, configure_logging
from puya.options import LocalsCoalescingStrategy, PuyaOptions


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="puyapy",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {version('puyapy')}")
    parser.add_argument(
        "-O",
        "--optimization-level",
        type=int,
        choices=[0, 1, 2],
        default=1,
        help="Set optimization level of output TEAL / AVM bytecode",
    )
    parser.add_argument(
        "--output-teal",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Output TEAL code",
    )
    parser.add_argument(
        "--output-arc32",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Output {contract}.arc32.json ARC-32 app spec file",
    )
    parser.add_argument(
        "--output-client",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Output Algorand Python contract client for typed ARC4 ABI calls",
    )
    parser.add_argument(
        "--out-dir", type=Path, help="Path for outputting artefacts", default=False
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
        help="Output debug information level, 0 = none, 1 = debug, 2 = reserved for future use",
    )
    parser.add_argument(
        "--output-awst",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Output parsed result of AST",
    )
    parser.add_argument(
        "--output-ssa-ir",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Output IR (in SSA form) before optimisations",
    )
    parser.add_argument(
        "--output-optimization-ir",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Output IR after each optimization",
    )
    parser.add_argument(
        "--output-destructured-ir",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Output IR after SSA destructuring and before MIR",
    )
    parser.add_argument(
        "--output-memory-ir",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Output MIR before lowering to TealOps",
    )
    parser.add_argument(
        "--output-bytecode",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Output AVM bytecode",
    )
    parser.add_argument(
        "--match-algod-bytecode",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="When outputting bytecode, ensure bytecode matches algod output",
    )
    parser.add_argument(
        "-T",
        "--template-var",
        dest="cli_template_definitions",
        metavar="VAR=VALUE",
        action="append",
        help="Define template vars for use when assembling via --output-bytecode"
        " should be specified without the prefix (see --template-vars-prefix), e.g."
        " -T=SOME_INT=1234"
        " -T=SOME_BYTES=0x1A2B"
        ' -T=SOME_STR=\\"hello\\"',
    )
    parser.add_argument(
        "--template-vars-prefix",
        help="Define the prefix to use with --template-var",
        default="TMPL_",
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
