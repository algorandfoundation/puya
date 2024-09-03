import functools
import typing
from collections.abc import Sequence
from pathlib import Path

import attrs
from immutabledict import immutabledict

from puya import log
from puya.arc32 import create_arc32_json
from puya.artifact_sorter import Artifact, ArtifactCompilationSorter
from puya.awst.nodes import (
    AWST,
)
from puya.context import CompileContext
from puya.errors import CodeError, InternalError
from puya.ir.main import awst_to_ir, optimize_and_destructure_ir
from puya.ir.models import (
    Contract as ContractIR,
    LogicSignature,
    ModuleArtifact,
)
from puya.ir.optimize.context import IROptimizeContext
from puya.log import LoggingContext
from puya.mir.main import program_ir_to_mir
from puya.models import (
    CompilationArtifact,
    CompiledContract,
    CompiledLogicSig,
    CompiledProgram,
    ContractMetaData,
    ContractReference,
    LogicSignatureMetaData,
    LogicSigReference,
    TemplateValue,
)
from puya.parse import SourceLocation
from puya.teal.main import mir_to_teal
from puya.teal.models import TealProgram, TealSubroutine
from puya.teal.output import emit_teal
from puya.ussemble.main import assemble_program
from puya.utils import attrs_extend, make_path_relative_to_cwd

logger = log.get_logger(__name__)


def compile_and_write(
    log_ctx: LoggingContext, context: CompileContext, awst: AWST
) -> list[CompilationArtifact]:
    log_ctx.exit_if_errors()
    artifacts = awst_to_teal(log_ctx, context, awst)
    log_ctx.exit_if_errors()
    write_artifacts(context, artifacts)
    log_ctx.exit_if_errors()
    return artifacts


def awst_to_teal(
    log_ctx: LoggingContext, context: CompileContext, awst: AWST
) -> list[CompilationArtifact]:
    log_ctx.exit_if_errors()
    ir = awst_to_ir(context, awst)
    log_ctx.exit_if_errors()
    teal = _ir_to_teal(log_ctx, context, ir)
    log_ctx.exit_if_errors()
    filtered_teal = [t for t in teal if t.id in context.compilation_set]
    return filtered_teal


def _ir_to_teal(
    log_ctx: LoggingContext, context: CompileContext, all_ir: Sequence[ModuleArtifact]
) -> list[CompilationArtifact]:
    result = list[CompilationArtifact]()

    compiled_artifacts = dict[
        ContractReference | LogicSigReference, _CompiledContract | _CompiledLogicSig
    ]()

    @functools.cache
    def get_program_bytecode(
        ref: ContractReference | LogicSigReference,
        kind: typing.Literal["approval", "clear_state", "logic_sig"],
        template_constants: immutabledict[str, TemplateValue],
    ) -> bytes:
        try:
            comp_ref = compiled_artifacts[ref]
        except KeyError:
            raise CodeError(f"invalid reference: {ref}") from None
        if kind == "logic_sig" and isinstance(comp_ref, _CompiledLogicSig):
            return assemble_program(context, comp_ref.program.teal, template_constants).bytecode
        elif kind in ("approval", "clear_state") and isinstance(comp_ref, _CompiledContract):
            program = comp_ref.approval_program if kind == "approval" else comp_ref.clear_program
            return assemble_program(context, program.teal, template_constants).bytecode
        else:
            raise InternalError(f"invalid kind: {kind}, {type(comp_ref)}")

    all_artifact_irs = {
        artifact.metadata.ref: Artifact(path=artifact.source_location.file, ir=artifact)
        for artifact in all_ir
    }

    optimize_context = attrs_extend(
        IROptimizeContext,
        context,
        get_program_bytecode=get_program_bytecode,
        state_totals={
            artifact.id: artifact.ir.metadata.state_totals
            for artifact in all_artifact_irs.values()
            if isinstance(artifact.ir, ContractIR)
        },
    )
    artifact_refs = [artifact.metadata.ref for artifact in all_ir]
    for artifact in ArtifactCompilationSorter.sort(artifact_refs, all_artifact_irs):
        name = artifact.ir.metadata.name
        try:
            out_dir = context.compilation_set[artifact.id]
        except KeyError:
            artifact_ir_base_path = None
        else:
            artifact_ir_base_path = out_dir / name

        num_errors_before_optimization = log_ctx.num_errors
        artifact_ir = optimize_and_destructure_ir(
            optimize_context, artifact.ir, artifact_ir_base_path
        )
        # IR validation that occurs at the end of optimize_and_destructure_ir may have revealed
        # further errors, add dummy artifacts and continue so other artifacts can still be lowered
        # and report any errors they encounter
        errors_in_optimization = log_ctx.num_errors > num_errors_before_optimization
        if artifact_ir_base_path:
            # used to check for conflicts that would occur on output
            artifacts_by_output_base = dict[Path, ModuleArtifact]()
            if existing := artifacts_by_output_base.get(artifact_ir_base_path):
                logger.error(
                    f"Duplicate contract name {name}", location=artifact_ir.source_location
                )
                logger.info(
                    f"Contract name {name} first seen here", location=existing.source_location
                )
            else:
                artifacts_by_output_base[artifact_ir_base_path] = artifact_ir

        compiled: _CompiledContract | _CompiledLogicSig
        match artifact_ir:
            case ContractIR() as contract:
                if errors_in_optimization:
                    compiled = _CompiledContract(
                        approval_program=_dummy_program(),
                        clear_program=_dummy_program(),
                        metadata=contract.metadata,
                        source_location=None,
                    )
                else:
                    compiled = _contract_ir_to_teal(
                        context,
                        contract,
                        artifact_ir_base_path,
                    )

            case LogicSignature() as logic_sig:
                if errors_in_optimization:
                    compiled = _CompiledLogicSig(
                        program=_dummy_program(),
                        metadata=logic_sig.metadata,
                        source_location=None,
                    )
                else:
                    compiled = _logic_sig_to_teal(
                        context,
                        logic_sig,
                        artifact_ir_base_path,
                    )
            case _:
                typing.assert_never(artifact_ir)

        compiled_artifacts[artifact.id] = compiled
        result.append(compiled)
    return result


