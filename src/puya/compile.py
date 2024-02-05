import os
import sys
from pathlib import Path

import mypy.build
import mypy.errors
import mypy.find_sources
import mypy.fscache
import mypy.modulefinder
import mypy.nodes
import mypy.options
import structlog

from puya.arc32 import write_arc32
from puya.awst import nodes as awst_nodes
from puya.awst_build.main import transform_ast
from puya.codegen.builder import compile_ir_to_teal
from puya.codegen.emitprogram import CompiledContract
from puya.context import CompileContext
from puya.errors import ErrorExitCode, Errors, InternalError, ParseError, log_exceptions
from puya.ir.context import IRBuildContext
from puya.ir.destructure.main import destructure_ssa
from puya.ir.main import build_embedded_ir, build_ir
from puya.ir.optimize.dead_code_elimination import remove_unused_subroutines
from puya.ir.optimize.main import optimize_contract_ir
from puya.ir.to_text_visitor import output_contract_ir_to_path
from puya.options import PuyaOptions
from puya.parse import (
    EMBEDDED_MODULES,
    TYPESHED_PATH,
    ParseSource,
    SourceLocation,
    parse_and_typecheck,
)
from puya.utils import attrs_extend, determine_out_dir, make_path_relative_to_cwd

logger = structlog.get_logger(__name__)


def parse_with_mypy(puya_options: PuyaOptions) -> CompileContext:
    mypy_options = get_mypy_options()
    # this generates the ASTs from the build sources, and all imported modules (recursively)
    try:
        parse_result = parse_and_typecheck(puya_options.paths, mypy_options)
    except mypy.errors.CompileError as ex:
        parse_errors = list[str]()
        parse_errors.extend(ex.messages)
        if not parse_errors:
            for a in ex.args:
                lines = a.splitlines()
                parse_errors.extend(lines)
        raise ParseError(parse_errors) from ex

    # Sometimes when we call back into mypy, there might be errors.
    # We don't want to crash when that happens.
    parse_result.manager.errors.set_file("<puya>", module=None, scope=None, options=mypy_options)

    # extract the source reader
    read_source = parse_result.manager.errors.read_source
    if read_source is None:
        raise InternalError("parse_results.manager.errors.read_source is None")

    context = CompileContext(
        options=puya_options,
        parse_result=parse_result,
        errors=Errors(read_source),
        read_source=read_source,
    )

    return context


def awst_to_teal(
    context: CompileContext, module_asts: dict[str, awst_nodes.Module]
) -> dict[ParseSource, list[CompiledContract]] | None:
    errors = context.errors
    parse_result = context.parse_result

    if errors.num_errors:
        return None
    embedded_funcs = [
        func
        for embedded_src in EMBEDDED_MODULES.values()
        for func in module_asts[embedded_src.puya_module_name].body
        if isinstance(func, awst_nodes.Function)
    ]
    build_context: IRBuildContext = attrs_extend(
        IRBuildContext,
        context,
        subroutines={},
        module_awsts=module_asts,
        embedded_funcs=embedded_funcs,
    )

    build_embedded_ir(build_context)
    module_irs = {
        source.module_name: [
            build_ir(build_context, node)
            for node in module_asts[source.module_name].body
            if isinstance(node, awst_nodes.ContractFragment) and not node.is_abstract
        ]
        for source in parse_result.sources
    }
    if errors.num_errors:
        return None

    result = dict[ParseSource, list[CompiledContract]]()
    for src in parse_result.sources:
        module_ir = module_irs.get(src.module_name)
        if module_ir is None:
            raise InternalError(f"Could not find IR for {src.path}")

        if not module_ir:
            if src.is_explicit:
                logger.warning(
                    f"No contracts found in explicitly named source file:"
                    f" {make_path_relative_to_cwd(src.path)}"
                )
        else:
            for contract_ir in module_ir:
                remove_unused_subroutines(context, contract_ir)
                metadata = contract_ir.metadata
                out_dir = determine_out_dir(src.path.parent, context.options)
                contract_ir_base_path = out_dir / "_".join((src.path.stem, metadata.class_name))
                if context.options.output_ssa_ir:
                    output_contract_ir_to_path(
                        contract_ir, contract_ir_base_path.with_suffix(".ssa.ir")
                    )

                if context.options.optimization_level > 0:
                    logger.info(
                        f"Optimizing {metadata.full_name}"
                        f" at level {context.options.optimization_level}"
                    )
                    contract_ir = optimize_contract_ir(
                        context,
                        contract_ir,
                        contract_ir_base_path if context.options.output_optimization_ir else None,
                    )

                contract_ir = destructure_ssa(context, contract_ir, contract_ir_base_path)

                compiled_contract = compile_ir_to_teal(context, contract_ir)
                result.setdefault(src, []).append(compiled_contract)

    if errors.num_errors:
        return None

    return result


