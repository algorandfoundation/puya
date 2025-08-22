import typing
from collections.abc import Mapping

import attrs

from puya import log
from puya.algo_constants import MAX_BYTES_LENGTH
from puya.avm import AVMType
from puya.errors import CodeError, InternalError
from puya.ir import models as ir
from puya.ir.avm_ops import AVMOp
from puya.ir.types_ import AVMBytesEncoding
from puya.ir.visitor import IRVisitor
from puya.mir import models
from puya.mir.context import ProgramMIRContext
from puya.utils import biguint_bytes_eval

logger = log.get_logger(__name__)

# TODO: ensure unique
_NEW_SLOT_SUB = "_puya_lib.mem.new_slot"


@attrs.define
class MemoryIRBuilder(IRVisitor[None]):
    context: ProgramMIRContext = attrs.field(on_setattr=attrs.setters.frozen)
    subroutine: ir.Subroutine = attrs.field(on_setattr=attrs.setters.frozen)
    is_main: bool = attrs.field(on_setattr=attrs.setters.frozen)
    _block_names: Mapping[ir.BasicBlock, str] = attrs.field(init=False)
    _param_idxs: Mapping[ir.Register, int] = attrs.field(init=False)
    current_ops: list[models.Op] = attrs.field(factory=list)
    terminator: models.ControlOp | None = None
    active_op: ir.Op | ir.ControlOp | None = None

    def _add_op(self, op: models.Op) -> None:
        self.current_ops.append(op)

    def _terminate(self, op: models.ControlOp) -> None:
        assert self.terminator is None
        self.terminator = op

    @_block_names.default
    def _block_names_cache(self) -> Mapping[ir.BasicBlock, str]:
        result = {}
        for block in self.subroutine.body:
            comment = (block.comment or "block").replace(" ", "_")
            subroutine_name = self.context.subroutine_names[self.subroutine]
            result[block] = f"{subroutine_name}_{comment}@{block.id}"
        return result

    @_param_idxs.default
    def _param_idxs_cache(self) -> Mapping[ir.Register, int]:
        parameters = self.subroutine.parameters
        num_params = len(parameters)
        return {param: idx - num_params for idx, param in enumerate(parameters)}

    def visit_assignment(self, ass: ir.Assignment) -> None:
        ass.source.accept(self)
        # right most target is top of stack
        for target in reversed(ass.targets):
            param_idx = self._param_idxs.get(target)
            if param_idx is None:
                self._add_op(
                    models.AbstractStore(
                        local_id=target.local_id,
                        source_location=ass.source_location,
                        atype=target.atype,
                    )
                )
            else:
                self._add_op(
                    models.StoreParam(
                        local_id=target.local_id,
                        index=param_idx,
                        source_location=ass.source_location,
                        atype=target.atype,
                    )
                )

    def visit_register(self, reg: ir.Register) -> None:
        param_idx = self._param_idxs.get(reg)
        if param_idx is None:
            self._add_op(
                models.AbstractLoad(
                    local_id=reg.local_id,
                    source_location=(self.active_op or reg).source_location,
                    atype=reg.atype,
                )
            )
        else:
            self._add_op(
                models.LoadParam(
                    local_id=reg.local_id,
                    index=param_idx,
                    source_location=(self.active_op or reg).source_location,
                    atype=reg.atype,
                )
            )

    def visit_undefined(self, val: ir.Undefined) -> None:
        self._add_op(
            models.Undefined(
                atype=val.atype,
                source_location=val.source_location,
            )
        )

    def visit_new_slot(self, new_slot: ir.NewSlot) -> None:
        self._add_op(
            models.CallSub(
                target=_NEW_SLOT_SUB,
                parameters=0,
                returns=1,
                produces=_produces_from_op(_NEW_SLOT_SUB, 1, self.active_op),
                source_location=new_slot.source_location,
            )
        )

    def visit_read_slot(self, read: ir.ReadSlot) -> None:
        if isinstance(read.slot, ir.SlotConstant):
            self._add_op(
                models.AbstractLoad(
                    local_id=f"slot{ir.TMP_VAR_INDICATOR}{read.slot.value}",
                    atype=read.slot.ir_type.contents.avm_type,
                )
            )
        else:
            if isinstance(read.slot, ir.UInt64Constant):
                op = "load"
                consumes = 0
                immediates: tuple[int, ...] = (read.slot.value,)
            else:
                read.slot.accept(self)
                op = "loads"
                consumes = 1
                immediates = ()
            self._add_op(
                models.IntrinsicOp(
                    op_code=op,
                    source_location=read.source_location,
                    immediates=immediates,
                    consumes=consumes,
                    produces=_produces_from_op(op, 1, self.active_op),
                )
            )

    def visit_write_slot(self, write: ir.WriteSlot) -> None:
        if isinstance(write.slot, ir.SlotConstant):
            write.value.accept(self)
            self._add_op(
                models.AbstractStore(
                    local_id=f"slot{ir.TMP_VAR_INDICATOR}{write.slot.value}",
                    atype=write.slot.ir_type.contents.avm_type,
                )
            )
        else:
            if isinstance(write.slot, ir.UInt64Constant):
                op = "store"
                consumes = 1
                immediates: tuple[int, ...] = (write.slot.value,)
            else:
                write.slot.accept(self)
                op = "stores"
                consumes = 2
                immediates = ()
            write.value.accept(self)
            self._add_op(
                models.IntrinsicOp(
                    op_code=op,
                    source_location=write.source_location,
                    immediates=immediates,
                    consumes=consumes,
                    produces=(),
                )
            )

    def visit_array_length(self, length: ir.ArrayLength) -> None:
        _unexpected_node(length)

    def visit_extract_value(self, read: ir.ExtractValue) -> None:
        _unexpected_node(read)

    def visit_replace_value(self, write: ir.ReplaceValue) -> None:
        _unexpected_node(write)

    def visit_box_read(self, read: ir.BoxRead) -> None:
        _unexpected_node(read)

    def visit_box_write(self, write: ir.BoxWrite) -> None:
        _unexpected_node(write)

    def visit_bytes_encode(self, encode: ir.BytesEncode) -> None:
        _unexpected_node(encode)

    def visit_decode_bytes(self, encode: ir.DecodeBytes) -> None:
        _unexpected_node(encode)

    def visit_template_var(self, deploy_var: ir.TemplateVar) -> None:
        self._add_op(
            models.TemplateVar(
                name=deploy_var.name,
                atype=deploy_var.atype,
                source_location=deploy_var.source_location,
            )
        )

    def visit_uint64_constant(self, const: ir.UInt64Constant) -> None:
        self._add_op(
            models.Int(
                const.value if not const.teal_alias else const.teal_alias,
                source_location=const.source_location,
            )
        )

    def visit_biguint_constant(self, const: ir.BigUIntConstant) -> None:
        big_uint_bytes = biguint_bytes_eval(const.value)
        self._add_op(
            models.Byte(
                big_uint_bytes,
                source_location=const.source_location,
                encoding=AVMBytesEncoding.base16,
            )
        )

    def visit_bytes_constant(self, const: ir.BytesConstant) -> None:
        self._add_op(
            models.Byte(
                const.value, encoding=const.encoding, source_location=const.source_location
            )
        )

    def visit_address_constant(self, const: ir.AddressConstant) -> None:
        self._add_op(
            models.Address(
                const.value,
                source_location=const.source_location,
            )
        )

    def visit_method_constant(self, const: ir.MethodConstant) -> None:
        self._add_op(
            models.Method(
                const.value,
                source_location=const.source_location,
            )
        )

    def visit_intrinsic_op(self, intrinsic: ir.Intrinsic) -> None:
        if intrinsic.op.code.startswith("box_"):
            try:
                box_key = intrinsic.args[0]
            except ValueError:
                raise InternalError("box key arg not found", intrinsic.source_location) from None
            if isinstance(box_key, ir.BytesConstant) and not box_key.value:
                raise CodeError("AVM does not support empty box keys", intrinsic.source_location)
        if intrinsic.op.code == "box_extract":
            length = intrinsic.args[2]
            if isinstance(length, ir.UInt64Constant) and length.value > MAX_BYTES_LENGTH:
                logger.warning(
                    f"value exceeds {MAX_BYTES_LENGTH} bytes", location=intrinsic.source_location
                )
        for arg in intrinsic.args:
            arg.accept(self)
        produces = len(intrinsic.op_signature.returns)
        self._add_op(
            models.IntrinsicOp(
                op_code=intrinsic.op.code,
                immediates=intrinsic.immediates,
                source_location=intrinsic.source_location,
                consumes=len(intrinsic.op_signature.args),
                produces=_produces_from_op(intrinsic.op.code, produces, self.active_op),
                error_message=intrinsic.error_message,
            )
        )

    def visit_invoke_subroutine(self, callsub: ir.InvokeSubroutine) -> None:
        target = callsub.target

        callsub_op = models.CallSub(
            target=self.context.subroutine_names[target],
            parameters=len(target.parameters),
            returns=len(target.returns),
            produces=_produces_from_op(
                self.context.subroutine_names[target], len(target.returns), self.active_op
            ),
            source_location=callsub.source_location,
        )

        # prepare args
        for arg in callsub.args:
            arg.accept(self)

        # call sub
        self._add_op(callsub_op)

    def visit_conditional_branch(self, branch: ir.ConditionalBranch) -> None:
        branch.condition.accept(self)
        self._terminate(
            models.ConditionalBranch(
                nonzero_target=self._block_names[branch.non_zero],
                zero_target=self._block_names[branch.zero],
                source_location=branch.source_location,
            )
        )

    def visit_goto(self, goto: ir.Goto) -> None:
        self._terminate(
            models.Goto(
                target=self._block_names[goto.target],
                source_location=goto.source_location,
            )
        )

    def visit_goto_nth(self, goto_nth: ir.GotoNth) -> None:
        block_labels = tuple(self._block_names[block] for block in goto_nth.blocks)
        goto_nth.value.accept(self)
        self._terminate(
            models.Switch(
                switch_targets=block_labels,
                default_target=self._block_names[goto_nth.default],
                source_location=goto_nth.source_location,
            )
        )

    def visit_switch(self, switch: ir.Switch) -> None:
        blocks = list[str]()
        for case, block in switch.cases.items():
            case.accept(self)
            block_name = self._block_names[block]
            blocks.append(block_name)
        switch.value.accept(self)
        self._terminate(
            models.Match(
                match_targets=blocks,
                default_target=self._block_names[switch.default],
                source_location=switch.source_location,
            )
        )

    def visit_subroutine_return(self, retsub: ir.SubroutineReturn) -> None:
        for r in retsub.result:
            r.accept(self)
        if self.is_main:
            assert len(retsub.result) == 1
            self._terminate(models.ProgramExit(source_location=retsub.source_location))
        else:
            self._terminate(
                models.RetSub(returns=len(retsub.result), source_location=retsub.source_location)
            )

    def visit_program_exit(self, exit_: ir.ProgramExit) -> None:
        exit_.result.accept(self)
        self._terminate(models.ProgramExit(source_location=exit_.source_location))

    def visit_fail(self, fail: ir.Fail) -> None:
        self._terminate(
            models.Err(error_message=fail.error_message, source_location=fail.source_location)
        )

    def lower_block_to_mir(self, block: ir.BasicBlock) -> models.MemoryBasicBlock:
        self.current_ops = list[models.Op]()
        self.terminator = None
        for op in block.all_ops:
            assert not isinstance(op, ir.Phi)
            self.active_op = op
            op.accept(self)
            # pop any values that may have been left on the stack and not assigned
            if isinstance(op, ir.ValueProvider) and op.types:
                self._add_op(models.Pop(len(op.types)))

        assert self.terminator is not None
        block_name = self._block_names[block]
        predecessors = [self._block_names[b] for b in block.predecessors]
        assert block.id is not None
        return models.MemoryBasicBlock(
            id=block.id,
            block_name=block_name,
            mem_ops=self.current_ops,
            terminator=self.terminator,
            predecessors=predecessors,
            source_location=block.source_location,
        )

    def visit_compiled_contract_reference(self, const: ir.CompiledContractReference) -> None:
        _unexpected_node(const)

    def visit_compiled_logicsig_reference(self, const: ir.CompiledLogicSigReference) -> None:
        _unexpected_node(const)

    def visit_value_tuple(self, tup: ir.ValueTuple) -> None:
        _unexpected_node(tup)

    def visit_itxn_constant(self, const: ir.ITxnConstant) -> None:
        _unexpected_node(const)

    def visit_slot_constant(self, const: ir.SlotConstant) -> None:
        _unexpected_node(const)

    def visit_inner_transaction_field(self, field: ir.InnerTransactionField) -> None:
        _unexpected_node(field)

    def visit_phi(self, phi: ir.Phi) -> None:
        _unexpected_node(phi)

    def visit_phi_argument(self, arg: ir.PhiArgument) -> None:
        _unexpected_node(arg)


