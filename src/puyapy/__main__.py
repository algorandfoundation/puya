import argparse
import typing
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path

from puya.algo_constants import MAINNET_AVM_VERSION, SUPPORTED_AVM_VERSIONS
from puya.log import LogLevel, configure_logging
from puya.options import LocalsCoalescingStrategy
from puyapy.compile import compile_to_teal
from puyapy.options import PuyaPyOptions
from puyapy.template import parse_template_key_value


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
        "--output-source-map",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Output debug source maps",
    )
    parser.add_argument(
        "--output-arc32",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Output {contract}.arc32.json ARC-32 app spec file",
    )
    parser.add_argument(
        "--output-arc56",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Output {contract}.arc56.json ARC-56 app spec file",
    )
    parser.add_argument(
        "--output-client",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Output Algorand Python contract client for typed ARC-4 ABI calls",
    )
    parser.add_argument(
        "--out-dir", type=Path, help="Path for outputting artefacts", default=False
    )
    parser.add_argument(
        "--log-level",
        type=LogLevel.__getitem__,
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
        help="Output parsed result of AWST",
    )
    parser.add_argument(
        "--output-awst-json",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Output parsed result of AWST as JSON",
    )
    parser.add_argument(
        "--output-source-annotations-json",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Output source annotations result of AWST parse as JSON",
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
        "--output-teal-intermediates",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Output TEAL before peephole optimisation and before block optimisation",
    )
    parser.add_argument(
        "--output-bytecode",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Output AVM bytecode",
    )
    parser.add_argument(
        "--output-op-statistics",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Output statistics about ops used for each program compiled",
    )
    parser.add_argument(
        "--match-algod-bytecode",
        action=_EmitDeprecated,
        dest=argparse.SUPPRESS,
        nargs=0,
        help="Deprecated: When outputting bytecode, ensure bytecode matches algod output",
    )
    parser.add_argument(
        "-T",
        "--template-var",
        dest="cli_template_definitions",
        metavar="VAR=VALUE",
        action=_ParseAndStoreTemplateVar,
        default={},
        nargs="+",
        help="Define template vars for use when assembling via --output-bytecode"
        " should be specified without the prefix (see --template-vars-prefix), e.g."
        ' -T SOME_INT=1234 SOME_BYTES=0x1A2B SOME_BOOL=True SOME_STR=\\"hello\\"',
    )
    parser.add_argument(
        "--template-vars-prefix",
        help="Define the prefix to use with --template-var",
        default="TMPL_",
    )
    parser.add_argument(
        "--target-avm-version",
        type=int,
        choices=SUPPORTED_AVM_VERSIONS,
        default=MAINNET_AVM_VERSION,
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

    namespace = parser.parse_args()
    options = PuyaPyOptions(**vars(namespace))
    configure_logging(min_log_level=options.log_level)
    compile_to_teal(options)


class _EmitDeprecated(argparse.Action):
    @typing.override
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[typing.Any] | None,
        option_string: str | None = None,
    ) -> None:
        print(f"warning: {option_string} is deprecated and no longer does anything")  # noqa: T201


class _ParseAndStoreTemplateVar(argparse.Action):
    @typing.override
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[typing.Any] | None,
        option_string: str | None = None,
    ) -> None:
        mapping: dict[str, int | bytes] = dict(getattr(namespace, self.dest, {}))
        lst = []
        if isinstance(values, str):
            lst = [values]
        elif values:
            for value in values:
                assert isinstance(value, str)
                lst.append(value)
        for kv in lst:
            try:
                name, value = parse_template_key_value(kv)
            except Exception as ex:
                parser.error(str(ex))
            mapping[name] = value
        setattr(namespace, self.dest, mapping)


if __name__ == "__main__":
    main()
