from collections import defaultdict

import attrs

from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.register_read_collector import RegisterReadCollector
from puya.ir.visitor_mutator import IRMutator

logger = log.get_logger(__name__)


_AnyOp = models.Op | models.ControlOp


def constant_replacer(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    collector = _ConstantCollector()
    collector.visit_all_blocks(subroutine.body)
    constants = collector.constants
    ssa_reads = collector.ssa_reads

    modified = 0
    work_list = constants.copy()
    while work_list:
        const_reg, const_val = work_list.popitem()
        replacer = ConstantRegisterReplacer({const_reg: const_val})
        for const_read in ssa_reads[const_reg]:
            if isinstance(const_read, models.Assignment) and const_read.source == const_reg:
                (register,) = const_read.targets
                constants[register] = work_list[register] = const_val
            const_read.accept(replacer)
        modified += replacer.modified

    phi_replace = {
        phi.register: phi_constant
        for block in subroutine.body
        for phi in block.phis
        if (phi_constant := _get_singular_phi_constant(phi, constants)) is not None
    }
    if phi_replace:
        modified += ConstantRegisterReplacer.apply(phi_replace, to=subroutine)
    return modified > 0


def _get_singular_phi_constant(
    phi: models.Phi, constants: dict[models.Register, models.Constant]
) -> models.Constant | None:
    try:
        (constant,) = {constants[phi_arg.value] for phi_arg in phi.args}
    except (KeyError, ValueError):
        return None
    else:
        return constant


@attrs.frozen
class _ConstantCollector(RegisterReadCollector):
    constants: dict[models.Register, models.Constant] = attrs.field(factory=dict)
    ssa_reads: defaultdict[models.Register, list[_AnyOp]] = attrs.field(
        factory=lambda: defaultdict(list)
    )

    def visit_block(self, block: models.BasicBlock) -> None:
        for op in block.ops:
            op.accept(self)
            for read_reg in self.used_registers:
                self.ssa_reads[read_reg].append(op)
            self._used_registers.clear()

        terminator = block.terminator
        assert terminator is not None
        terminator.accept(self)
        for read_reg in self.used_registers:
            self.ssa_reads[read_reg].append(terminator)

    def visit_assignment(self, ass: models.Assignment) -> None:
        src = ass.source
        if isinstance(src, models.Constant):
            (target,) = ass.targets
            self.constants[target] = src
        else:
            super().visit_assignment(ass)


@attrs.define
class ConstantRegisterReplacer(IRMutator):
    constants: dict[models.Register, models.Constant]
    modified: int = 0

    @classmethod
    def apply(
        cls, constants: dict[models.Register, models.Constant], to: models.Subroutine
    ) -> int:
        replacer = cls(constants)
        for block in to.body:
            replacer.visit_block(block)
        return replacer.modified

    def visit_assignment(self, ass: models.Assignment) -> models.Assignment:
        # don't visit target(s), needs to stay as Register
        ass.source = ass.source.accept(self)
        return ass

    def visit_phi(self, phi: models.Phi) -> models.Phi:
        # don't visit phi nodes, needs to stay as Register
        return phi

    def visit_register(self, reg: models.Register) -> models.Register:
        try:
            const = self.constants[reg]
        except KeyError:
            return reg
        self.modified += 1
        return const  # type: ignore[return-value]
