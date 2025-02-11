from collections.abc import Mapping

import attrs

from puya.context import ArtifactCompileContext
from puya.ir import models as ir
from puya.mir import models
from puya.mir.vla import VariableLifetimeAnalysis
from puya.utils import attrs_extend


@attrs.define(kw_only=True)
class ProgramMIRContext(ArtifactCompileContext):
    program: ir.Program
    subroutine_names: Mapping[ir.Subroutine, str] = attrs.field(init=False)

    @subroutine_names.default
    def _get_short_subroutine_names(self) -> dict[ir.Subroutine, str]:
        """Return a mapping of unique TEAL names for all subroutines in program, while attempting
        to use the shortest name possible"""
        names = {"main": self.program.main}
        for subroutine in self.program.subroutines:
            if subroutine.short_name and subroutine.short_name not in names:
                name = subroutine.short_name
            else:
                assert subroutine.id not in names
                name = subroutine.id
            names[name] = subroutine

        return {v: k for k, v in names.items()}

    def for_subroutine(self, subroutine: models.MemorySubroutine) -> "SubroutineCodeGenContext":
        return attrs_extend(SubroutineCodeGenContext, self, subroutine=subroutine)


@attrs.define(frozen=False)
class SubroutineCodeGenContext(ProgramMIRContext):
    subroutine: models.MemorySubroutine
    _vla: VariableLifetimeAnalysis | None = None

    @property
    def vla(self) -> VariableLifetimeAnalysis:
        if self._vla is None:
            self._vla = VariableLifetimeAnalysis.analyze(self.subroutine)
        return self._vla

    def invalidate_vla(self) -> None:
        self._vla = None
