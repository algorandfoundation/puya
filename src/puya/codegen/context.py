import attrs

from puya.codegen import ops as mir
from puya.codegen.vla import VariableLifetimeAnalysis
from puya.context import CompileContext
from puya.ir import models as ir
from puya.utils import attrs_extend


@attrs.define
class ProgramCodeGenContext(CompileContext):
    contract: ir.Contract
    program: ir.Program

    def for_subroutine(self, subroutine: mir.MemorySubroutine) -> "SubroutineCodeGenContext":
        return attrs_extend(SubroutineCodeGenContext, self, subroutine=subroutine)


@attrs.define(frozen=False)
class SubroutineCodeGenContext(ProgramCodeGenContext):
    subroutine: mir.MemorySubroutine
    _vla: VariableLifetimeAnalysis | None = attrs.field(default=None)

    @property
    def vla(self) -> VariableLifetimeAnalysis:
        if self._vla is None:
            self._vla = VariableLifetimeAnalysis.analyze(self.subroutine)
        return self._vla

    def invalidate_vla(self) -> None:
        self._vla = None
