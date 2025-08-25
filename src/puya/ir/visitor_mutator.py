import typing
from collections.abc import Sequence

import attrs

from puya.errors import InternalError
from puya.ir import models as ir
from puya.ir.visitor import IRVisitor


@attrs.define(kw_only=True)
class IRMutator(IRVisitor[typing.Any]):
    """
    Allows modifying IR blocks by implementing specific overrides that return
    replacement values.

    A return value of None indicates nothing is modified
    Phis cannot be replaced or removed, but can be modified during visitation
    ControlOps can be replaced but not removed
    Ops can be removed by using remove_op, this is only required there is not a direct replacement
    Ops can be inserted before the current op being visited using add_op
    Registers can be replaced via two overrides:
        visit_register_define will replace registers used in assignment and phi targets
        visit_register will allow replacements for register reads
    ValueProviders and Values can only be replaced
    """

    _inserted_ops: list[ir.Op] = attrs.field(factory=list, init=False)
    _removed_op: ir.Op | None = attrs.field(default=None, init=False)

    def add_op(self, op: ir.Op) -> None:
        self._inserted_ops.append(op)

    def remove_op(self, op: ir.Op) -> None:
        assert self._removed_op is None, "cannot remove op twice"
        self._removed_op = op

    def visit_block(self, block: ir.BasicBlock) -> None:
        for phi in block.phis:
            phi.accept(self)

        idx = 0
        ops = block.ops
        for op in ops.copy():
            maybe_replacement = op.accept(self)
            if self._inserted_ops:
                ops[idx:idx] = self._inserted_ops
                idx += len(self._inserted_ops)
                self._inserted_ops.clear()
            if op is self._removed_op:
                if maybe_replacement:
                    raise InternalError(
                        "don't need to remove an op if replacing", op.source_location
                    )
                ops.pop(idx)
                self._removed_op = None
                continue
            if self._removed_op:
                raise InternalError("Can only remove currently visited op", op.source_location)
            if maybe_replacement:
                ops[idx] = maybe_replacement
            idx += 1

        if block.terminator is not None:
            maybe_replacement = block.terminator.accept(self)
            if self._inserted_ops:
                ops[idx:idx] = self._inserted_ops
                idx += len(self._inserted_ops)
                self._inserted_ops.clear()
            if maybe_replacement:
                block.terminator = maybe_replacement

    def visit_sequence[T: ir.ValueProvider](self, seq: Sequence[T]) -> list[T] | None:
        new_seq = None
        for idx, value in enumerate(seq):
            if replacement := value.accept(self):
                if new_seq is None:
                    new_seq = list(seq)
                new_seq[idx] = replacement
        return new_seq

    def visit_register_define(self, reg: ir.Register) -> ir.Register | None:
        """Override to replace a register definition in assignment and phi nodes"""
        maybe_reg = self.visit_register(reg)
        if maybe_reg is not None and not isinstance(maybe_reg, ir.Register):
            raise InternalError(
                "can only replace register definitions with another register",
                reg.source_location,
            )
        return maybe_reg

    @typing.override
    def visit_phi(self, phi: ir.Phi) -> ir.Phi | None:
        if replacement := self.visit_register_define(phi.register):
            phi.register = replacement
        for arg in phi.args:
            arg.accept(self)
        return None

    @typing.override
    def visit_assignment(self, ass: ir.Assignment) -> ir.Assignment | None:
        replacement_targets = None
        for idx, target in enumerate(ass.targets):
            if replacement := self.visit_register_define(target):
                if replacement_targets is None:
                    replacement_targets = list(ass.targets)
                replacement_targets[idx] = replacement
        if replacement_targets:
            ass.targets = replacement_targets
        if replacement := ass.source.accept(self):
            ass.source = replacement
        return None

    @typing.override
    def visit_compiled_contract_reference(
        self, const: ir.CompiledContractReference
    ) -> ir.Value | None:
        template_variables = None
        for var, value in const.template_variables.items():
            if replacement := value.accept(self):
                if template_variables is None:
                    template_variables = dict(const.template_variables)
                template_variables[var] = replacement
        if template_variables is not None:
            return attrs.evolve(const, template_variables=template_variables)
        else:
            return None

    @typing.override
    def visit_compiled_logicsig_reference(
        self, const: ir.CompiledLogicSigReference
    ) -> ir.Value | None:
        template_variables = None
        for var, value in const.template_variables.items():
            if replacement := value.accept(self):
                if template_variables is None:
                    template_variables = dict(const.template_variables)
                template_variables[var] = replacement
        if template_variables is not None:
            return attrs.evolve(const, template_variables=template_variables)
        else:
            return None

    @typing.override
    def visit_read_slot(self, read: ir.ReadSlot) -> ir.ValueProvider | ir.Op | None:
        if replacement := read.slot.accept(self):
            read.slot = replacement
        return None

    @typing.override
    def visit_write_slot(self, write: ir.WriteSlot) -> ir.Op | None:
        if replacement := write.slot.accept(self):
            write.slot = replacement
        if replacement := write.value.accept(self):
            write.value = replacement
        return None

    @typing.override
    def visit_array_length(self, length: ir.ArrayLength) -> ir.ValueProvider | None:
        if replacement := length.base.accept(self):
            length.base = replacement
        return None

    @typing.override
    def visit_extract_value(self, read: ir.ExtractValue) -> ir.ValueProvider | None:
        if replacement := read.base.accept(self):
            read.base = replacement
        indexes = None
        for idx, index in enumerate(read.indexes):
            if isinstance(index, ir.Value) and (replacement := index.accept(self)):
                if indexes is None:
                    indexes = list(read.indexes)
                indexes[idx] = replacement
        if indexes is not None:
            read.indexes = tuple(indexes)
        return None

    @typing.override
    def visit_replace_value(self, write: ir.ReplaceValue) -> ir.ValueProvider | None:
        if replacement := write.base.accept(self):
            write.base = replacement
        indexes = None
        for idx, index in enumerate(write.indexes):
            if isinstance(index, ir.Value) and (replacement := index.accept(self)):
                if indexes is None:
                    indexes = list(write.indexes)
                indexes[idx] = replacement
        if indexes is not None:
            write.indexes = tuple(indexes)
        if replacement := write.value.accept(self):
            write.value = replacement
        return None

    @typing.override
    def visit_box_read(self, read: ir.BoxRead) -> ir.ValueProvider | None:
        if replacement := read.key.accept(self):
            read.key = replacement
        return None

    @typing.override
    def visit_box_write(self, write: ir.BoxWrite) -> ir.Op | None:
        if replacement := write.key.accept(self):
            write.key = replacement
        if replacement := write.value.accept(self):
            write.value = replacement
        return None

    @typing.override
    def visit_bytes_encode(self, encode: ir.BytesEncode) -> ir.ValueProvider | None:
        if replacement := self.visit_sequence(encode.values):
            encode.values = replacement
        return None

    @typing.override
    def visit_decode_bytes(self, decode: ir.DecodeBytes) -> ir.ValueProvider | None:
        if replacement := decode.value.accept(self):
            decode.value = replacement
        return None

    @typing.override
    def visit_intrinsic_op(self, intrinsic: ir.Intrinsic) -> ir.ValueProvider | ir.Op | None:
        if replacement := self.visit_sequence(intrinsic.args):
            intrinsic.args = replacement
        return None

    @typing.override
    def visit_inner_transaction_field(
        self, field: ir.InnerTransactionField
    ) -> ir.ValueProvider | None:
        if replacement := field.group_index.accept(self):
            field.group_index = replacement
        if replacement := field.is_last_in_group.accept(self):
            field.is_last_in_group = replacement
        if field.array_index and (replacement := field.array_index.accept(self)):
            field.array_index = replacement
        return None

    @typing.override
    def visit_invoke_subroutine(
        self, callsub: ir.InvokeSubroutine
    ) -> ir.ValueProvider | ir.Op | None:
        if replacement := self.visit_sequence(callsub.args):
            callsub.args = replacement
        return None

    @typing.override
    def visit_conditional_branch(self, branch: ir.ConditionalBranch) -> ir.ControlOp | None:
        if replacement := branch.condition.accept(self):
            branch.condition = replacement
        return None

    @typing.override
    def visit_goto_nth(self, goto_nth: ir.GotoNth) -> ir.ControlOp | None:
        if replacement := goto_nth.value.accept(self):
            goto_nth.value = replacement
        return None

    @typing.override
    def visit_switch(self, switch: ir.Switch) -> ir.ControlOp | None:
        if replacement := switch.value.accept(self):
            switch.value = replacement

        cases = switch.cases
        for value in list(cases):
            if replacement := value.accept(self):
                cases[replacement] = cases.pop(value)
        return None

    @typing.override
    def visit_subroutine_return(self, retsub: ir.SubroutineReturn) -> ir.ControlOp | None:
        if replacement := self.visit_sequence(retsub.result):
            retsub.result = replacement
        return None

    @typing.override
    def visit_program_exit(self, exit_: ir.ProgramExit) -> ir.ControlOp | None:
        if replacement := exit_.result.accept(self):
            exit_.result = replacement
        return None

    @typing.override
    def visit_goto(self, goto: ir.Goto) -> ir.ControlOp | None:
        pass

    @typing.override
    def visit_fail(self, fail: ir.Fail) -> ir.ControlOp | None:
        pass

    @typing.override
    def visit_value_tuple(self, tup: ir.ValueTuple) -> ir.ValueProvider | None:
        if replacement := self.visit_sequence(tup.values):
            tup.values = replacement
        return None

    @typing.override
    def visit_phi_argument(self, arg: ir.PhiArgument) -> None:
        if replacement := self.visit_register(arg.value):
            if not isinstance(replacement, ir.Register):
                raise InternalError(
                    "cannot replace phi arg with non register value", arg.value.source_location
                )
            arg.value = replacement

    @typing.override
    def visit_register(self, reg: ir.Register) -> ir.Value | None:
        """override this to replace register usage, not definitions"""

    @typing.override
    def visit_undefined(self, val: ir.Undefined) -> ir.Value | None:
        pass

    @typing.override
    def visit_uint64_constant(self, const: ir.UInt64Constant) -> ir.Value | None:
        pass

    @typing.override
    def visit_biguint_constant(self, const: ir.BigUIntConstant) -> ir.Value | None:
        pass

    @typing.override
    def visit_bytes_constant(self, const: ir.BytesConstant) -> ir.Value | None:
        pass

    @typing.override
    def visit_address_constant(self, const: ir.AddressConstant) -> ir.Value | None:
        pass

    @typing.override
    def visit_method_constant(self, const: ir.MethodConstant) -> ir.Value | None:
        pass

    @typing.override
    def visit_itxn_constant(self, const: ir.ITxnConstant) -> ir.Value | None:
        pass

    @typing.override
    def visit_slot_constant(self, const: ir.SlotConstant) -> ir.Value | None:
        pass

    @typing.override
    def visit_new_slot(self, new_slot: ir.NewSlot) -> ir.ValueProvider | ir.Op | None:
        pass

    @typing.override
    def visit_template_var(self, deploy_var: ir.TemplateVar) -> ir.Value | None:
        pass
