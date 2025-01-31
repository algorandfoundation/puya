import typing
from itertools import zip_longest

import attrs

from puya.avm import AVMType
from puya.errors import InternalError
from puya.ir.types_ import AVMBytesEncoding
from puya.mir import models as mir
from puya.mir.visitor import MIRVisitor
from puya.teal import models as teal


@attrs.frozen
class TealBuilder(MIRVisitor[None]):
    next_block_label: str | None
    use_frame: bool
    label_stack: list[str]
    ops: list[teal.TealOp] = attrs.field(factory=list)

    @classmethod
    def build_subroutine(cls, mir_sub: mir.MemorySubroutine) -> teal.TealSubroutine:
        result = teal.TealSubroutine(
            is_main=mir_sub.is_main,
            signature=mir_sub.signature,
            blocks=[],
            source_location=mir_sub.source_location,
        )
        entry_block = mir_sub.body[0]
        label_stack = [entry_block.block_name]
        blocks_by_label = {
            b.block_name: (b, None if next_b is None else next_b.block_name)
            for b, next_b in zip_longest(mir_sub.body, mir_sub.body[1:])
        }
        while label_stack:
            label = label_stack.pop()
            mir_block, next_block_label = blocks_by_label.pop(label, (None, None))
            if mir_block is None:
                continue
            builder = cls(
                next_block_label=next_block_label,
                use_frame=not mir_sub.is_main,
                label_stack=label_stack,
            )
            if mir_block is entry_block and not mir_sub.is_main:
                builder.ops.append(
                    teal.Proto(
                        parameters=len(mir_sub.signature.parameters),
                        returns=len(mir_sub.signature.returns),
                        source_location=mir_sub.source_location,
                    )
                )
            for op in mir_block.ops:
                op.accept(builder)
            teal_block = teal.TealBlock(
                label=mir_block.block_name,
                ops=builder.ops,
                x_stack_in=mir_block.x_stack_in or (),
                entry_stack_height=mir_block.entry_stack_height,
                exit_stack_height=mir_block.exit_stack_height,
            )
            teal_block.validate_stack_height()
            result.blocks.append(teal_block)
        return result

    def _add_op(self, op: teal.TealOp) -> None:
        self.ops.append(op)

    def visit_int(self, const: mir.Int) -> None:
        self._add_op(
            teal.Int(
                const.value,
                stack_manipulations=_lstack_manipulations(const),
                source_location=const.source_location,
            )
        )

    def visit_byte(self, const: mir.Byte) -> None:
        self._add_op(
            teal.Byte(
                const.value,
                const.encoding,
                stack_manipulations=_lstack_manipulations(const),
                source_location=const.source_location,
            )
        )

    def visit_undefined(self, push: mir.Undefined) -> None:
        match push.atype:
            case AVMType.uint64:
                self._add_op(
                    teal.Byte(
                        b"",
                        AVMBytesEncoding.utf8,
                        stack_manipulations=_lstack_manipulations(push),
                        source_location=push.source_location,
                    )
                )
            case AVMType.bytes:
                self._add_op(
                    teal.Int(
                        0,
                        stack_manipulations=_lstack_manipulations(push),
                        source_location=push.source_location,
                    )
                )
            case unexpected:
                typing.assert_never(unexpected)

    def visit_template_var(self, const: mir.TemplateVar) -> None:
        self._add_op(
            teal.TemplateVar(
                name=const.name,
                op_code=const.op_code,
                stack_manipulations=_lstack_manipulations(const),
                source_location=const.source_location,
            )
        )

    def visit_address(self, const: mir.Address) -> None:
        self._add_op(
            teal.Address(
                const.value,
                stack_manipulations=_lstack_manipulations(const),
                source_location=const.source_location,
            )
        )

    def visit_method(self, const: mir.Method) -> None:
        self._add_op(
            teal.Method(
                const.value,
                stack_manipulations=_lstack_manipulations(const),
                source_location=const.source_location,
            )
        )

    def visit_comment(self, _comment: mir.Comment) -> None:
        pass

    def visit_abstract_store(self, store: mir.AbstractStore) -> typing.Never:
        raise InternalError(
            "AbstractStore op encountered during TEAL generation", store.source_location
        )

    def visit_abstract_load(self, load: mir.AbstractLoad) -> typing.Never:
        raise InternalError(
            "AbstractLoad op encountered during TEAL generation", load.source_location
        )

    def _store_f_stack(self, store: mir.StoreFStack) -> None:
        local_id = store.local_id
        source_location = store.source_location
        define = teal.StackDefine(local_id)
        if self.use_frame:
            op: teal.TealOp = teal.FrameBury(
                store.frame_index,
                stack_manipulations=[*_lstack_manipulations(store), define],
                source_location=source_location,
            )
        else:
            op = teal.Bury(
                store.depth,
                stack_manipulations=[*_lstack_manipulations(store), define],
                source_location=source_location,
            )
        self._add_op(op)

    def _insert_f_stack(self, store: mir.StoreFStack) -> None:
        local_id = store.local_id
        source_location = store.source_location
        self._add_op(
            teal.Cover(
                store.depth,
                stack_manipulations=[
                    *_lstack_manipulations(store),
                    teal.StackInsert(store.depth, local_id),
                    teal.StackDefine(local_id),
                ],
                source_location=source_location,
            )
        )

    def visit_store_f_stack(self, store: mir.StoreFStack) -> None:
        if store.insert:
            self._insert_f_stack(store)
        else:
            self._store_f_stack(store)

    def visit_load_f_stack(self, load: mir.LoadFStack) -> None:
        sm = _lstack_manipulations(load)
        loc = load.source_location
        if self.use_frame:  # and load.depth:
            op: teal.TealOp = teal.FrameDig(
                n=load.frame_index, stack_manipulations=sm, source_location=loc
            )
        else:
            op = teal.Dig(n=load.depth, stack_manipulations=sm, source_location=loc)
        self._add_op(op)

    def visit_store_x_stack(self, store: mir.StoreXStack) -> None:
        self._add_op(
            teal.Cover(
                store.depth,
                stack_manipulations=[
                    *_lstack_manipulations(store),
                    teal.StackInsert(store.depth, store.local_id),
                    teal.StackDefine(store.local_id),
                ],
                source_location=store.source_location,
            )
        )

    def visit_load_x_stack(self, load: mir.LoadXStack) -> None:
        self._add_op(
            teal.Uncover(
                load.depth,
                stack_manipulations=[
                    teal.StackPop(load.depth),
                    *_lstack_manipulations(load),
                ],
                source_location=load.source_location,
            )
        )

    def visit_store_l_stack(self, store: mir.StoreLStack) -> None:
        if store.copy:
            self._add_op(
                teal.Dup(
                    stack_manipulations=[
                        # re-alias top of stack
                        teal.StackConsume(1),
                        *_lstack_manipulations(store),
                        # actual dup
                        teal.StackExtend([f"{store.local_id} (copy)"]),
                    ],
                    source_location=store.source_location,
                ),
            )
        cover = store.depth
        if store.copy:
            cover += 1
        self._add_op(
            teal.Cover(
                cover,
                stack_manipulations=[
                    teal.StackConsume(1),
                    # store
                    teal.StackInsert(cover, store.local_id),
                    teal.StackDefine([store.local_id]),
                ],
                source_location=store.source_location,
            )
        )

    def visit_load_l_stack(self, load: mir.LoadLStack) -> None:
        uncover = load.depth
        assert uncover is not None, "expected l-stack depths to be assigned"
        if load.copy:
            self._add_op(
                teal.Dig(
                    uncover,
                    stack_manipulations=_lstack_manipulations(load),
                    source_location=load.source_location,
                )
            )
        else:
            self._add_op(
                teal.Uncover(
                    uncover,
                    stack_manipulations=[teal.StackPop(uncover), *_lstack_manipulations(load)],
                    source_location=load.source_location,
                )
            )

    def visit_load_param(self, load: mir.LoadParam) -> None:
        self._add_op(
            teal.FrameDig(
                load.index,
                source_location=load.source_location,
                stack_manipulations=_lstack_manipulations(load),
            )
        )

    def visit_store_param(self, store: mir.StoreParam) -> None:
        self._add_op(
            teal.FrameBury(
                store.index,
                stack_manipulations=_lstack_manipulations(store),
                source_location=store.source_location,
            )
        )

    def visit_allocate(self, allocate: mir.Allocate) -> None:
        bad_bytes_value = teal.Int(
            0,
            source_location=allocate.source_location,
        )
        bad_uint_value = teal.Byte(
            value=b"",
            encoding=AVMBytesEncoding.utf8,
            source_location=allocate.source_location,
        )

        for idx, local_id in enumerate(allocate.allocate_on_entry):
            bad_value = bad_bytes_value if idx < allocate.num_bytes else bad_uint_value
            self._add_op(
                attrs.evolve(
                    bad_value,
                    stack_manipulations=[teal.StackExtend([local_id])],
                )
            )

    def visit_pop(self, pop: mir.Pop) -> None:
        self._add_op(
            teal.PopN(
                n=pop.n,
                stack_manipulations=_lstack_manipulations(pop),
                source_location=pop.source_location,
            )
        )

    def visit_callsub(self, callsub: mir.CallSub) -> None:
        self._add_op(
            teal.CallSub(
                target=callsub.target,
                consumes=callsub.parameters,
                produces=callsub.returns,
                stack_manipulations=_lstack_manipulations(callsub),
                source_location=callsub.source_location,
            )
        )

    def visit_retsub(self, retsub: mir.RetSub) -> None:
        fx_height = retsub.fx_height
        if retsub.returns < fx_height:
            # move returns to base of frame in order
            for n in reversed(range(retsub.returns)):
                self._add_op(teal.FrameBury(n, source_location=retsub.source_location))
        else:
            # f-stack + x-stack is smaller than number of returns, so move it out of the way
            n = retsub.returns + fx_height - 1
            for _ in range(fx_height):
                self._add_op(teal.Uncover(n, source_location=retsub.source_location))
        self._add_op(
            teal.RetSub(
                consumes=retsub.returns,
                source_location=retsub.source_location,
            )
        )

    def visit_program_exit(self, op: mir.ProgramExit) -> None:
        self._add_op(
            teal.Return(
                error_message=op.error_message,
                stack_manipulations=_lstack_manipulations(op),
                source_location=op.source_location,
            )
        )

    def visit_err(self, op: mir.Err) -> None:
        self._add_op(
            teal.Err(
                error_message=op.error_message,
                stack_manipulations=_lstack_manipulations(op),
                source_location=op.source_location,
            )
        )

    def visit_goto(self, op: mir.Goto) -> None:
        self._add_op(
            teal.Branch(
                target=op.target,
                error_message=op.error_message,
                stack_manipulations=_lstack_manipulations(op),
                source_location=op.source_location,
            )
        )
        self.label_stack.append(op.target)

    def visit_conditional_branch(self, op: mir.ConditionalBranch) -> None:
        condition_op: type[teal.BranchNonZero | teal.BranchZero]
        if op.nonzero_target == self.next_block_label:
            condition_op = teal.BranchZero
            condition_op_target = op.zero_target
            other_target = op.nonzero_target
        else:
            condition_op = teal.BranchNonZero
            condition_op_target = op.nonzero_target
            other_target = op.zero_target

        self._add_op(
            condition_op(
                target=condition_op_target,
                error_message=op.error_message,
                stack_manipulations=_lstack_manipulations(op),
                source_location=op.source_location,
            )
        )
        self.label_stack.append(condition_op_target)
        self._add_op(
            teal.Branch(
                target=other_target,
                error_message="",
                stack_manipulations=[],
                source_location=op.source_location,
            )
        )
        self.label_stack.append(other_target)

    def visit_switch(self, op: mir.Switch) -> None:
        self._add_op(
            teal.Switch(
                targets=op.switch_targets,
                error_message=op.error_message,
                stack_manipulations=_lstack_manipulations(op),
                source_location=op.source_location,
            )
        )
        self.label_stack.extend(op.switch_targets)
        self._add_op(
            teal.Branch(
                target=op.default_target,
                error_message="",
                stack_manipulations=[],
                source_location=op.source_location,
            )
        )
        self.label_stack.append(op.default_target)

    def visit_match(self, op: mir.Match) -> None:
        self._add_op(
            teal.Match(
                targets=op.match_targets,
                error_message=op.error_message,
                stack_manipulations=_lstack_manipulations(op),
                source_location=op.source_location,
            )
        )
        self.label_stack.extend(op.match_targets)
        self._add_op(
            teal.Branch(
                target=op.default_target,
                error_message="",
                stack_manipulations=[],
                source_location=op.source_location,
            )
        )
        self.label_stack.append(op.default_target)

    def visit_intrinsic(self, intrinsic: mir.IntrinsicOp) -> None:
        self._add_op(
            teal.Intrinsic(
                op_code=intrinsic.op_code,
                immediates=intrinsic.immediates,
                error_message=intrinsic.error_message,
                consumes=intrinsic.consumes,
                produces=len(intrinsic.produces),
                stack_manipulations=_lstack_manipulations(intrinsic),
                source_location=intrinsic.source_location,
            )
        )


def _lstack_manipulations(op: mir.BaseOp) -> list[teal.StackManipulation]:
    result = list[teal.StackManipulation]()
    if op.consumes:
        result.append(teal.StackConsume(op.consumes))
    if op.produces:
        result.append(teal.StackExtend(op.produces))
        result.append(teal.StackDefine(op.produces))
    return result