@attrs.frozen
class _CompiledProgram(CompiledProgram):
    teal: TealProgram
    teal_src: str
    bytecode: bytes | None


@attrs.frozen
class _CompiledContract(CompiledContract):
    source_location: SourceLocation | None
    approval_program: _CompiledProgram
    clear_program: _CompiledProgram
    metadata: ContractMetaData


@attrs.frozen
class _CompiledLogicSig(CompiledLogicSig):
    source_location: SourceLocation | None
    program: _CompiledProgram
    metadata: LogicSignatureMetaData


def _dummy_program() -> _CompiledProgram:
    return _CompiledProgram(
        teal=TealProgram(
            target_avm_version=0, main=TealSubroutine(signature="", blocks=[]), subroutines=[]
        ),
        teal_src="",
        bytecode=b"",
    )


def _contract_ir_to_teal(
    context: CompileContext,
    contract_ir: ContractIR,
    contract_ir_base_path: Path | None,
) -> _CompiledContract:
    approval_mir = program_ir_to_mir(
        context,
        contract_ir.approval_program,
        contract_ir_base_path.with_suffix(".approval.mir") if contract_ir_base_path else None,
    )
    clear_state_mir = program_ir_to_mir(
        context,
        contract_ir.clear_program,
        contract_ir_base_path.with_suffix(".clear.mir") if contract_ir_base_path else None,
    )
    approval = mir_to_teal(context, approval_mir)
    clear_state = mir_to_teal(context, clear_state_mir)
    return _CompiledContract(
        approval_program=_compile_program(context, approval),
        clear_program=_compile_program(context, clear_state),
        metadata=contract_ir.metadata,
        source_location=contract_ir.source_location,
    )


def _logic_sig_to_teal(
    context: CompileContext,
    logic_sig_ir: LogicSignature,
    logic_sig_ir_base_path: Path | None,
) -> _CompiledLogicSig:
    program_mir = program_ir_to_mir(
        context,
        logic_sig_ir.program,
        logic_sig_ir_base_path.with_suffix(".mir") if logic_sig_ir_base_path else None,
    )
    program = mir_to_teal(context, program_mir)
    return _CompiledLogicSig(
        program=_compile_program(context, program),
        metadata=logic_sig_ir.metadata,
        source_location=logic_sig_ir.source_location,
    )


def _compile_program(context: CompileContext, program: TealProgram) -> _CompiledProgram:
    return _CompiledProgram(
        teal=program,
        teal_src=emit_teal(context, program),
        bytecode=(
            assemble_program(
                context,
                program,
                {k: (v, None) for k, v in context.options.template_variables.items()},
            ).bytecode
            if context.options.output_bytecode
            else None
        ),
    )


def write_artifacts(
    context: CompileContext, compiled_artifacts: list[CompilationArtifact]
) -> None:
    if not compiled_artifacts:
        logger.warning("No contracts or logic signatures discovered in any source files")
        return
    for artifact in compiled_artifacts:
        out_dir = context.compilation_set.get(artifact.id)
        if out_dir is None:
            continue
        teal_file_stem = artifact.metadata.name
        arc32_file_stem = f"{teal_file_stem}.arc32.json"
        artifact_base_path = out_dir / teal_file_stem
        match artifact:
            case CompiledLogicSig(program=program):
                programs = {"": program}
            case CompiledContract(approval_program=approval, clear_program=clear) as contract:
                programs = {
                    ".approval": approval,
                    ".clear": clear,
                }
                if contract.metadata.is_arc4:
                    app_spec_json = create_arc32_json(
                        approval.teal_src,
                        clear.teal_src,
                        contract.metadata,
                    )
                    if context.options.output_arc32:
                        arc32_path = out_dir / arc32_file_stem
                        logger.info(f"Writing {make_path_relative_to_cwd(arc32_path)}")
                        arc32_path.write_text(app_spec_json)
            case _:
                typing.assert_never(artifact)
        if context.options.output_teal:
            _write_output(
                artifact_base_path,
                {
                    f"{suffix}.teal": program.teal_src.encode("utf8")
                    for suffix, program in programs.items()
                },
            )
        if context.options.output_bytecode:
            _write_output(
                artifact_base_path,
                {f"{suffix}.bin": program.bytecode for suffix, program in programs.items()},
            )


def _write_output(base_path: Path, programs: dict[str, bytes | None]) -> None:
    for suffix, program in programs.items():
        output_path = base_path.with_suffix(suffix)
        if program is None:
            logger.critical(f"Unable to output {make_path_relative_to_cwd(output_path)}")
        else:
            logger.info(f"Writing {make_path_relative_to_cwd(output_path)}")
            output_path.write_bytes(program)
