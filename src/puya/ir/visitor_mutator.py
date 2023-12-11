import contextlib
import typing as t
from collections.abc import Iterator

import attrs

from puya.ir.models import (
    AddressConstant,
    Assignment,
    BasicBlock,
    BigUIntConstant,
    BytesConstant,
    ConditionalBranch,
    ControlOp,
    Fail,
    Goto,
    GotoNth,
    Intrinsic,
    InvokeSubroutine,
    MethodConstant,
    Op,
    Phi,
    PhiArgument,
    ProgramExit,
    Register,
    SubroutineReturn,
    Switch,
    UInt64Constant,
    ValueTuple,
)
from puya.ir.visitor import IRVisitor


@attrs.define
class IRMutator(IRVisitor[t.Any]):
    is_target_context: bool = attrs.field(default=False, init=False)
    current_op: Phi | Op | ControlOp | None = attrs.field(
        default=None, init=False
    )  # TODO: this is probably removable

    @contextlib.contextmanager
    def _enter_target_context(self) -> Iterator[None]:
        assert not self.is_target_context
        self.is_target_context = True
        try:
            yield
        finally:
            self.is_target_context = False

    def visit_block(self, block: BasicBlock) -> None:
        new_phis = []
        for phi in block.phis:
            self.current_op = phi
            new_phi = self.visit_phi(phi)
            if new_phi is not None:
                new_phis.append(new_phi)
        block.phis = new_phis
        new_ops = []
        for op in block.ops:
            self.current_op = op
            new_op = op.accept(self)
            if new_op is not None:
                new_ops.append(new_op)
        block.ops = new_ops
        if block.terminator is not None:
            self.current_op = block.terminator
            block.terminator = block.terminator.accept(self)

    def visit_assignment(self, ass: Assignment) -> Assignment | None:
        with self._enter_target_context():
            ass.targets = [self.visit_register(r) for r in ass.targets]
        ass.source = ass.source.accept(self)
        return ass

    def visit_register(self, reg: Register) -> Register:
        return reg

    def visit_uint64_constant(self, const: UInt64Constant) -> UInt64Constant:
        return const

    def visit_biguint_constant(self, const: BigUIntConstant) -> BigUIntConstant:
        return const

    def visit_bytes_constant(self, const: BytesConstant) -> BytesConstant:
        return const

    def visit_address_constant(self, const: AddressConstant) -> AddressConstant:
        return const

    def visit_method_constant(self, const: MethodConstant) -> MethodConstant:
        return const

    def visit_phi(self, phi: Phi) -> Phi | None:
        with self._enter_target_context():
            phi.register = self.visit_register(phi.register)
        phi.args = [self.visit_phi_argument(a) for a in phi.args]
        return phi

    def visit_phi_argument(self, arg: PhiArgument) -> PhiArgument:
        arg.value = arg.value.accept(self)
        return arg

    def visit_intrinsic_op(self, intrinsic: Intrinsic) -> Intrinsic | None:
        intrinsic.args = [a.accept(self) for a in intrinsic.args]
        return intrinsic

    def visit_invoke_subroutine(self, callsub: InvokeSubroutine) -> InvokeSubroutine:
        callsub.args = [a.accept(self) for a in callsub.args]
        return callsub

    def visit_conditional_branch(self, branch: ConditionalBranch) -> ControlOp:
        branch.condition = branch.condition.accept(self)
        return branch

    def visit_goto_nth(self, goto_nth: GotoNth) -> ControlOp:
        goto_nth.value = goto_nth.value.accept(self)
        return goto_nth

    def visit_goto(self, goto: Goto) -> ControlOp:
        return goto

    def visit_switch(self, switch: Switch) -> ControlOp:
        switch.value = switch.value.accept(self)
        switch.cases = {case.accept(self): target for case, target in switch.cases.items()}
        return switch

    def visit_subroutine_return(self, retsub: SubroutineReturn) -> ControlOp:
        retsub.result = [v.accept(self) for v in retsub.result]
        return retsub

    def visit_program_exit(self, exit_: ProgramExit) -> ControlOp:
        exit_.result = exit_.result.accept(self)
        return exit_

    def visit_fail(self, fail: Fail) -> ControlOp:
        return fail

    def visit_value_tuple(self, tup: ValueTuple) -> ValueTuple:
        tup.values = [v.accept(self) for v in tup.values]
        return tup
