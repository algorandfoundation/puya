import sys
from collections.abc import Sequence
from importlib.metadata import version
from typing import Annotated, Literal

import cyclopts

from puya.algo_constants import MAINNET_AVM_VERSION, SUPPORTED_AVM_VERSIONS
from puya.errors import PuyaExitError
from puya.log import LogLevel, configure_logging
from puya.options import LocalsCoalescingStrategy
from puyapy.compile import compile_to_teal
from puyapy.options import PuyaPyOptions
from puyapy.template import parse_template_key_value

_app = cyclopts.App(help_on_error=True, version=f"puyapy {version('puyapy')}")

_outputs_group = cyclopts.Group(
    name="Outputs",
    help="Options for controlling what is output and where",
    sort_key=10,
)
_compilation_group = cyclopts.Group(
    name="Compilation",
    help="Options that affect the compilation process, such as optimisation options etc.",
    sort_key=20,
)
_templating_group = cyclopts.Group(
    name="Templating",
    help="Options for controlling the generation of TEAL template files",
    sort_key=30,
)
_additional_outputs_group = cyclopts.Group(
    name="Additional outputs",
    help="Controls additional compiler outputs that may be useful to compiler developers.",
    sort_key=100,
)

_OutputToggle = Annotated[bool, cyclopts.Parameter(group=_outputs_group)]
_InternalOutputToggle = Annotated[
    bool, cyclopts.Parameter(group=_additional_outputs_group, negative=())
]


@_app.default
def puyapy(
    paths: Annotated[
        Sequence[cyclopts.types.ExistingPath], cyclopts.Parameter(name="PATH", negative=())
    ],
    /,
    *,
    # outputs
    out_dir: Annotated[
        cyclopts.types.Directory | None, cyclopts.Parameter(group=_outputs_group)
    ] = None,
    log_level: Annotated[LogLevel, cyclopts.Parameter(group=_outputs_group)] = LogLevel.info,
    output_teal: _OutputToggle = True,
    output_source_map: _OutputToggle = True,
    output_arc56: _OutputToggle = True,
    output_arc32: _OutputToggle = False,
    output_bytecode: _OutputToggle = False,
    output_client: _OutputToggle = False,
    debug_level: Annotated[
        Literal[0, 1, 2], cyclopts.Parameter(alias="-g", group=_outputs_group)
    ] = 1,
    # compilation
    optimization_level: Annotated[
        Literal[0, 1, 2], cyclopts.Parameter(alias="-O", group=_compilation_group)
    ] = 1,
    target_avm_version: Annotated[  # type: ignore[valid-type]
        Literal[*SUPPORTED_AVM_VERSIONS],
        cyclopts.Parameter(group=_compilation_group),
    ] = MAINNET_AVM_VERSION,
    resource_encoding: Annotated[
        Literal["index", "value"], cyclopts.Parameter(group=_compilation_group)
    ] = "value",
    locals_coalescing_strategy: Annotated[
        LocalsCoalescingStrategy, cyclopts.Parameter(group=_compilation_group)
    ] = LocalsCoalescingStrategy.root_operand,
    # templating
    template_var: Annotated[
        Sequence[str],
        cyclopts.Parameter(alias="-T", group=_templating_group, show_default=False, negative=()),
    ] = (),
    template_vars_prefix: Annotated[str, cyclopts.Parameter(group=_templating_group)] = "TMPL_",
    # internal outputs
    output_awst: _InternalOutputToggle = False,
    output_awst_json: _InternalOutputToggle = False,
    output_source_annotations_json: _InternalOutputToggle = False,
    output_ssa_ir: _InternalOutputToggle = False,
    output_optimization_ir: _InternalOutputToggle = False,
    output_destructured_ir: _InternalOutputToggle = False,
    output_memory_ir: _InternalOutputToggle = False,
    output_teal_intermediates: _InternalOutputToggle = False,
    output_op_statistics: _InternalOutputToggle = False,
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
    cli_template_definitions = dict(parse_template_key_value(t) for t in template_var)
    options = PuyaPyOptions(**args, cli_template_definitions=cli_template_definitions)
    configure_logging(min_log_level=options.log_level)
    try:
        compile_to_teal(options)
    except PuyaExitError as ex:
        sys.exit(ex.exit_code)


def _convert_argparse_style_flags(token: str) -> str:
    match [*token]:
        case "-", "O" | "g" as flag, value:
            return f"-{flag}={value}"
    return token


def app() -> None:
    _app(map(_convert_argparse_style_flags, sys.argv[1:]))


if __name__ == "__main__":
    app()
