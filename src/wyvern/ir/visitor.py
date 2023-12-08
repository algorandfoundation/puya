from __future__ import annotations  # needed to break import cycle

import typing as t
from abc import ABC, abstractmethod

if t.TYPE_CHECKING:
    from collections.abc import Iterable

    import wyvern.ir.models

T = t.TypeVar("T")


class IRVisitor(t.Generic[T], ABC):
    @abstractmethod
    def visit_assignment(self, ass: wyvern.ir.models.Assignment) -> T:
        ...

    @abstractmethod
    def visit_register(self, reg: wyvern.ir.models.Register) -> T:
        ...

    @abstractmethod
    def visit_uint64_constant(self, const: wyvern.ir.models.UInt64Constant) -> T:
        ...

    @abstractmethod
    def visit_biguint_constant(self, const: wyvern.ir.models.BigUIntConstant) -> T:
        ...

    @abstractmethod
    def visit_bytes_constant(self, const: wyvern.ir.models.BytesConstant) -> T:
        ...

    @abstractmethod
    def visit_address_constant(self, const: wyvern.ir.models.AddressConstant) -> T:
        ...

    @abstractmethod
    def visit_method_constant(self, const: wyvern.ir.models.MethodConstant) -> T:
        ...

    @abstractmethod
    def visit_phi(self, phi: wyvern.ir.models.Phi) -> T:
        ...

    @abstractmethod
    def visit_phi_argument(self, arg: wyvern.ir.models.PhiArgument) -> T:
        ...

    @abstractmethod
    def visit_intrinsic_op(self, intrinsic: wyvern.ir.models.Intrinsic) -> T:
        ...

    @abstractmethod
    def visit_invoke_subroutine(self, callsub: wyvern.ir.models.InvokeSubroutine) -> T:
        ...

    @abstractmethod
    def visit_value_tuple(self, tup: wyvern.ir.models.ValueTuple) -> T:
        ...

    @abstractmethod
    def visit_conditional_branch(self, branch: wyvern.ir.models.ConditionalBranch) -> T:
        ...

    @abstractmethod
    def visit_goto(self, goto: wyvern.ir.models.Goto) -> T:
        ...

    @abstractmethod
    def visit_goto_nth(self, goto_nth: wyvern.ir.models.GotoNth) -> T:
        ...

    @abstractmethod
    def visit_switch(self, switch: wyvern.ir.models.Switch) -> T:
        ...

    @abstractmethod
    def visit_subroutine_return(self, retsub: wyvern.ir.models.SubroutineReturn) -> T:
        ...

    @abstractmethod
    def visit_program_exit(self, exit_: wyvern.ir.models.ProgramExit) -> T:
        ...

    @abstractmethod
    def visit_fail(self, fail: wyvern.ir.models.Fail) -> T:
        ...


class IRTraverser(IRVisitor[None]):
    active_block: wyvern.ir.models.BasicBlock

    def visit_all_blocks(self, blocks: Iterable[wyvern.ir.models.BasicBlock]) -> None:
        for block in blocks:
            self.active_block = block
            self.visit_block(block)

    def visit_block(self, block: wyvern.ir.models.BasicBlock) -> None:
        for op in list(block.all_ops):  # make a copy in case visitors need to modify ops
            op.accept(self)

    def visit_assignment(self, ass: wyvern.ir.models.Assignment) -> None:
        for target in ass.targets:
            target.accept(self)
        ass.source.accept(self)

    def visit_register(self, reg: wyvern.ir.models.Register) -> None:
        pass

    def visit_uint64_constant(self, const: wyvern.ir.models.UInt64Constant) -> None:
        pass

    def visit_biguint_constant(self, const: wyvern.ir.models.BigUIntConstant) -> None:
        pass

    def visit_bytes_constant(self, const: wyvern.ir.models.BytesConstant) -> None:
        pass

    def visit_address_constant(self, const: wyvern.ir.models.AddressConstant) -> None:
        pass

    def visit_method_constant(self, const: wyvern.ir.models.MethodConstant) -> None:
        pass

    def visit_phi(self, phi: wyvern.ir.models.Phi) -> None:
        phi.register.accept(self)
        for arg in phi.args:
            arg.accept(self)

    def visit_phi_argument(self, arg: wyvern.ir.models.PhiArgument) -> None:
        arg.value.accept(self)

    def visit_intrinsic_op(self, intrinsic: wyvern.ir.models.Intrinsic) -> None:
        for arg in intrinsic.args:
            arg.accept(self)

    def visit_invoke_subroutine(self, callsub: wyvern.ir.models.InvokeSubroutine) -> None:
        for arg in callsub.args:
            arg.accept(self)

    def visit_conditional_branch(self, branch: wyvern.ir.models.ConditionalBranch) -> None:
        branch.condition.accept(self)

    def visit_goto(self, goto: wyvern.ir.models.Goto) -> None:
        pass

    def visit_goto_nth(self, goto_nth: wyvern.ir.models.GotoNth) -> None:
        goto_nth.value.accept(self)

    def visit_switch(self, switch: wyvern.ir.models.Switch) -> None:
        switch.value.accept(self)
        for case in switch.cases:
            case.accept(self)

    def visit_subroutine_return(self, retsub: wyvern.ir.models.SubroutineReturn) -> None:
        for r in retsub.result:
            r.accept(self)

    def visit_program_exit(self, exit_: wyvern.ir.models.ProgramExit) -> None:
        exit_.result.accept(self)

    def visit_fail(self, fail: wyvern.ir.models.Fail) -> None:
        pass

    def visit_value_tuple(self, tup: wyvern.ir.models.ValueTuple) -> None:
        for v in tup.values:
            v.accept(self)