def write_arc32_application_spec(
    context: CompileContext,
    compiled_contracts_by_source_path: dict[ParseSource, list[CompiledContract]],
) -> None:
    for src, compiled_contracts in compiled_contracts_by_source_path.items():
        arc4_contracts = [c for c in compiled_contracts if c.metadata.is_arc4]
        if not arc4_contracts:
            continue
        base_path = determine_out_dir(src.path.parent, context.options)
        for arc4_contract in arc4_contracts:
            stem = (
                "application.json"
                if len(arc4_contracts) == 1
                else f"application.{arc4_contract.metadata.full_name}.json"
            )
            arc32_path = base_path / stem
            logger.info(f"Writing {make_path_relative_to_cwd(arc32_path)}")
            write_arc32(arc32_path, arc4_contract)


def write_compiled_contracts(
    context: CompileContext,
    compiled_contracts_by_source_path: dict[ParseSource, list[CompiledContract]],
) -> None:
    for src, compiled_contracts in compiled_contracts_by_source_path.items():
        if len(compiled_contracts) == 1:
            base_path = determine_out_dir(src.path.parent, context.options) / src.path.stem
            write_contract_files(base_path=base_path, compiled_contract=compiled_contracts[0])
        else:
            for contract in compiled_contracts:
                base_path = determine_out_dir(src.path.parent, context.options)

                qualified_path = base_path / f"{src.path.stem}_{contract.metadata.full_name}"
                write_contract_files(base_path=qualified_path, compiled_contract=contract)


def log_options(puya_options: PuyaOptions) -> None:
    logger.debug(puya_options)


def compile_to_teal(puya_options: PuyaOptions) -> None:
    """Drive the actual core compilation step."""
    log_options(puya_options)
    try:
        context = parse_with_mypy(puya_options)
    except ParseError as ex:
        _log_parse_errors(ex)
        sys.exit(ErrorExitCode.code)

    with log_exceptions(context.errors, exit_on_failure=True):
        awst = transform_ast(context)
        compiled_contracts_by_source_path = awst_to_teal(context, awst)
        write_teal_to_output(context, compiled_contracts_by_source_path)


def write_teal_to_output(
    context: CompileContext, contracts: dict[ParseSource, list[CompiledContract]] | None
) -> None:
    if contracts is None:
        logger.error("Build failed")
        sys.exit(ErrorExitCode.code)
    elif not contracts:
        logger.error("No contracts discovered in any source files")
    else:
        options = context.options
        if options.output_teal:
            write_compiled_contracts(context, contracts)
        if options.output_arc32:
            write_arc32_application_spec(context, contracts)


def get_mypy_options() -> mypy.options.Options:
    # TODO: build configuration interface to these options
    mypy_opts = mypy.options.Options()
    # improve mypy parsing performance by using a cut-down typeshed
    mypy_opts.custom_typeshed_dir = str(TYPESHED_PATH)
    mypy_opts.abs_custom_typeshed_dir = str(TYPESHED_PATH.resolve())

    mypy_opts.export_types = True
    mypy_opts.preserve_asts = True
    # next two options disable caching entirely.
    # slows things down but prevents intermittent failures.
    mypy_opts.incremental = False
    mypy_opts.cache_dir = os.devnull

    # strict mode flags, need to review these and all others too
    mypy_opts.disallow_any_generics = True
    mypy_opts.disallow_subclassing_any = True
    mypy_opts.disallow_untyped_calls = True
    mypy_opts.disallow_untyped_defs = True
    mypy_opts.disallow_incomplete_defs = True
    mypy_opts.check_untyped_defs = True
    mypy_opts.disallow_untyped_decorators = True
    mypy_opts.warn_redundant_casts = True
    mypy_opts.warn_unused_ignores = True
    mypy_opts.warn_return_any = True
    mypy_opts.strict_equality = True
    mypy_opts.strict_concatenate = True

    # disallow use of any
    mypy_opts.disallow_any_unimported = True
    mypy_opts.disallow_any_expr = True
    mypy_opts.disallow_any_decorated = True
    mypy_opts.disallow_any_explicit = True

    # mypy_opts.dump_graph = True
    # mypy_opts.dump_deps = True

    mypy_opts.pretty = True  # show source in output

    return mypy_opts


def write_contract_files(base_path: Path, compiled_contract: CompiledContract) -> None:
    output_paths = {
        ".approval.teal": compiled_contract.approval_program.src,
        ".approval.debug.teal": compiled_contract.approval_program.debug_src,
        ".clear.teal": compiled_contract.clear_program.src,
        ".clear.debug.teal": compiled_contract.clear_program.debug_src,
    }
    for suffix, src in output_paths.items():
        if src is None:
            continue
        output_path = base_path.with_suffix(suffix)
        output_text = "\n".join(src)
        logger.info(f"Writing {make_path_relative_to_cwd(output_path)}")
        output_path.write_text(output_text, encoding="utf-8")


def _log_parse_error(errors: list[str], location: SourceLocation | None) -> None:
    if not errors:
        return
    message, *related_lines = errors
    logger.error(message, related_lines=related_lines, location=location)


def _log_parse_errors(ex: ParseError) -> None:
    location: SourceLocation | None = None
    related_errors = list[str]()
    for error in ex.errors:
        if not error.location:
            # collate related error messages and log together
            related_errors.append(error.message)
        else:
            _log_parse_error(related_errors, location)
            related_errors = [error.message]
            location = error.location
    _log_parse_error(related_errors, location)
