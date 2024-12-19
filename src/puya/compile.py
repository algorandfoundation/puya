import functools
import shutil
import typing
from collections.abc import Mapping, Sequence
from pathlib import Path

import attrs
from cattrs.preconf.json import make_converter
from immutabledict import immutabledict

from puya import log
from puya.arc32 import create_arc32_json
from puya.arc56 import create_arc56_json
from puya.artifact_sorter import Artifact, ArtifactCompilationSorter
from puya.awst.nodes import AWST
from puya.awst.validation.main import validate_awst
from puya.context import ArtifactCompileContext, CompileContext
from puya.errors import CodeError, InternalError
from puya.ir.main import awst_to_ir, optimize_and_destructure_ir
from puya.ir.models import (
    Contract as ContractIR,
    LogicSignature,
    ModuleArtifact,
)
from puya.log import LoggingContext
from puya.mir.main import program_ir_to_mir
from puya.models import (
    CompilationArtifact,
    CompiledContract,
    CompiledLogicSig,
    CompiledProgram,
    ContractMetaData,
    ContractReference,
    DebugInfo,
    LogicSignatureMetaData,
    LogicSigProgramReference,
    LogicSigReference,
    ProgramKind,
    TemplateValue,
)
from puya.options import PuyaOptions
from puya.parse import SourceLocation
from puya.teal.main import mir_to_teal
from puya.teal.models import TealProgram, TealSubroutine
from puya.teal.output import emit_teal
from puya.ussemble.main import assemble_program
from puya.utils import attrs_extend, make_path_relative_to, make_path_relative_to_cwd

logger = log.get_logger(__name__)


def awst_to_teal(
    log_ctx: LoggingContext,
    options: PuyaOptions,
    compilation_set: Mapping[ContractReference | LogicSigReference, Path],
    sources_by_path: Mapping[Path, Sequence[str] | None],
    awst: AWST,
    *,
    write: bool = True,
) -> list[CompilationArtifact]:
    validate_awst(awst)
    log_ctx.exit_if_errors()
    context = CompileContext(
        options=options,
        compilation_set=compilation_set,
        sources_by_path=sources_by_path,
    )
    log_ctx.exit_if_errors()
    ir = awst_to_ir(context, awst)
    log_ctx.exit_if_errors()
    teal = _ir_to_teal(log_ctx, context, ir)
    log_ctx.exit_if_errors()
    if write:
        _write_artifacts(context, teal)
    return teal


def _ir_to_teal(
    log_ctx: LoggingContext, context: CompileContext, all_ir: Sequence[ModuleArtifact]
) -> list[CompilationArtifact]:
    compiled_artifacts = dict[
        ContractReference | LogicSigReference, _CompiledContract | _CompiledLogicSig
    ]()

    @functools.cache
    def get_program_bytecode(
        ref: ContractReference | LogicSigReference,
        kind: ProgramKind,
        template_constants: immutabledict[str, TemplateValue],
    ) -> bytes:
        try:
            comp_ref = compiled_artifacts[ref]
        except KeyError:
            raise CodeError(f"invalid reference: {ref}") from None
        match kind, comp_ref:
            case ProgramKind.logic_signature, _CompiledLogicSig(program=program):
                pass
            case ProgramKind.approval, _CompiledContract(approval_program=program):
                pass
            case ProgramKind.clear_state, _CompiledContract(clear_program=program):
                pass
            case _:
                raise InternalError(f"invalid kind: {kind}, {type(comp_ref)}")
        assembled = assemble_program(
            context, program.teal, template_constants=template_constants, is_reference=True
        )
        return assembled.bytecode

    state_totals = {
        ir.metadata.ref: ir.metadata.state_totals for ir in all_ir if isinstance(ir, ContractIR)
    }

    # used to check for conflicts that would occur on output
    artifacts_by_output_base = dict[Path, Artifact]()
    result = list[CompilationArtifact]()
    for artifact in ArtifactCompilationSorter.sort(all_ir):
        out_dir = None
        if out_dir_setting := context.compilation_set.get(artifact.id):
            name = artifact.ir.metadata.name
            maybe_out_dir = out_dir_setting / f"{name}.ir"
            first_seen = artifacts_by_output_base.setdefault(maybe_out_dir, artifact)
            if artifact is not first_seen:
                logger.error(f"duplicate contract name {name}", location=artifact.source_location)
                logger.info(
                    f"contract name {name} first seen here", location=first_seen.source_location
                )
            else:
                out_dir = maybe_out_dir
                shutil.rmtree(out_dir, ignore_errors=True)

        artifact_context = attrs_extend(
            ArtifactCompileContext,
            context,
            get_program_bytecode=get_program_bytecode,
            state_totals=state_totals,
            out_dir=out_dir,
            metadata=artifact.ir.metadata,
        )

        num_errors_before_optimization = log_ctx.num_errors
        artifact_ir = optimize_and_destructure_ir(artifact_context, artifact.ir)
        # IR validation that occurs at the end of optimize_and_destructure_ir may have revealed
        # further errors, add dummy artifacts and continue so other artifacts can still be lowered
        # and report any errors they encounter
        errors_in_optimization = log_ctx.num_errors > num_errors_before_optimization

        compiled: _CompiledContract | _CompiledLogicSig
        match artifact_ir:
            case ContractIR() as contract:
                if not errors_in_optimization:
                    compiled = _contract_ir_to_teal(artifact_context, contract)
                else:
                    compiled = _CompiledContract(
                        approval_program=_dummy_program(),
                        clear_program=_dummy_program(),
                        metadata=contract.metadata,
                        source_location=None,
                    )
            case LogicSignature() as logic_sig:
                if not errors_in_optimization:
                    compiled = _logic_sig_to_teal(artifact_context, logic_sig)
                else:
                    compiled = _CompiledLogicSig(
                        program=_dummy_program(),
                        metadata=logic_sig.metadata,
                        source_location=None,
                    )
            case unexpected:
                typing.assert_never(unexpected)

        compiled_artifacts[artifact.id] = compiled
        result.append(compiled)
    return result


