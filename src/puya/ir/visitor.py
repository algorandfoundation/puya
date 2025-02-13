# ruff: noqa: ARG002

from __future__ import annotations  # needed to break import cycle

import typing as t
from abc import ABC, abstractmethod

if t.TYPE_CHECKING:
    from collections.abc import Iterable

    import puya.ir.models


class IRVisitor[T](ABC):
    @abstractmethod
    def visit_assignment(self, ass: puya.ir.models.Assignment) -> T: ...

    @abstractmethod
    def visit_register(self, reg: puya.ir.models.Register) -> T: ...

    @abstractmethod
    def visit_undefined(self, val: puya.ir.models.Undefined) -> T: ...

    @abstractmethod
    def visit_uint64_constant(self, const: puya.ir.models.UInt64Constant) -> T: ...

    @abstractmethod
    def visit_biguint_constant(self, const: puya.ir.models.BigUIntConstant) -> T: ...

    @abstractmethod
    def visit_bytes_constant(self, const: puya.ir.models.BytesConstant) -> T: ...

    @abstractmethod
    def visit_compiled_contract_reference(
        self, const: puya.ir.models.CompiledContractReference
    ) -> T: ...

    @abstractmethod
    def visit_compiled_logicsig_reference(
        self, const: puya.ir.models.CompiledLogicSigReference
    ) -> T: ...

    @abstractmethod
    def visit_address_constant(self, const: puya.ir.models.AddressConstant) -> T: ...

    @abstractmethod
    def visit_method_constant(self, const: puya.ir.models.MethodConstant) -> T: ...

    @abstractmethod
    def visit_itxn_constant(self, const: puya.ir.models.ITxnConstant) -> T: ...

    @abstractmethod
    def visit_slot_constant(self, const: puya.ir.models.SlotConstant) -> T: ...

    @abstractmethod
    def visit_phi(self, phi: puya.ir.models.Phi) -> T: ...

    @abstractmethod
    def visit_phi_argument(self, arg: puya.ir.models.PhiArgument) -> T: ...

    @abstractmethod
    def visit_intrinsic_op(self, intrinsic: puya.ir.models.Intrinsic) -> T: ...

    @abstractmethod
    def visit_inner_transaction_field(
        self, intrinsic: puya.ir.models.InnerTransactionField
    ) -> T: ...

    @abstractmethod
    def visit_new_slot(self, new_slot: puya.ir.models.NewSlot) -> T: ...

    @abstractmethod
    def visit_read_slot(self, read_slot: puya.ir.models.ReadSlot) -> T: ...

    @abstractmethod
    def visit_write_slot(self, write_slot: puya.ir.models.WriteSlot) -> T: ...

    @abstractmethod
    def visit_array_read_index(self, read: puya.ir.models.ArrayReadIndex) -> T: ...

    @abstractmethod
    def visit_array_write_index(self, write: puya.ir.models.ArrayWriteIndex) -> T: ...

    @abstractmethod
    def visit_array_concat(self, concat: puya.ir.models.ArrayConcat) -> T: ...

    @abstractmethod
    def visit_array_encode(self, concat: puya.ir.models.ArrayEncode) -> T: ...
    @abstractmethod
    def visit_array_pop(self, pop: puya.ir.models.ArrayPop) -> T: ...

    @abstractmethod
    def visit_array_length(self, pop: puya.ir.models.ArrayLength) -> T: ...

    @abstractmethod
    def visit_invoke_subroutine(self, callsub: puya.ir.models.InvokeSubroutine) -> T: ...

    @abstractmethod
    def visit_value_tuple(self, tup: puya.ir.models.ValueTuple) -> T: ...

    @abstractmethod
    def visit_conditional_branch(self, branch: puya.ir.models.ConditionalBranch) -> T: ...

    @abstractmethod
    def visit_goto(self, goto: puya.ir.models.Goto) -> T: ...

    @abstractmethod
    def visit_goto_nth(self, goto_nth: puya.ir.models.GotoNth) -> T: ...

    @abstractmethod
    def visit_switch(self, switch: puya.ir.models.Switch) -> T: ...

    @abstractmethod
    def visit_subroutine_return(self, retsub: puya.ir.models.SubroutineReturn) -> T: ...

    @abstractmethod
    def visit_program_exit(self, exit_: puya.ir.models.ProgramExit) -> T: ...

    @abstractmethod
    def visit_fail(self, fail: puya.ir.models.Fail) -> T: ...

    @abstractmethod
    def visit_template_var(self, deploy_var: puya.ir.models.TemplateVar) -> T: ...


