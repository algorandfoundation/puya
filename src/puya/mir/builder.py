from math import ceil

import attrs
import structlog

from puya.errors import CodeError, InternalError
from puya.ir import models as ir
from puya.ir.types_ import AVMBytesEncoding
from puya.ir.visitor import IRVisitor
from puya.mir import models
from puya.mir.context import ProgramCodeGenContext

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(__name__)


@attrs.define
class MemoryIRBuilder(IRVisitor[None]):
    context: ProgramCodeGenContext = attrs.field(on_setattr=attrs.setters.frozen)
    current_subroutine: ir.Subroutine
    is_main: bool
    current_ops: list[models.BaseOp] = attrs.field(factory=list)
    active_op: ir.Op | ir.ControlOp | None = None
    next_block: ir.BasicBlock | None = None

    def _add_op(self, op: models.BaseOp) -> None:
        self.current_ops.append(op)

    def _get_block_name(self, block: ir.BasicBlock) -> str:
        assert block in self.current_subroutine.body
        comment = (block.comment or "block").replace(" ", "_")
        subroutine_name = self.context.subroutine_names[self.current_subroutine]
        return f"{subroutine_name}_{comment}@{block.id}"

    def visit_assignment(self, ass: ir.Assignment) -> None:
        ass.source.accept(self)
        # right most target is top of stack
        for target in reversed(ass.targets):
            try:
                param_idx = self.current_subroutine.parameters.index(target)
            except ValueError:
                self._add_op(
                    models.StoreVirtual(
                        local_id=target.local_id,
                        source_location=ass.source_location,
                        atype=target.atype,
                    )
                )
            else:
                index = param_idx - len(self.current_subroutine.parameters)
                self._add_op(
                    models.StoreParam(
                        local_id=target.local_id,
                        index=index,
                        source_location=ass.source_location,
                        atype=target.atype,
                    )
                )

    def visit_register(self, reg: ir.Register) -> None:
        try:
            param_idx = self.current_subroutine.parameters.index(reg)
        except ValueError:
            self._add_op(
                models.LoadVirtual(
                    local_id=reg.local_id,
                    source_location=(self.active_op or reg).source_location,
                    atype=reg.atype,
                )
            )
        else:
            index = param_idx - len(self.current_subroutine.parameters)
            self._add_op(
                models.LoadParam(
                    local_id=reg.local_id,
                    index=index,
                    source_location=(self.active_op or reg).source_location,
                    atype=reg.atype,
                )
            )

    def visit_value_tuple(self, tup: ir.ValueTuple) -> None:
        raise InternalError(
            "Encountered ValueTuple during codegen - should have been eliminated in prior stages",
            tup.source_location,
        )

    def visit_uint64_constant(self, const: ir.UInt64Constant) -> None:
        self._add_op(
            models.PushInt(
                const.value if not const.teal_alias else const.teal_alias,
                source_location=const.source_location,
            )
        )

    def visit_biguint_constant(self, const: ir.BigUIntConstant) -> None:
        byte_length = ceil(const.value.bit_length() / 8.0)
        assert byte_length <= 64, "Biguints must be 64 bytes or less"
        big_uint_bytes = const.value.to_bytes(byteorder="big", length=byte_length)
        self._add_op(
            models.PushBytes(
                big_uint_bytes,
                source_location=const.source_location,
                comment=str(const.value),
                encoding=AVMBytesEncoding.base16,
            )
        )

    def visit_bytes_constant(self, const: ir.BytesConstant) -> None:
        self._add_op(
            models.PushBytes(
                const.value, encoding=const.encoding, source_location=const.source_location
            )
        )

    def visit_address_constant(self, const: ir.AddressConstant) -> None:
        self._add_op(
            models.PushAddress(
                const.value,
                source_location=const.source_location,
            )
        )

    def visit_method_constant(self, const: ir.MethodConstant) -> None:
        self._add_op(
            models.PushMethod(
                const.value,
                source_location=const.source_location,
            )
        )

    def visit_phi(self, phi: ir.Phi) -> None:
        raise InternalError(
            "Encountered Phi node during codegen - should have been eliminated in prior stages",
            phi.source_location,
        )

    def visit_phi_argument(self, arg: ir.PhiArgument) -> None:
        raise InternalError(
            "Encountered PhiArgument during codegen - should have been eliminated in prior stages",
            arg.source_location,
        )

    def visit_intrinsic_op(self, intrinsic: ir.Intrinsic) -> None:
        if intrinsic.op.min_avm_version > self.context.options.target_avm_version:
            raise CodeError(
                f"Opcode {intrinsic.op.code} requires a min avm version of "
                f"{intrinsic.op.min_avm_version} but the target avm version is"
                f" {self.context.options.target_avm_version}",
                intrinsic.source_location,
            )
        for arg in intrinsic.args:
            arg.accept(self)
        self._add_op(
            models.IntrinsicOp(
                op_code=intrinsic.op.code,
                immediates=intrinsic.immediates,
                source_location=intrinsic.source_location,
                consumes=len(intrinsic.op_signature.args),
                produces=len(intrinsic.op_signature.returns),
                comment=intrinsic.comment,
            )
        )

    def visit_invoke_subroutine(self, callsub: ir.InvokeSubroutine) -> None:
        discard_results = callsub is self.active_op
        target = callsub.target

        callsub_op = models.CallSub(
            target=self.context.subroutine_names[target],
            parameters=len(target.parameters),
            returns=len(target.returns),
            source_location=callsub.source_location,
        )

        # prepare args
        for arg in callsub.args:
            arg.accept(self)

        # call sub
        self._add_op(callsub_op)

        if discard_results and target.returns:
            num_returns = len(target.returns)
            self._add_op(models.Pop(num_returns))

    def visit_conditional_branch(self, branch: ir.ConditionalBranch) -> None:
        branch.condition.accept(self)
        if self.next_block is branch.zero:
            other = branch.zero
            self._add_op(
                models.BranchNonZero(
                    immediates=[self._get_block_name(branch.non_zero)],
                    source_location=branch.source_location,
                )
            )
        else:
            other = branch.non_zero
            self._add_op(
                models.BranchZero(
                    immediates=[self._get_block_name(branch.zero)],
                    source_location=branch.source_location,
                )
            )
        self._add_op(
            models.Branch(
                immediates=[self._get_block_name(other)], source_location=branch.source_location
            )
        )

    def visit_goto(self, goto: ir.Goto) -> None:
        self._add_op(
            models.Branch(
                immediates=[self._get_block_name(goto.target)],
                source_location=goto.source_location,
            )
        )

    def visit_goto_nth(self, goto_nth: ir.GotoNth) -> None:
        block_labels = [self._get_block_name(block) for block in goto_nth.blocks]
        goto_nth.value.accept(self)
        self._add_op(
            models.Switch(immediates=block_labels, source_location=goto_nth.source_location)
        )
        goto_nth.default.accept(self)

    def visit_switch(self, switch: ir.Switch) -> None:
        blocks = list[str]()
        for case, block in switch.cases.items():
            case.accept(self)
            block_name = self._get_block_name(block)
            blocks.append(block_name)
        switch.value.accept(self)

        self._add_op(models.Match(immediates=blocks, source_location=switch.source_location))
        switch.default.accept(self)

    def visit_subroutine_return(self, retsub: ir.SubroutineReturn) -> None:
        for r in retsub.result:
            r.accept(self)
        self._add_op(
            models.IntrinsicOp(
                op_code="return",
                source_location=retsub.source_location,
                consumes=len(retsub.result),
                produces=0,
            )
            if self.is_main
            else models.RetSub(source_location=retsub.source_location, returns=len(retsub.result))
        )

    def visit_program_exit(self, exit_: ir.ProgramExit) -> None:
        exit_.result.accept(self)
        self._add_op(
            models.IntrinsicOp(
                op_code="return",
                source_location=exit_.source_location,
                consumes=0,
                produces=0,
            )
        )

    def visit_fail(self, fail: ir.Fail) -> None:
        self._add_op(
            models.IntrinsicOp(
                op_code="err",
                comment=fail.comment,
                source_location=fail.source_location,
                consumes=0,
                produces=0,
            )
        )

    def lower_block_to_teal(
        self, block: ir.BasicBlock, next_block: ir.BasicBlock | None
    ) -> models.MemoryBasicBlock:
        self.next_block = next_block
        self.current_ops = list[models.BaseOp]()
        for op in block.all_ops:
            assert not isinstance(op, ir.Phi)
            self.active_op = op
            op.accept(self)
        if (
            next_block is not None
            and self.current_ops
            and isinstance((last_op := self.current_ops[-1]), models.IntrinsicOp)
            and last_op.op_code == "b"
            and last_op.immediates[0] == (next_block_name := self._get_block_name(next_block))
        ):
            self.current_ops[-1] = models.Comment(
                f"Implicit fall through to {next_block_name}",
                source_location=last_op.source_location,
            )

        block_name = self._get_block_name(block)
        predecessors = [self._get_block_name(b) for b in block.predecessors]
        successors = [self._get_block_name(b) for b in block.successors]
        return models.MemoryBasicBlock(
            block_name=block_name,
            ops=self.current_ops,
            predecessors=predecessors,
            successors=successors,
            source_location=block.source_location,
        )
