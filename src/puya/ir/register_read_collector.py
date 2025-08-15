from collections.abc import Set

import attrs

from puya.ir import models
from puya.ir.visitor import IRTraverser


@attrs.frozen
class RegisterReadCollector(IRTraverser):
    _used_registers: dict[models.Register, None] = attrs.field(factory=dict, init=False)

    @property
    def used_registers(self) -> Set[models.Register]:
        return self._used_registers.keys()

    def visit_register(self, reg: models.Register) -> None:
        self._used_registers[reg] = None

    def visit_assignment(self, ass: models.Assignment) -> None:
        ass.source.accept(self)

    def visit_phi(self, phi: models.Phi) -> None:
        for arg in phi.args:
            self.visit_phi_argument(arg)