@attrs.frozen
class _CompiledProgram(CompiledProgram):
    teal: TealProgram
    teal_src: str
    template_variables: Mapping[str, int | bytes | None]
    debug_info: DebugInfo | None = None
    bytecode: bytes | None = None


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
    from puya.mir.models import Signature

    return _CompiledProgram(
        teal=TealProgram(
            ref=LogicSigProgramReference(LogicSigReference()),
            avm_version=0,
            main=TealSubroutine(
                is_main=True,
                signature=Signature(
                    name="",
                    parameters=(),
                    returns=(),
                ),
                blocks=[],
                source_location=None,
            ),
            subroutines=[],
        ),
        teal_src="",
        template_variables={},
    )


def _contract_ir_to_teal(
    context: ArtifactCompileContext, contract_ir: ContractIR
) -> _CompiledContract:
    approval_mir = program_ir_to_mir(context, contract_ir.approval_program)
    clear_state_mir = program_ir_to_mir(context, contract_ir.clear_program)
    approval = mir_to_teal(context, approval_mir)
    clear_state = mir_to_teal(context, clear_state_mir)
    return _CompiledContract(
        approval_program=_compile_program(context, approval),
        clear_program=_compile_program(context, clear_state),
        metadata=contract_ir.metadata,
        source_location=contract_ir.source_location,
    )


def _logic_sig_to_teal(
    context: ArtifactCompileContext, logic_sig_ir: LogicSignature
) -> _CompiledLogicSig:
    program_mir = program_ir_to_mir(context, logic_sig_ir.program)
    program = mir_to_teal(context, program_mir)
    return _CompiledLogicSig(
        program=_compile_program(context, program),
        metadata=logic_sig_ir.metadata,
        source_location=logic_sig_ir.source_location,
    )


def _compile_program(context: ArtifactCompileContext, program: TealProgram) -> _CompiledProgram:
    assembled = assemble_program(context, program)
    return _CompiledProgram(
        teal=program,
        teal_src=emit_teal(context, program),
        bytecode=assembled.bytecode,
        debug_info=assembled.debug_info,
        template_variables=assembled.template_variables,
    )


def _write_artifacts(
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
                    if context.options.output_arc32:
                        app_spec_json = create_arc32_json(
                            approval.teal_src,
                            clear.teal_src,
                            contract.metadata,
                        )
                        _write_output(
                            artifact_base_path,
                            {".arc32.json": app_spec_json.encode("utf8")},
                        )
                    if context.options.output_arc56:
                        app_spec_json = create_arc56_json(
                            metadata=contract.metadata,
                            approval_program=approval,
                            clear_program=clear,
                            template_prefix=context.options.template_vars_prefix,
                        )
                        _write_output(
                            artifact_base_path,
                            {".arc56.json": app_spec_json.encode("utf8")},
                        )
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
        if context.options.output_source_map:
            _write_output(
                artifact_base_path,
                {
                    f"{suffix}.puya.map": (
                        _debug_info_as_json(program.debug_info, out_dir)
                        if program.debug_info
                        else None
                    )
                    for suffix, program in programs.items()
                },
            )


_debug_info_converter = make_converter(omit_if_default=True)


def _debug_info_as_json(info: DebugInfo, base_path: Path) -> bytes:
    # make sources relative to output
    info = attrs.evolve(
        info,
        sources=[
            make_path_relative_to(path=Path(s), to=base_path, walk_up=True) for s in info.sources
        ],
    )
    json = _debug_info_converter.dumps(info, DebugInfo, indent=2)
    return json.encode("utf-8")


def _write_output(base_path: Path, programs: dict[str, bytes | None]) -> None:
    for suffix, program in programs.items():
        output_path = base_path.with_suffix(suffix)
        if program is None:
            logger.critical(f"Unable to output {make_path_relative_to_cwd(output_path)}")
        else:
            logger.info(f"Writing {make_path_relative_to_cwd(output_path)}")
            output_path.write_bytes(program)
