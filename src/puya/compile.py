import itertools
import shutil
import typing
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

import attrs
from cattrs.preconf.json import make_converter
from immutabledict import immutabledict

from puya import log
from puya.arc32 import create_arc32_json
from puya.arc56 import create_arc56_json
from puya.artifact_metadata import ContractMetaData, LogicSignatureMetaData, StateTotals
from puya.artifact_sorter import Artifact, ArtifactCompilationSorter
from puya.awst.nodes import AWST
from puya.awst.validation.main import validate_awst
from puya.compilation_artifacts import (
    CompilationArtifact,
    CompiledContract,
    CompiledLogicSig,
    CompiledProgram,
    DebugInfo,
    TemplateValue,
)
from puya.context import (
    ArtifactCompileContext,
    CompileContext,
    CompiledProgramProvider,
    OutputPathProvider,
)
from puya.errors import CodeError, InternalError
from puya.ir import models as ir_models
from puya.ir.main import awst_to_ir, transform_ir
from puya.ir.to_text_visitor import render_program
from puya.log import LoggingContext
from puya.mir.main import program_ir_to_mir
from puya.options import PuyaOptions
from puya.parse import SourceLocation
from puya.program_refs import ContractReference, LogicSigReference, ProgramKind
from puya.teal.main import mir_to_teal
from puya.teal.models import TealProgram
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
    ir = list(awst_to_ir(context, awst))
    log_ctx.exit_if_errors()
    teal = list(_ir_to_teal(log_ctx, context, ir))
    log_ctx.exit_if_errors()
    if write:
        _write_artifacts(context, teal)
    return teal


def _ir_to_teal(
    log_ctx: LoggingContext, context: CompileContext, all_ir: Sequence[ir_models.ModuleArtifact]
) -> Iterator[CompilationArtifact]:
    compiled_program_provider = _CompiledProgramProviderImpl(
        compile_context=context,
        state_totals={
            ir.metadata.ref: ir.metadata.state_totals
            for ir in all_ir
            if isinstance(ir, ir_models.Contract)
        },
    )

    # used to check for conflicts that would occur on output
    artifacts_by_output_base = dict[Path, Artifact]()
    for artifact in ArtifactCompilationSorter.sort(all_ir):
        output_path_provider = None
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
                output_path_provider = _SequentialOutputPathProvider(
                    metadata=artifact.ir.metadata, out_dir=out_dir
                )

        artifact_context = attrs_extend(
            ArtifactCompileContext,
            context,
            output_path_provider=output_path_provider,
            compiled_program_provider=compiled_program_provider,
        )

        num_errors_before_transforms = log_ctx.num_errors
        artifact_ir = artifact.ir
        if artifact_context.options.output_ssa_ir:
            for program in artifact_ir.all_programs():
                render_program(artifact_context, program, qualifier="ssa")
        artifact_ir = transform_ir(artifact_context, artifact_ir)

        # IR validation that occurs at the end of optimize_and_destructure_ir may have revealed
        # further errors, add dummy artifacts and continue so other artifacts can still be lowered
        # and report any errors they encounter
        errors_in_optimization = log_ctx.num_errors > num_errors_before_transforms

        if not errors_in_optimization:
            compiled: _CompiledContract | _CompiledLogicSig
            if isinstance(artifact_ir, ir_models.Contract):
                compiled = _contract_ir_to_teal(artifact_context, artifact_ir)
            else:
                compiled = _logic_sig_to_teal(artifact_context, artifact_ir)
            yield compiled
            compiled_program_provider.add_compiled_result(artifact, compiled)


