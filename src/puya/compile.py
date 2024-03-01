import functools
import os
import sys
from collections.abc import Sequence
from pathlib import Path

import mypy.build
import mypy.errors
import mypy.find_sources
import mypy.fscache
import mypy.modulefinder
import mypy.nodes
import mypy.options
import mypy.util
import structlog

from puya.arc32 import create_arc32_json
from puya.awst_build.main import transform_ast
from puya.context import CompileContext
from puya.errors import ErrorExitCode, Errors, InternalError, ParseError, log_exceptions
from puya.ir.main import build_module_irs, optimize_and_destructure_ir
from puya.ir.models import Contract as ContractIR
from puya.mir.main import program_ir_to_mir
from puya.models import CompiledContract
from puya.options import PuyaOptions
from puya.parse import (
    TYPESHED_PATH,
    ParseSource,
    SourceLocation,
    parse_and_typecheck,
)
from puya.teal.main import mir_to_teal
from puya.utils import determine_out_dir, make_path_relative_to_cwd

logger = structlog.get_logger(__name__)


def compile_to_teal(puya_options: PuyaOptions) -> None:
    """Drive the actual core compilation step."""
    logger.debug(puya_options)
    try:
        context = parse_with_mypy(puya_options)
    except ParseError as ex:
        _log_parse_errors(ex)
        sys.exit(ErrorExitCode.code)

    with log_exceptions(context.errors, exit_check=True):
        awst = transform_ast(context)
        module_irs = build_module_irs(context, awst)
        compiled_contracts_by_source_path = module_irs_to_teal(context, module_irs)
        write_artifacts(context, compiled_contracts_by_source_path)


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

    @functools.cache
    def read_source(p: str) -> Sequence[str] | None:
        return mypy.util.read_py_file(p, parse_result.manager.fscache.read)

    context = CompileContext(
        options=puya_options,
        parse_result=parse_result,
        errors=Errors(read_source),
        read_source=read_source,
    )

    return context


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


def module_irs_to_teal(
    context: CompileContext, module_irs: dict[str, list[ContractIR]]
) -> dict[ParseSource, list[CompiledContract]]:
    result = dict[ParseSource, list[CompiledContract]]()
    # used to check for conflicts that would occur on output
    contracts_by_output_base = dict[Path, ContractIR]()
    for src in context.parse_result.sources:
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
                out_dir = determine_out_dir(src.path.parent, context.options)
                name = contract_ir.metadata.name
                contract_ir_base_path = out_dir / name
                if existing := contracts_by_output_base.get(contract_ir_base_path):
                    context.errors.error(
                        f"Duplicate contract name {name}", location=contract_ir.source_location
                    )
                    context.errors.note(
                        f"Contract name {name} first seen here", location=existing.source_location
                    )
                else:
                    contracts_by_output_base[contract_ir_base_path] = contract_ir

                contract_ir = optimize_and_destructure_ir(
                    context, contract_ir, contract_ir_base_path
                )
                compiled = _contract_ir_to_teal(context, contract_ir, contract_ir_base_path)
                result.setdefault(src, []).append(compiled)
    return result


def _contract_ir_to_teal(
    context: CompileContext, contract_ir: ContractIR, contract_ir_base_path: Path
) -> CompiledContract:
    approval_mir = program_ir_to_mir(
        context, contract_ir.approval_program, contract_ir_base_path.with_suffix(".approval.mir")
    )
    clear_state_mir = program_ir_to_mir(
        context, contract_ir.clear_program, contract_ir_base_path.with_suffix(".clear.mir")
    )
    approval_output = mir_to_teal(context, approval_mir)
    clear_state_output = mir_to_teal(context, clear_state_mir)
    compiled = CompiledContract(
        approval_program=approval_output,
        clear_program=clear_state_output,
        metadata=contract_ir.metadata,
    )
    return compiled


def write_artifacts(
    context: CompileContext,
    compiled_contracts_by_source_path: dict[ParseSource, list[CompiledContract]],
) -> None:
    if not compiled_contracts_by_source_path:
        logger.warning("No contracts discovered in any source files")
        return
    for src, compiled_contracts in compiled_contracts_by_source_path.items():
        out_dir = determine_out_dir(src.path.parent, context.options)
        for contract in compiled_contracts:
            teal_file_stem = contract.metadata.name
            arc32_file_stem = f"{teal_file_stem}.arc32.json"
            if context.options.output_teal:
                teal_path = out_dir / teal_file_stem
                write_contract_files(base_path=teal_path, compiled_contract=contract)
            if contract.metadata.is_arc4 and context.options.output_arc32:
                arc32_path = out_dir / arc32_file_stem
                logger.info(f"Writing {make_path_relative_to_cwd(arc32_path)}")
                json_text = create_arc32_json(contract)
                arc32_path.write_text(json_text)


def write_contract_files(base_path: Path, compiled_contract: CompiledContract) -> None:
    output_paths = {
        ".approval.teal": compiled_contract.approval_program,
        ".clear.teal": compiled_contract.clear_program,
    }
    for suffix, src in output_paths.items():
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
