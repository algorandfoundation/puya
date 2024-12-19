import typing as t

import attrs

from puya.ir import models
from puya.ir.visitor import IRVisitor


@attrs.define
class IRMutator(IRVisitor[t.Any]):
    def visit_block(self, block: models.BasicBlock) -> None:
        new_phis = []
        for phi in block.phis:
            new_phi = self.visit_phi(phi)
            if new_phi is not None:
                new_phis.append(new_phi)
        block.phis = new_phis
        new_ops = []
        for op in block.ops:
            new_op = op.accept(self)
            if new_op is not None:
                new_ops.append(new_op)
        block.ops = new_ops
        if block.terminator is not None:
            block.terminator = block.terminator.accept(self)

    def visit_assignment(self, ass: models.Assignment) -> models.Assignment | None:
        ass.targets = [self.visit_register(r) for r in ass.targets]
        ass.source = ass.source.accept(self)
        return ass

    def visit_register(self, reg: models.Register) -> models.Register:
        return reg

    def visit_undefined(self, val: models.Undefined) -> models.Undefined:
        return val

    def visit_template_var(self, deploy_var: models.TemplateVar) -> models.TemplateVar:
        return deploy_var

    def visit_uint64_constant(self, const: models.UInt64Constant) -> models.UInt64Constant:
        return const

    def visit_biguint_constant(self, const: models.BigUIntConstant) -> models.BigUIntConstant:
        return const

    def visit_bytes_constant(self, const: models.BytesConstant) -> models.BytesConstant:
        return const

    def visit_address_constant(self, const: models.AddressConstant) -> models.AddressConstant:
        return const

    def visit_method_constant(self, const: models.MethodConstant) -> models.MethodConstant:
        return const

    def visit_itxn_constant(self, const: models.ITxnConstant) -> models.ITxnConstant:
        return const

    def visit_compiled_contract_reference(
        self, const: models.CompiledContractReference
    ) -> models.CompiledContractReference:
        return attrs.evolve(
            const,
            template_variables={
                var: value.accept(self) for var, value in const.template_variables.items()
            },
        )

    def visit_compiled_logicsig_reference(
        self, const: models.CompiledLogicSigReference
    ) -> models.CompiledLogicSigReference:
        return attrs.evolve(
            const,
            template_variables={
                var: value.accept(self) for var, value in const.template_variables.items()
            },
        )

    def visit_phi(self, phi: models.Phi) -> models.Phi | None:
        phi.register = self.visit_register(phi.register)
        phi.args = [self.visit_phi_argument(a) for a in phi.args]
        return phi

    def visit_phi_argument(self, arg: models.PhiArgument) -> models.PhiArgument:
        arg.value = arg.value.accept(self)
        return arg

    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> models.Intrinsic | None:
        intrinsic.args = [a.accept(self) for a in intrinsic.args]
        return intrinsic

    def visit_inner_transaction_field(
        self, field: models.InnerTransactionField
    ) -> models.InnerTransactionField | models.Intrinsic:
        field.group_index = field.group_index.accept(self)
        field.is_last_in_group = field.is_last_in_group.accept(self)
        if field.array_index:
            field.array_index = field.array_index.accept(self)
        return field

    def visit_invoke_subroutine(self, callsub: models.InvokeSubroutine) -> models.InvokeSubroutine:
        callsub.args = [a.accept(self) for a in callsub.args]
        return callsub

    def visit_conditional_branch(self, branch: models.ConditionalBranch) -> models.ControlOp:
        branch.condition = branch.condition.accept(self)
        return branch

    def visit_goto_nth(self, goto_nth: models.GotoNth) -> models.ControlOp:
        goto_nth.value = goto_nth.value.accept(self)
        return goto_nth

    def visit_goto(self, goto: models.Goto) -> models.ControlOp:
        return goto

    def visit_switch(self, switch: models.Switch) -> models.ControlOp:
        switch.value = switch.value.accept(self)
        switch.cases = {case.accept(self): target for case, target in switch.cases.items()}
        return switch

    def visit_subroutine_return(self, retsub: models.SubroutineReturn) -> models.ControlOp:
        retsub.result = [v.accept(self) for v in retsub.result]
        return retsub

    def visit_program_exit(self, exit_: models.ProgramExit) -> models.ControlOp:
        exit_.result = exit_.result.accept(self)
        return exit_

    def visit_fail(self, fail: models.Fail) -> models.ControlOp:
        return fail

    def visit_value_tuple(self, tup: models.ValueTuple) -> models.ValueTuple:
        tup.values = [v.accept(self) for v in tup.values]
        return tup
