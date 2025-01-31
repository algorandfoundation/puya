import graphlib
import typing
from collections.abc import Iterable, Mapping, Sequence

import attrs

from puya import log
from puya.errors import CodeError
from puya.ir.models import CompiledContractReference, CompiledLogicSigReference, ModuleArtifact
from puya.ir.visitor import IRTraverser
from puya.parse import SourceLocation
from puya.program_refs import ContractReference, LogicSigReference

logger = log.get_logger(__name__)


@attrs.frozen(eq=False)
class Artifact:
    ir: ModuleArtifact
    depends_on: dict[ContractReference | LogicSigReference, SourceLocation | None] = attrs.field(
        factory=dict
    )

    @typing.final
    @property
    def id(self) -> ContractReference | LogicSigReference:
        return self.ir.metadata.ref

    @typing.final
    @property
    def source_location(self) -> SourceLocation:
        return self.ir.source_location


@attrs.define
class ArtifactCompilationSorter(IRTraverser):
    """
    Sorts IR artifacts so that programs that depend on the byte code of other programs
    are processed after their dependencies
    """

    artifacts: Mapping[ContractReference | LogicSigReference, Artifact]
    artifact: Artifact

    @classmethod
    def sort(
        cls,
        all_ir: Sequence[ModuleArtifact],
    ) -> Iterable[Artifact]:
        all_artifacts = {artifact.metadata.ref: Artifact(ir=artifact) for artifact in all_ir}
        artifacts = list(all_artifacts.values())
        for artifact in artifacts:
            reference_collector = cls(
                artifacts=all_artifacts,
                artifact=artifact,
            )
            for program in artifact.ir.all_programs():
                for subroutine in program.subroutines:
                    reference_collector.visit_all_blocks(subroutine.body)
        sorter = graphlib.TopologicalSorter(
            {artifact: [all_artifacts[n] for n in artifact.depends_on] for artifact in artifacts}
        )
        try:
            result = list(sorter.static_order())
        except graphlib.CycleError as ex:
            artifact_cycle: Sequence[Artifact] = ex.args[1]
            *_, before, last = artifact_cycle
            cycle_loc = last.depends_on[before.id]
            programs = " -> ".join(a.id for a in reversed(artifact_cycle))
            raise CodeError(f"cyclical program reference: {programs}", cycle_loc) from None
        return result

    def visit_compiled_contract_reference(self, const: CompiledContractReference) -> None:
        self._check_reference(const.artifact)
        # add unique references with source_location
        # will re-add a reference if current location is None
        if self.artifact.depends_on.get(const.artifact) is None:
            self.artifact.depends_on[const.artifact] = const.source_location

    def visit_compiled_logicsig_reference(self, const: CompiledLogicSigReference) -> None:
        self._check_reference(const.artifact)
        # add unique references with source_location
        # will re-add a reference if current location is None
        if self.artifact.depends_on.get(const.artifact) is None:
            self.artifact.depends_on[const.artifact] = const.source_location

    def _check_reference(self, ref: ContractReference | LogicSigReference) -> None:
        if ref not in self.artifacts:
            logger.critical(f"missing reference: {ref}")
