from collections.abc import Mapping

import attrs

from puya.context import ArtifactCompileContext
from puya.ir import models as ir


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
