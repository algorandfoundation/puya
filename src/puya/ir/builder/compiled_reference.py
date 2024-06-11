import copy
import graphlib
import typing
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import attrs

from puya import log
from puya.algo_constants import MAX_APP_PAGE_SIZE, MAX_BYTES_LENGTH, PROGRAM_DATA
from puya.context import CompileContext
from puya.errors import CodeError, InternalError
from puya.ir import models as ir
from puya.ir.models import CompiledReference, ModuleArtifact
from puya.ir.types_ import AVMBytesEncoding
from puya.ir.visitor import IRTraverser
from puya.ir.visitor_mutator import IRMutator
from puya.models import (
    CompilationArtifact,
    CompiledContract,
    CompiledLogicSignature,
    CompiledReferenceField,
    TemplateVariables,
)
from puya.parse import SourceLocation
from puya.utils import Address, sha512_256_hash

logger = log.get_logger(__name__)


@attrs.frozen
class ProgramAssemblerContext(CompileContext):

    _current_assembles: list[str] = attrs.field(factory=list)


def replace_compiled_references(
    context: CompileContext,
    compiled_artifacts: dict[str, CompiledContract | CompiledLogicSignature],
    artifact: ir.ModuleArtifact,
) -> ir.ModuleArtifact:
    artifact = copy.deepcopy(artifact)
    replacer = CompiledReferenceReplacer(context, compiled_artifacts)
    for program in artifact.all_programs():
        for subroutine in program.subroutines:
            for block in subroutine.body:
                replacer.visit_block(block)
    return artifact


@attrs.define
class CompiledReferenceReplacer(IRMutator):
    context: CompileContext
    artifacts: Mapping[str, CompilationArtifact]

    def visit_compiled_reference(self, const: ir.CompiledReference) -> ir.Constant:  # type: ignore[override]
        try:
            artifact = self.artifacts[const.artifact]
        except KeyError:
            raise InternalError(
                f"Could not find artifact: {const.artifact}", const.source_location
            ) from None
        match artifact, const.field:
            case (
                CompiledContract(approval_program=approval, clear_program=clear),
                CompiledReferenceField.approval | CompiledReferenceField.clear_state,
            ):
                program = approval if const.field == CompiledReferenceField.approval else clear
                program_bytecode = program.get_bytecode_overrides(const.template_variables)
                page = const.program_page
                program_page = program_bytecode[
                    page * MAX_BYTES_LENGTH : (page + 1) * MAX_BYTES_LENGTH
                ]
                return ir.BytesConstant(
                    value=program_page,
                    encoding=AVMBytesEncoding.base64,
                    source_location=const.source_location,
                )
            case CompiledLogicSignature(program=program), CompiledReferenceField.account:
                program_bytecode = program.get_bytecode_overrides(const.template_variables)
                address_public_key = sha512_256_hash(PROGRAM_DATA + program_bytecode)
                return ir.AddressConstant(
                    value=Address.from_public_key(address_public_key).address,
                    source_location=const.source_location,
                )
            case (
                CompiledContract(approval_program=approval, clear_program=clear),
                CompiledReferenceField.extra_program_pages,
            ):
                approval_bytecode = approval.get_bytecode_overrides(const.template_variables)
                clear_bytecode = clear.get_bytecode_overrides(const.template_variables)
                total_bytes = len(approval_bytecode) + len(clear_bytecode)
                extra_pages = (total_bytes - 1) // MAX_APP_PAGE_SIZE
                return ir.UInt64Constant(
                    value=extra_pages,
                    source_location=const.source_location,
                )
            case (
                CompiledContract() as contract,
                (
                    CompiledReferenceField.global_uints
                    | CompiledReferenceField.global_bytes
                    | CompiledReferenceField.local_uints
                    | CompiledReferenceField.local_bytes
                ) as state_field,
            ):
                total = _get_state_total(contract, state_field, const.source_location)
                return ir.UInt64Constant(
                    value=total,
                    source_location=const.source_location,
                )
            case _:
                raise CodeError(
                    f"Invalid field {const.field} for {const.artifact}",
                    const.source_location,
                )


@attrs.frozen(eq=False)
class Artifact:
    ir: ModuleArtifact
    path: Path
    field_template_variables: dict[CompiledReferenceField, list[TemplateVariables]] = attrs.field(
        factory=dict
    )
    depends_on: dict[str, SourceLocation | None] = attrs.field(factory=dict)

    @property
    def full_name(self) -> str:
        return self.ir.metadata.full_name


@attrs.define
class ArtifactCompilationSorter(IRTraverser):
    """
    Sorts IR artifacts so that programs that depend on the byte code of other programs
    are processed after their dependencies
    """

    artifacts: dict[str, Artifact]
    artifact: Artifact

    @classmethod
    def sort(
        cls,
        module_irs: dict[Path, list[ModuleArtifact]],
    ) -> Iterable[Artifact]:
        artifacts = {
            ir.metadata.full_name: Artifact(
                path=path,
                ir=ir,
            )
            for path, module_ir in module_irs.items()
            for ir in module_ir
        }

        for artifact in artifacts.values():
            reference_collector = cls(
                artifacts=artifacts,
                artifact=artifact,
            )
            for program in artifact.ir.all_programs():
                for subroutine in program.subroutines:
                    reference_collector.visit_all_blocks(subroutine.body)
        sorter = graphlib.TopologicalSorter(
            {
                artifact: [artifacts[n] for n in artifact.depends_on]
                for artifact in artifacts.values()
            }
        )
        try:
            result = list(sorter.static_order())
        except graphlib.CycleError as ex:
            artifact_cycle: Sequence[Artifact] = ex.args[1]
            *_, before, last = artifact_cycle
            cycle_loc = last.depends_on[before.full_name]
            programs = " -> ".join(a.full_name for a in reversed(artifact_cycle))
            raise CodeError(f"cyclical program reference: {programs}", cycle_loc) from None
        return result

    def visit_compiled_reference(self, const: CompiledReference) -> None:
        try:
            artifact = self.artifacts[const.artifact]
        except KeyError:
            raise CodeError(f"unknown artifact: {const.artifact}", const.source_location) from None
        variables = tuple(sorted((k, v) for k, v in const.template_variables.items()))

        # add unique references with source_location
        # will re-add a reference if current location is None
        if self.artifact.depends_on.get(const.artifact) is None:
            self.artifact.depends_on[const.artifact] = const.source_location

        # add unique variable sets for this field to the dependency
        field_variable_sets = artifact.field_template_variables.setdefault(const.field, [])
        if variables not in field_variable_sets:
            field_variable_sets.append(variables)


def _get_state_total(
    contract: CompiledContract,
    field: typing.Literal[
        CompiledReferenceField.global_uints,
        CompiledReferenceField.global_bytes,
        CompiledReferenceField.local_uints,
        CompiledReferenceField.local_bytes,
    ],
    loc: SourceLocation | None,
) -> int:
    total = attrs.asdict(contract.metadata.state_totals).get(field.name)
    if not isinstance(total, int):
        raise InternalError(f"Invalid state total field: {field.name}", loc)
    return total
