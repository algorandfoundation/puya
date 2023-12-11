from __future__ import annotations  # needed to break import cycle

import typing as t
from abc import ABC, abstractmethod

if t.TYPE_CHECKING:
    from collections.abc import Iterable

    import puya.ir.models

T = t.TypeVar("T")


class IRVisitor(t.Generic[T], ABC):
    @abstractmethod
    def visit_assignment(self, ass: puya.ir.models.Assignment) -> T:
        ...

    @abstractmethod
    def visit_register(self, reg: puya.ir.models.Register) -> T:
        ...

    @abstractmethod
    def visit_uint64_constant(self, const: puya.ir.models.UInt64Constant) -> T:
        ...

    @abstractmethod
    def visit_biguint_constant(self, const: puya.ir.models.BigUIntConstant) -> T:
        ...

    @abstractmethod
    def visit_bytes_constant(self, const: puya.ir.models.BytesConstant) -> T:
        ...

    @abstractmethod
    def visit_address_constant(self, const: puya.ir.models.AddressConstant) -> T:
        ...

    @abstractmethod
    def visit_method_constant(self, const: puya.ir.models.MethodConstant) -> T:
        ...

    @abstractmethod
    def visit_phi(self, phi: puya.ir.models.Phi) -> T:
        ...

    @abstractmethod
    def visit_phi_argument(self, arg: puya.ir.models.PhiArgument) -> T:
        ...

    @abstractmethod
    def visit_intrinsic_op(self, intrinsic: puya.ir.models.Intrinsic) -> T:
        ...

    @abstractmethod
    def visit_invoke_subroutine(self, callsub: puya.ir.models.InvokeSubroutine) -> T:
        ...

    @abstractmethod
    def visit_value_tuple(self, tup: puya.ir.models.ValueTuple) -> T:
        ...

    @abstractmethod
    def visit_conditional_branch(self, branch: puya.ir.models.ConditionalBranch) -> T:
        ...

    @abstractmethod
    def visit_goto(self, goto: puya.ir.models.Goto) -> T:
        ...

    @abstractmethod
    def visit_goto_nth(self, goto_nth: puya.ir.models.GotoNth) -> T:
        ...

    @abstractmethod
    def visit_switch(self, switch: puya.ir.models.Switch) -> T:
        ...

    @abstractmethod
    def visit_subroutine_return(self, retsub: puya.ir.models.SubroutineReturn) -> T:
        ...

    @abstractmethod
    def visit_program_exit(self, exit_: puya.ir.models.ProgramExit) -> T:
        ...

    @abstractmethod
    def visit_fail(self, fail: puya.ir.models.Fail) -> T:
        ...


class IRTraverser(IRVisitor[None]):
    active_block: puya.ir.models.BasicBlock

    def visit_all_blocks(self, blocks: Iterable[puya.ir.models.BasicBlock]) -> None:
        for block in blocks:
            self.active_block = block
            self.visit_block(block)

    def visit_block(self, block: puya.ir.models.BasicBlock) -> None:
        for op in list(block.all_ops):  # make a copy in case visitors need to modify ops
            op.accept(self)

    def visit_assignment(self, ass: puya.ir.models.Assignment) -> None:
        for target in ass.targets:
            target.accept(self)
        ass.source.accept(self)

    def visit_register(self, reg: puya.ir.models.Register) -> None:
        pass

    def visit_uint64_constant(self, const: puya.ir.models.UInt64Constant) -> None:
        pass

    def visit_biguint_constant(self, const: puya.ir.models.BigUIntConstant) -> None:
        pass

    def visit_bytes_constant(self, const: puya.ir.models.BytesConstant) -> None:
        pass

    def visit_address_constant(self, const: puya.ir.models.AddressConstant) -> None:
        pass

    def visit_method_constant(self, const: puya.ir.models.MethodConstant) -> None:
        pass

    def visit_phi(self, phi: puya.ir.models.Phi) -> None:
        phi.register.accept(self)
        for arg in phi.args:
            arg.accept(self)

    def visit_phi_argument(self, arg: puya.ir.models.PhiArgument) -> None:
        arg.value.accept(self)

    def visit_intrinsic_op(self, intrinsic: puya.ir.models.Intrinsic) -> None:
        for arg in intrinsic.args:
            arg.accept(self)

    def visit_invoke_subroutine(self, callsub: puya.ir.models.InvokeSubroutine) -> None:
        for arg in callsub.args:
            arg.accept(self)

    def visit_conditional_branch(self, branch: puya.ir.models.ConditionalBranch) -> None:
        branch.condition.accept(self)

    def visit_goto(self, goto: puya.ir.models.Goto) -> None:
        pass

    def visit_goto_nth(self, goto_nth: puya.ir.models.GotoNth) -> None:
        goto_nth.value.accept(self)

    def visit_switch(self, switch: puya.ir.models.Switch) -> None:
        switch.value.accept(self)
        for case in switch.cases:
            case.accept(self)

    def visit_subroutine_return(self, retsub: puya.ir.models.SubroutineReturn) -> None:
        for r in retsub.result:
            r.accept(self)

    def visit_program_exit(self, exit_: puya.ir.models.ProgramExit) -> None:
        exit_.result.accept(self)

    def visit_fail(self, fail: puya.ir.models.Fail) -> None:
        pass

    def visit_value_tuple(self, tup: puya.ir.models.ValueTuple) -> None:
        for v in tup.values:
            v.accept(self)