@attrs.define
class _CompiledProgramProviderImpl(CompiledProgramProvider):
    compile_context: CompileContext
    state_totals: Mapping[ContractReference, StateTotals]
    _compiled_artifacts: dict[
        ContractReference | LogicSigReference, "_CompiledContract | _CompiledLogicSig"
    ] = attrs.field(factory=dict, init=False)
    _bytecode_cache: dict[
        tuple[
            ContractReference | LogicSigReference, ProgramKind, immutabledict[str, TemplateValue]
        ],
        bytes,
    ] = attrs.field(factory=dict, init=False)

    def add_compiled_result(
        self, artifact: Artifact, result: "_CompiledContract | _CompiledLogicSig"
    ) -> None:
        self._compiled_artifacts[artifact.id] = result

    @typing.override
    def build_program_bytecode(
        self,
        ref: ContractReference | LogicSigReference,
        kind: ProgramKind,
        *,
        template_constants: immutabledict[str, TemplateValue],
    ) -> bytes:
        cache_key = (ref, kind, template_constants)
        try:
            return self._bytecode_cache[cache_key]
        except KeyError:
            pass

        try:
            comp_ref = self._compiled_artifacts[ref]
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
            self.compile_context,
            ref,
            program.teal,
            template_constants=template_constants,
            is_reference=True,
        )
        result = assembled.bytecode
        self._bytecode_cache[cache_key] = result
        return result

    @typing.override
    def get_state_totals(self, ref: ContractReference) -> StateTotals:
        return self.state_totals[ref]


@attrs.define
class _SequentialOutputPathProvider(OutputPathProvider):
    _metadata: ContractMetaData | LogicSignatureMetaData
    _out_dir: Path
    _group_seq: int = attrs.field(default=0, init=False)
    _output_seq: defaultdict[str, Iterator[int]] = attrs.field(
        factory=lambda: defaultdict(itertools.count), init=False
    )

    @typing.override
    def begin_group(self) -> None:
        self._output_seq.clear()
        self._group_seq += 1

    @typing.override
    def next_path(self, *, kind: str, qualifier: str, suffix: str) -> Path:
        out_dir = self._out_dir
        out_dir.mkdir(exist_ok=True, parents=True)
        if qualifier:
            qualifier = f".{qualifier}"
        seq = self._group_seq * 100 + next(self._output_seq[kind])
        qualifier = f"{seq:03d}{qualifier}"
        if kind is not ProgramKind.logic_signature:
            qualifier = f"{kind}.{qualifier}"
        return out_dir / f"{self._metadata.name}.{qualifier}.{suffix}"


@attrs.frozen
class _CompiledProgram(CompiledProgram):
    teal: TealProgram
    teal_src: str
    template_variables: Mapping[str, int | bytes | None]
    stats: Mapping[str, int]
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


def _contract_ir_to_teal(
    context: ArtifactCompileContext, contract_ir: ir_models.Contract
) -> _CompiledContract:
    approval_mir = program_ir_to_mir(context, contract_ir.approval_program)
    clear_state_mir = program_ir_to_mir(context, contract_ir.clear_program)
    approval_teal = mir_to_teal(context, approval_mir)
    clear_state_teal = mir_to_teal(context, clear_state_mir)
    ref = contract_ir.metadata.ref
    approval_program = _compile_program(context, ref, approval_teal)
    clear_program = _compile_program(context, ref, clear_state_teal)
    return _CompiledContract(
        approval_program=approval_program,
        clear_program=clear_program,
        metadata=contract_ir.metadata,
        source_location=contract_ir.source_location,
    )


def _logic_sig_to_teal(
    context: ArtifactCompileContext, logic_sig_ir: ir_models.LogicSignature
) -> _CompiledLogicSig:
    program_mir = program_ir_to_mir(context, logic_sig_ir.program)
    teal_program = mir_to_teal(context, program_mir)
    program = _compile_program(context, logic_sig_ir.metadata.ref, teal_program)
    return _CompiledLogicSig(
        program=program,
        metadata=logic_sig_ir.metadata,
        source_location=logic_sig_ir.source_location,
    )


def _compile_program(
    context: ArtifactCompileContext,
    ref: ContractReference | LogicSigReference,
    program: TealProgram,
) -> _CompiledProgram:
    assembled = assemble_program(context, ref, program)
    teal_src = emit_teal(context, program)
    return _CompiledProgram(
        teal=program,
        teal_src=teal_src,
        bytecode=assembled.bytecode,
        debug_info=assembled.debug_info,
        template_variables=assembled.template_variables,
        stats=assembled.stats,
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
        out_dir.mkdir(exist_ok=True, parents=True)
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
        if context.options.output_op_statistics:
            _write_output(
                artifact_base_path,
                {
                    f"{suffix}.stats.txt": "\n".join(
                        f"{stat} = {value}" for stat, value in program.stats.items()
                    ).encode("utf8")
                    for suffix, program in programs.items()
                },
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