def _unexpected_node(node: ir.IRVisitable) -> typing.Never:
    raise InternalError(
        f"Encountered node of type {type(node).__name__!r} during codegen"
        f" - should have been eliminated in prior stages",
        node.source_location,
    )


def build_new_slot_sub(allocation_slot: int) -> models.MemorySubroutine:
    """
    # bitlen counts bits from the right-most bit
    # setbit sets bits from the left-most bit
    # to convert the result of a bitlen back to an index compatible with setbit
    # we need to subtract the bitlen result from the length of the byte array
    # which is hardcoded to 256 bits

    load SLOT       // slot
    bitlen          // free_slot
    load SLOT       // free_slot, slot
    int 256         // free_slot, slot, 256
    dig 2           // free_slot, slot, 256, free_slot
    -               // free_slot, slot, free_slot_idx
    int 0           // free_slot, slot, free_slot_idx, 0
    setbit          // free_slot, new_slot
    store SLOT      // free_slot
    retsub
    """

    def make_op(
        op: AVMOp, *immediates: int, local_id: str | None = None, error_message: str | None = None
    ) -> models.IntrinsicOp:
        variant = op.get_variant(immediates)
        produces = (
            (local_id,)
            if local_id
            else _produces_from_op(op, len(variant.signature.returns), None)
        )
        return models.IntrinsicOp(
            op_code=op,
            immediates=immediates,
            consumes=len(variant.signature.args),
            produces=produces,
            error_message=error_message,
            source_location=None,
        )

    return models.MemorySubroutine(
        id=_NEW_SLOT_SUB,
        is_main=False,
        signature=models.Signature(name=_NEW_SLOT_SUB, parameters=(), returns=(AVMType.uint64,)),
        pre_alloc=models.FStackPreAllocation.empty(),
        body=[
            models.MemoryBasicBlock(
                id=0,
                block_name=_NEW_SLOT_SUB + "@entry",
                mem_ops=[
                    make_op(AVMOp.load, allocation_slot, local_id="slot_allocations"),
                    make_op(AVMOp.bitlen),
                    models.AbstractStore(
                        local_id="free_slot#0",
                        atype=AVMType.uint64,
                        source_location=None,
                    ),
                    make_op(AVMOp.load, allocation_slot, local_id="slot_allocations"),
                    models.Int(
                        value=256,
                        source_location=None,
                    ),
                    models.AbstractLoad(
                        local_id="free_slot#0",
                        atype=AVMType.uint64,
                        source_location=None,
                    ),
                    make_op(AVMOp.sub, local_id="free_slot_idx"),
                    models.Int(
                        value=0,
                        source_location=None,
                    ),
                    make_op(
                        AVMOp.setbit,
                        error_message="no available slots",
                        local_id="new_slot_allocations",
                    ),
                    make_op(AVMOp.store, allocation_slot),
                    models.AbstractLoad(
                        local_id="free_slot#0",
                        atype=AVMType.uint64,
                        source_location=None,
                    ),
                ],
                predecessors=[],
                terminator=models.RetSub(returns=1, fx_height=0, source_location=None),
                source_location=None,
            )
        ],
        source_location=None,
    )


def _produces_from_op(
    prefix: str, size: int, maybe_assignment: ir.IRVisitable | None
) -> tuple[str, ...]:
    if isinstance(maybe_assignment, ir.Assignment):
        return tuple(r.local_id for r in maybe_assignment.targets)
    else:
        return models.produces_from_desc(prefix, size)