class IRTraverser(IRVisitor[None]):
    def visit_all_blocks(self, blocks: Iterable[puya.ir.models.BasicBlock]) -> None:
        for block in blocks:
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

    def visit_undefined(self, val: puya.ir.models.Undefined) -> None:
        pass

    def visit_uint64_constant(self, const: puya.ir.models.UInt64Constant) -> None:
        pass

    def visit_biguint_constant(self, const: puya.ir.models.BigUIntConstant) -> None:
        pass

    def visit_bytes_constant(self, const: puya.ir.models.BytesConstant) -> None:
        pass

    def visit_address_constant(self, const: puya.ir.models.AddressConstant) -> None:
        pass

    def visit_template_var(self, deploy_var: puya.ir.models.TemplateVar) -> None:
        pass

    def visit_method_constant(self, const: puya.ir.models.MethodConstant) -> None:
        pass

    def visit_slot_constant(self, const: puya.ir.models.SlotConstant) -> None:
        pass

    def visit_compiled_contract_reference(
        self, const: puya.ir.models.CompiledContractReference
    ) -> None:
        for var in const.template_variables.values():
            var.accept(self)

    def visit_compiled_logicsig_reference(
        self, const: puya.ir.models.CompiledLogicSigReference
    ) -> None:
        for var in const.template_variables.values():
            var.accept(self)

    def visit_new_slot(self, _: puya.ir.models.NewSlot) -> None:
        pass

    def visit_read_slot(self, read: puya.ir.models.ReadSlot) -> None:
        read.slot.accept(self)

    def visit_write_slot(self, write: puya.ir.models.WriteSlot) -> None:
        write.slot.accept(self)
        write.value.accept(self)

    def visit_array_read_index(self, read: puya.ir.models.ArrayReadIndex) -> None:
        read.array.accept(self)
        read.index.accept(self)

    def visit_array_write_index(self, write: puya.ir.models.ArrayWriteIndex) -> None:
        write.array.accept(self)
        write.index.accept(self)
        write.value.accept(self)

    def visit_array_concat(self, concat: puya.ir.models.ArrayConcat) -> None:
        concat.array.accept(self)
        concat.other.accept(self)

    def visit_array_encode(self, encode: puya.ir.models.ArrayEncode) -> None:
        for value in encode.values:
            value.accept(self)

    def visit_array_pop(self, pop: puya.ir.models.ArrayPop) -> None:
        pop.array.accept(self)

    def visit_array_length(self, length: puya.ir.models.ArrayLength) -> None:
        length.array.accept(self)

    def visit_itxn_constant(self, const: puya.ir.models.ITxnConstant) -> None:
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

    def visit_inner_transaction_field(self, field: puya.ir.models.InnerTransactionField) -> None:
        field.group_index.accept(self)
        field.is_last_in_group.accept(self)
        if field.array_index:
            field.array_index.accept(self)

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


class NoOpIRVisitor[T](IRVisitor[T | None]):
    def visit_assignment(self, ass: puya.ir.models.Assignment) -> T | None:
        return None

    def visit_register(self, reg: puya.ir.models.Register) -> T | None:
        return None

    def visit_undefined(self, val: puya.ir.models.Undefined) -> T | None:
        return None

    def visit_uint64_constant(self, const: puya.ir.models.UInt64Constant) -> T | None:
        return None

    def visit_biguint_constant(self, const: puya.ir.models.BigUIntConstant) -> T | None:
        return None

    def visit_bytes_constant(self, const: puya.ir.models.BytesConstant) -> T | None:
        return None

    def visit_address_constant(self, const: puya.ir.models.AddressConstant) -> T | None:
        return None

    def visit_method_constant(self, const: puya.ir.models.MethodConstant) -> T | None:
        return None

    def visit_itxn_constant(self, const: puya.ir.models.ITxnConstant) -> T | None:
        return None

    def visit_slot_constant(self, const: puya.ir.models.SlotConstant) -> T | None:
        return None

    def visit_compiled_contract_reference(
        self, const: puya.ir.models.CompiledContractReference
    ) -> T | None:
        return None

    def visit_compiled_logicsig_reference(
        self, const: puya.ir.models.CompiledLogicSigReference
    ) -> T | None:
        return None

    def visit_new_slot(self, new_slot: puya.ir.models.NewSlot) -> T | None:
        return None

    def visit_read_slot(self, read: puya.ir.models.ReadSlot) -> T | None:
        return None

    def visit_write_slot(self, write: puya.ir.models.WriteSlot) -> T | None:
        return None

    def visit_array_read_index(self, read: puya.ir.models.ArrayReadIndex) -> T | None:
        return None

    def visit_array_write_index(self, write: puya.ir.models.ArrayWriteIndex) -> T | None:
        return None

    def visit_array_concat(self, concat: puya.ir.models.ArrayConcat) -> T | None:
        return None

    def visit_array_encode(self, extend: puya.ir.models.ArrayEncode) -> T | None:
        return None

    def visit_array_pop(self, write: puya.ir.models.ArrayPop) -> T | None:
        return None

    def visit_array_length(self, write: puya.ir.models.ArrayLength) -> T | None:
        return None

    def visit_phi(self, phi: puya.ir.models.Phi) -> T | None:
        return None

    def visit_template_var(self, deploy_var: puya.ir.models.TemplateVar) -> T | None:
        return None

    def visit_phi_argument(self, arg: puya.ir.models.PhiArgument) -> T | None:
        return None

    def visit_intrinsic_op(self, intrinsic: puya.ir.models.Intrinsic) -> T | None:
        return None

    def visit_inner_transaction_field(
        self, field: puya.ir.models.InnerTransactionField
    ) -> T | None:
        return None

    def visit_invoke_subroutine(self, callsub: puya.ir.models.InvokeSubroutine) -> T | None:
        return None

    def visit_value_tuple(self, tup: puya.ir.models.ValueTuple) -> T | None:
        return None

    def visit_conditional_branch(self, branch: puya.ir.models.ConditionalBranch) -> T | None:
        return None

    def visit_goto(self, goto: puya.ir.models.Goto) -> T | None:
        return None

    def visit_goto_nth(self, goto_nth: puya.ir.models.GotoNth) -> T | None:
        return None

    def visit_switch(self, switch: puya.ir.models.Switch) -> T | None:
        return None

    def visit_subroutine_return(self, retsub: puya.ir.models.SubroutineReturn) -> T | None:
        return None

    def visit_program_exit(self, exit_: puya.ir.models.ProgramExit) -> T | None:
        return None

    def visit_fail(self, fail: puya.ir.models.Fail) -> T | None:
        return None
