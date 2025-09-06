import sys
import typing
from collections.abc import Sequence
from importlib.metadata import version

import cyclopts

from puya.algo_constants import MAINNET_AVM_VERSION, SUPPORTED_AVM_VERSIONS
from puya.log import LogLevel, configure_logging
from puya.options import LocalsCoalescingStrategy
from puyapy.compile import compile_to_teal
from puyapy.options import PuyaPyOptions
from puyapy.template import parse_template_key_value

_app = cyclopts.App(help_on_error=True, version=f"puyapy {version('puyapy')}")


@_app.default
def puyapy(
    paths: typing.Annotated[
        Sequence[cyclopts.types.ExistingPath], cyclopts.Parameter(name="PATH", negative=())
    ],
    /,
    *,
    out_dir: cyclopts.types.Directory | None = None,
    output_awst: bool = False,
    output_awst_json: bool = False,
    output_source_annotations_json: bool = False,
    output_client: bool = False,
    output_ssa_ir: bool = False,
    output_optimization_ir: bool = False,
    output_destructured_ir: bool = False,
    output_memory_ir: bool = False,
    output_teal_intermediates: bool = False,
    output_teal: bool = True,
    output_source_map: bool = True,
    output_bytecode: bool = False,
    output_arc32: bool = True,
    output_arc56: bool = True,
    output_op_statistics: bool = False,
    optimization_level: typing.Annotated[
        typing.Literal[0, 1, 2], cyclopts.Parameter(alias="-O")
    ] = 1,
    debug_level: typing.Annotated[typing.Literal[0, 1, 2], cyclopts.Parameter(alias="-g")] = 1,
    target_avm_version: typing.Literal[*SUPPORTED_AVM_VERSIONS] = MAINNET_AVM_VERSION,  # type: ignore[valid-type]
    template_vars_prefix: str = "TMPL_",
    template_var: typing.Annotated[Sequence[str], cyclopts.Parameter(alias="-T")] = (),
    locals_coalescing_strategy: LocalsCoalescingStrategy = LocalsCoalescingStrategy.root_operand,
    resource_encoding: typing.Literal["index", "value"] = "value",
    log_level: LogLevel = LogLevel.info,
) -> None:
    """
    PuyaPy compiler for compiling Algorand Python to TEAL

    Parameters:
        paths: Files or directories to compile
        output_teal: Output TEAL code
        output_source_map: Output debug source maps
        output_arc32: Output {contract}.arc32.json ARC-32 app spec file
        output_arc56: Output {contract}.arc56.json ARC-56 app spec file
        output_client: Output Algorand Python contract client for typed ARC-4 ABI calls
        output_awst: Output parsed result of AWST
        output_awst_json: Output parsed result of AWST as JSON
        output_source_annotations_json: Output source annotations result of AWST parse as JSON
        output_ssa_ir: Output IR (in SSA form) before optimizations
        output_optimization_ir: Output IR after each optimization
        output_destructured_ir: Output IR after SSA destructuring and before MIR
        output_memory_ir: Output MIR before lowering to TEAL
        output_bytecode: Output AVM bytecode
        output_teal_intermediates: Output TEAL before peephole optimization and before
                                block optimization
        output_op_statistics: Output statistics about ops used for each program compiled
                optimization_level: Set optimization level of output TEAL / AVM bytecode
        optimization_level: Set optimization level of output TEAL / AVM bytecode
        debug_level: Output debug information level, 0 = none,
                     1 = debug, 2 = reserved for future use
        target_avm_version: Target AVM version
        template_var: Define template vars for use when assembling via --output-bytecode.
                      Should be specified without the prefix (see --template-vars-prefix), e.g.
                      -T SOME_INT=1234 SOME_BYTES=0x1A2B SOME_BOOL=True -T SOME_STR="hello"
        template_vars_prefix: Define the prefix to use with --template-var
        locals_coalescing_strategy: Strategy choice for out-of-ssa local variable coalescing.
                                    The best choice for your app is best determined through
                                    experimentation
        resource_encoding: If "index", then resource types (Application, Asset, Account) in ABI
                           methods should be passed as an index into their
                           appropriate foreign array.
                           The default option "value", as of PuyaPy 5.0, means these values will be
                           passed directly.
        out_dir: Path for outputting artefacts
        log_level: Minimum level to log to console
    """
    args = locals()
    args.pop("template_var")
    options = PuyaPyOptions(
        **args,
        cli_template_definitions=dict(parse_template_key_value(t) for t in template_var),
    )
    configure_logging(min_log_level=options.log_level)
    compile_to_teal(options)


def _convert_argparse_style_flags(token: str) -> str:
    if len(token) == 3 and token.startswith(("-O", "-g")):
        _, flag, value = iter(token)
        return f"-{flag}={value}"
    return token


def app() -> None:
    _app(map(_convert_argparse_style_flags, sys.argv[1:]))


if __name__ == "__main__":
    app()
