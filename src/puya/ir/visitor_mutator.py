import typing as t

import attrs

from puya.ir.models import (
    AddressConstant,
    ArrayExtend,
    ArrayLength,
    ArrayPop,
    ArrayReadIndex,
    ArrayWriteIndex,
    Assignment,
    BasicBlock,
    BigUIntConstant,
    BytesConstant,
    CompiledContractReference,
    CompiledLogicSigReference,
    ConditionalBranch,
    ControlOp,
    Fail,
    Goto,
    GotoNth,
    InnerTransactionField,
    Intrinsic,
    InvokeSubroutine,
    ITxnConstant,
    MethodConstant,
    NewSlot,
    Op,
    Phi,
    PhiArgument,
    ProgramExit,
    ReadSlot,
    Register,
    SlotConstant,
    SubroutineReturn,
    Switch,
    TemplateVar,
    UInt64Constant,
    Undefined,
    ValueProvider,
    ValueTuple,
    WriteSlot,
)
from puya.ir.visitor import IRVisitor


@attrs.define
class IRMutator(IRVisitor[t.Any]):
    _current_block_ops: list[Op] | None = attrs.field(default=None, init=False)

    @property
    def current_block_ops(self) -> list[Op]:
        assert self._current_block_ops is not None
        return self._current_block_ops

    def visit_block(self, block: BasicBlock) -> None:
        new_phis = []
        for phi in block.phis:
            new_phi = self.visit_phi(phi)
            if new_phi is not None:
                new_phis.append(new_phi)
        block.phis = new_phis
        self._current_block_ops = new_ops = []
        for op in block.ops:
            new_op = op.accept(self)
            if new_op is not None:
                new_ops.append(new_op)
        self._current_block_ops = None
        block.ops = new_ops
        if block.terminator is not None:
            block.terminator = block.terminator.accept(self)

    def visit_assignment(self, ass: Assignment) -> Assignment | None:
        ass.targets = [self.visit_register(r) for r in ass.targets]
        ass.source = ass.source.accept(self)
        return ass

    def visit_register(self, reg: Register) -> Register:
        return reg

    def visit_undefined(self, val: Undefined) -> Undefined:
        return val

    def visit_template_var(self, deploy_var: TemplateVar) -> TemplateVar:
        return deploy_var

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

    def visit_itxn_constant(self, const: ITxnConstant) -> ITxnConstant:
        return const

    def visit_slot_constant(self, const: SlotConstant) -> SlotConstant:
        return const

    def visit_compiled_contract_reference(
        self, const: CompiledContractReference
    ) -> CompiledContractReference:
        return attrs.evolve(
            const,
            template_variables={
                var: value.accept(self) for var, value in const.template_variables.items()
            },
        )

    def visit_compiled_logicsig_reference(
        self, const: CompiledLogicSigReference
    ) -> CompiledLogicSigReference:
        return attrs.evolve(
            const,
            template_variables={
                var: value.accept(self) for var, value in const.template_variables.items()
            },
        )

    def visit_new_slot(self, new_slot: NewSlot) -> NewSlot:
        return new_slot

    def visit_read_slot(self, read: ReadSlot) -> ReadSlot:
        return attrs.evolve(read, slot=read.slot.accept(self))

    def visit_write_slot(self, write: WriteSlot) -> WriteSlot:
        return attrs.evolve(write, slot=write.slot.accept(self), value=write.value.accept(self))

    def visit_array_read_index(self, read: ArrayReadIndex) -> ArrayReadIndex | ValueProvider:
        return attrs.evolve(read, array=read.array.accept(self), index=read.index.accept(self))

    def visit_array_write_index(self, write: ArrayWriteIndex) -> ArrayWriteIndex | ValueProvider:
        return attrs.evolve(
            write,
            array=write.array.accept(self),
            index=write.index.accept(self),
            value=write.value.accept(self),
        )

    def visit_array_extend(self, append: ArrayExtend) -> ArrayExtend | ValueProvider:
        return attrs.evolve(
            append,
            array=append.array.accept(self),
            values=append.values.accept(self),
        )

    def visit_array_pop(self, pop: ArrayPop) -> ArrayPop | ValueProvider:
        return attrs.evolve(
            pop,
            array=pop.array.accept(self),
        )

    def visit_array_length(self, length: ArrayLength) -> ArrayLength | ValueProvider:
        return attrs.evolve(
            length,
            array=length.array.accept(self),
        )

    def visit_phi(self, phi: Phi) -> Phi | None:
        phi.register = self.visit_register(phi.register)
        phi.args = [self.visit_phi_argument(a) for a in phi.args]
        return phi

    def visit_phi_argument(self, arg: PhiArgument) -> PhiArgument:
        arg.value = arg.value.accept(self)
        return arg

    def visit_intrinsic_op(self, intrinsic: Intrinsic) -> Intrinsic | None:
        intrinsic.args = [a.accept(self) for a in intrinsic.args]
        return intrinsic

    def visit_inner_transaction_field(
        self, field: InnerTransactionField
    ) -> InnerTransactionField | Intrinsic:
        field.group_index = field.group_index.accept(self)
        field.is_last_in_group = field.is_last_in_group.accept(self)
        if field.array_index:
            field.array_index = field.array_index.accept(self)
        return field

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
