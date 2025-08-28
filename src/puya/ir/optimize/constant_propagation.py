import typing
from collections import defaultdict

import attrs

from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.register_read_collector import RegisterReadCollector
from puya.ir.visitor_mutator import IRMutator

logger = log.get_logger(__name__)


def constant_replacer(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    collector = _ConstantCollector()
    collector.visit_all_blocks(subroutine.body)
    constants = collector.constants
    ssa_reads = collector.ssa_reads

    modified = False
    work_list = constants.copy()
    while work_list:
        const_reg, const_val = work_list.popitem()
        for const_read in ssa_reads[const_reg]:
            if type(const_read) is models.Assignment and const_read.source == const_reg:
                (register,) = const_read.targets
                work_list[register] = const_val
                constants[register] = const_val
                const_read.source = const_val
                modified = True
            elif type(const_read) is models.Phi:
                maybe_phi_constant = _get_singular_phi_constant(const_read, constants)
                if maybe_phi_constant is not None:
                    work_list[const_read.register] = maybe_phi_constant
                    constants[const_read.register] = maybe_phi_constant
            else:
                replacer = _ConstantRegisterReplacer(find=const_reg, replace=const_val)
                const_read.accept(replacer)
                modified = True
    return modified


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
    ssa_reads: defaultdict[models.Register, list[models.Op | models.ControlOp | models.Phi]] = (
        attrs.field(factory=lambda: defaultdict(list))
    )

    def visit_block(self, block: models.BasicBlock) -> None:
        for op in block.all_ops:
            self._used_registers.clear()
            op.accept(self)
            for read_reg in self.used_registers:
                self.ssa_reads[read_reg].append(op)

    def visit_assignment(self, ass: models.Assignment) -> None:
        src = ass.source
        if isinstance(src, models.Constant):
            (target,) = ass.targets
            self.constants[target] = src
        else:
            super().visit_assignment(ass)


@attrs.frozen(kw_only=True)
class _ConstantRegisterReplacer(IRMutator):
    find: models.Register
    replace: models.Constant

    @typing.override
    def visit_register_define(self, _reg: models.Register) -> None:
        pass

    @typing.override
    def visit_phi(self, phi: models.Phi) -> None:
        # don't visit phi nodes / args, needs to stay as Register
        pass

    @typing.override
    def visit_register(self, reg: models.Register) -> models.Constant | None:
        if reg == self.find:
            return self.replace
        else:
            return None
