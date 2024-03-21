import os
import typing
from pathlib import Path

import mypy.build
import mypy.errors
import mypy.find_sources
import mypy.fscache
import mypy.modulefinder
import mypy.nodes
import mypy.options
import mypy.util

from puya import log
from puya.arc32 import create_arc32_json, write_arc32_client
from puya.awst_build.main import transform_ast
from puya.context import CompileContext
from puya.errors import (
    InternalError,
    ParseError,
)
from puya.ir.main import build_module_irs, optimize_and_destructure_ir
from puya.ir.models import (
    Contract as ContractIR,
    LogicSignature,
    ModuleArtifact,
)
from puya.mir.main import program_ir_to_mir
from puya.models import CompilationArtifact, CompiledContract, CompiledLogicSignature
from puya.options import PuyaOptions
from puya.parse import (
    TYPESHED_PATH,
    ParseSource,
    SourceLocation,
    parse_and_typecheck,
)
from puya.teal.main import mir_to_teal
from puya.utils import determine_out_dir, make_path_relative_to_cwd

logger = log.get_logger(__name__)


def compile_to_teal(puya_options: PuyaOptions) -> None:
    """Drive the actual core compilation step."""
    with log.logging_context() as log_ctx:
        logger.debug(puya_options)
        context = parse_with_mypy(puya_options)
        log_ctx.exit_if_errors()
        awst = transform_ast(context)
        log_ctx.exit_if_errors()
        module_irs = build_module_irs(context, awst)
        log_ctx.exit_if_errors()
        compiled_contracts_by_source_path = module_irs_to_teal(context, module_irs)
        log_ctx.exit_if_errors()
        write_artifacts(context, compiled_contracts_by_source_path)
    log_ctx.exit_if_errors()


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

    context = CompileContext(
        options=puya_options,
        parse_result=parse_result,
    )

    return context


def get_mypy_options() -> mypy.options.Options:
    mypy_opts = mypy.options.Options()
    # improve mypy parsing performance by using a cut-down typeshed
    mypy_opts.custom_typeshed_dir = str(TYPESHED_PATH)
    mypy_opts.abs_custom_typeshed_dir = str(TYPESHED_PATH.resolve())

    mypy_opts.export_types = True
    mypy_opts.preserve_asts = True
    mypy_opts.include_docstrings = True
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

    mypy_opts.pretty = True  # show source in output

    return mypy_opts


def module_irs_to_teal(
    context: CompileContext, module_irs: dict[str, list[ModuleArtifact]]
) -> dict[ParseSource, list[CompilationArtifact]]:
    result = dict[ParseSource, list[CompilationArtifact]]()
    # used to check for conflicts that would occur on output
    artifacts_by_output_base = dict[Path, ModuleArtifact]()
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
            for artifact_ir in module_ir:
                out_dir = determine_out_dir(src.path.parent, context.options)
                name = artifact_ir.metadata.name
                artifact_ir_base_path = out_dir / name
                if existing := artifacts_by_output_base.get(artifact_ir_base_path):
                    logger.error(
                        f"Duplicate contract name {name}", location=artifact_ir.source_location
                    )
                    logger.info(
                        f"Contract name {name} first seen here", location=existing.source_location
                    )
                else:
                    artifacts_by_output_base[artifact_ir_base_path] = artifact_ir

                artifact_ir = optimize_and_destructure_ir(
                    context, artifact_ir, artifact_ir_base_path
                )

                match artifact_ir:
                    case ContractIR() as contract:
                        compiled: CompilationArtifact = _contract_ir_to_teal(
                            context, contract, artifact_ir_base_path
                        )
                    case LogicSignature() as logic_sig:
                        compiled = _logic_sig_to_teal(context, logic_sig, artifact_ir_base_path)
                    case _:
                        typing.assert_never(artifact_ir)

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


def _logic_sig_to_teal(
    context: CompileContext, logic_sig_ir: LogicSignature, logic_sig_ir_base_path: Path
) -> CompiledLogicSignature:
    program_mir = program_ir_to_mir(
        context, logic_sig_ir.program, logic_sig_ir_base_path.with_suffix(".mir")
    )
    program_output = mir_to_teal(context, program_mir)
    compiled = CompiledLogicSignature(
        program=program_output,
        metadata=logic_sig_ir.metadata,
    )
    return compiled


def write_artifacts(
    context: CompileContext,
    compiled_artifacts_by_source_path: dict[ParseSource, list[CompilationArtifact]],
) -> None:
    if not compiled_artifacts_by_source_path:
        logger.warning("No contracts or logic signatures discovered in any source files")
        return
    for src, compiled_artifacts in compiled_artifacts_by_source_path.items():
        out_dir = determine_out_dir(src.path.parent, context.options)
        for artifact in compiled_artifacts:
            teal_file_stem = artifact.metadata.name
            arc32_file_stem = f"{teal_file_stem}.arc32.json"
            match artifact:
                case CompiledLogicSignature() as logic_sig:
                    if context.options.output_teal:
                        write_logic_sig_files(
                            base_path=out_dir / teal_file_stem, compiled_logic_sig=logic_sig
                        )
                case CompiledContract() as contract:
                    if context.options.output_teal:
                        teal_path = out_dir / teal_file_stem
                        write_contract_files(base_path=teal_path, compiled_contract=contract)
                    if artifact.metadata.is_arc4:
                        if context.options.output_arc32:
                            arc32_path = out_dir / arc32_file_stem
                            logger.info(f"Writing {make_path_relative_to_cwd(arc32_path)}")
                            json_text = create_arc32_json(contract)
                            arc32_path.write_text(json_text)
                        if context.options.output_client:
                            write_arc32_client(
                                contract.metadata.name, contract.metadata.arc4_methods, out_dir
                            )
                case _:
                    typing.assert_never(artifact)


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


def write_logic_sig_files(base_path: Path, compiled_logic_sig: CompiledLogicSignature) -> None:
    output_path = base_path.with_suffix(".teal")
    output_text = "\n".join(compiled_logic_sig.program)
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
