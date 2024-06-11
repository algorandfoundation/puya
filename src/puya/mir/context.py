from collections.abc import Mapping

import attrs

from puya.context import CompileContext
from puya.ir import models as ir
from puya.mir import models
from puya.mir.vla import VariableLifetimeAnalysis
from puya.utils import attrs_extend


@attrs.define(kw_only=True)
class ProgramMIRContext(CompileContext):
    program: ir.Program
    subroutine_names: Mapping[ir.Subroutine, str] = attrs.field(init=False)

    @subroutine_names.default
    def _get_short_subroutine_names(self) -> dict[ir.Subroutine, str]:
        """Return a mapping of unique TEAL names for all subroutines in program, while attempting
        to use the shortest name possible"""
        names = dict[ir.Subroutine, str]()
        names[self.program.main] = "main"
        seen_names = set(names.values())
        for subroutine in self.program.subroutines:
            name: str
            if subroutine.method_name not in seen_names:
                name = subroutine.method_name
            elif (
                subroutine.class_name is not None
                and (class_prefixed := f"{subroutine.class_name}.{subroutine.method_name}")
                not in seen_names
            ):
                name = class_prefixed
            else:
                name = subroutine.full_name
            assert name not in seen_names
            names[subroutine] = name
            seen_names.add(name)

        return names

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
