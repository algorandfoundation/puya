import itertools
from collections.abc import Sequence

import attrs

from puya import log
from puya.mir import models as mir
from puya.mir.context import SubroutineCodeGenContext
from puya.mir.visitor import MIRVisitor

logger = log.get_logger(__name__)

# Note: implementation of the koopmans algorithm part of http://www.euroforth.org/ef06/shannon-bailey06.pdf
# see also https://users.ece.cmu.edu/~koopman/stack_compiler/stack_co.html#appendix


@attrs.define
class UsagePair:
    a: mir.LoadVirtual | mir.StoreVirtual
    b: mir.LoadVirtual
    a_index: int
    b_index: int

    @staticmethod
    def by_distance(pair: "UsagePair") -> tuple[int, int, int]:
        return pair.b_index - pair.a_index, pair.a_index, pair.b_index


def koopmans(ctx: SubroutineCodeGenContext) -> None:
    for block in ctx.subroutine.body:
        usage_pairs = find_usage_pairs(block)
        copy_usage_pairs(block, usage_pairs)


def find_usage_pairs(block: mir.MemoryBasicBlock) -> list[UsagePair]:
    # find usage pairs of variables within the block
    # the first element of the pair is an op that defines or uses a variable
    # the second element of the pair is an op that uses the variable
    # return pairs in ascending order, based on the number of instruction between each pair
    variables = dict[str, list[tuple[int, mir.StoreVirtual | mir.LoadVirtual]]]()
    for index, op in enumerate(block.ops):
        match op:
            case mir.StoreVirtual(local_id=local_id) | mir.LoadVirtual(local_id=local_id):
                variables.setdefault(local_id, []).append((index, op))

    pairs = list[UsagePair]()
    for uses in variables.values():
        for (a_index, a), (b_index, b) in itertools.pairwise(uses):
            if isinstance(b, mir.StoreVirtual):
                continue  # skip redefines, if they are used they will be picked up in next pair
            pairs.append(UsagePair(a=a, b=b, a_index=a_index, b_index=b_index))

    return sorted(pairs, key=UsagePair.by_distance)


def copy_usage_pairs(block: mir.MemoryBasicBlock, pairs: list[UsagePair]) -> None:
    # 1. copy define or use to bottom of l-stack
    # 2. replace usage with instruction to rotate the value from the bottom of l-stack to the top

    # to copy: dup, cover {stack_height}
    # to rotate: uncover {stack_height} - 1
    replaced_ops = dict[mir.StoreOp | mir.LoadOp, mir.LoadOp]()
    for pair in pairs:
        local_id = pair.a.local_id
        # step 1. copy define or use to bottom of stack

        # note: pairs may refer to ops that have been replaced by an earlier iteration
        a = replaced_ops.get(pair.a, pair.a)
        # redetermine index as block ops may have changed
        a_index = block.ops.index(a)

        # insert replacement before store, or after load
        insert_index = a_index if isinstance(a, mir.StoreVirtual) else a_index + 1
        store_height = block.get_stack_height(insert_index)
        dup = mir.StoreLStack(
            depth=store_height - 1,
            local_id=local_id,
            # leave a copy for the existing virtual store to consume
            # this will be eliminated later if not required
            copy=True,
            source_location=a.source_location,
            atype=a.atype,
        )
        block.ops.insert(insert_index, dup)
        logger.debug(f"Inserted {block.block_name}.ops[{insert_index}]: '{dup}'")

        # step 2. replace b usage with instruction to rotate the value from the bottom of the stack
        b = replaced_ops.get(pair.b, pair.b)
        b_index = block.ops.index(b)

        uncover = mir.LoadLStack(
            depth=None,
            local_id=local_id,
            copy=False,
            source_location=b.source_location,
            atype=b.atype,
        )
        # replace op
        block.ops[b_index] = uncover

        # remember replacement in case it is part of another pair
        replaced_ops[b] = uncover
        logger.debug(f"Replaced {block.block_name}.ops[{b_index}]: '{b}' with '{uncover}'")


def determine_l_stack_depth(ctx: SubroutineCodeGenContext) -> None:
    for block in ctx.subroutine.body:
        stack = list[str]()
        for idx, op in enumerate(block.ops):
            match op:
                case mir.StoreLStack(local_id=local_id) as store:
                    index = len(stack) - store.depth - 1
                    stack.pop()
                    stack.insert(index, local_id)
                    stack.extend(store.produces)
                case mir.LoadLStack(local_id=local_id) as load:
                    block.ops[idx] = attrs.evolve(op, depth=len(stack) - stack.index(local_id) - 1)
                    if not load.copy:
                        stack.remove(local_id)
                    stack.append("")
                case _:
                    if op.consumes:
                        stack = stack[: -op.consumes]
                    stack.extend(op.produces)
    ctx.l_stack_depth_calculated = True


def _get_lstack_before_op(block: mir.MemoryBasicBlock, target_index: int) -> Sequence[str]:
    stack = list[str]()
    for op in block.ops[:target_index]:
        match op:
            case mir.StoreLStack(local_id=local_id) as store:
                assert store.copy
                stack.insert(0, local_id)
                stack.append("")
            case mir.LoadLStack(local_id=local_id) as load:
                assert not load.copy
                stack.remove(local_id)
                stack.append("")
            case _:
                if op.consumes:
                    stack = stack[: -op.consumes]
                stack.extend(op.produces)
        delta = len(op.produces) - op.consumes
        assert delta == op.accept(StackDelta()), "invalid delta"
    return stack


class StackDelta(MIRVisitor[int]):

    def visit_int(self, _: mir.Int) -> int:
        return 1

    def visit_byte(self, _: mir.Byte) -> int:
        return 1

    def visit_comment(self, _: mir.Comment) -> int:
        return 0

    def visit_store_l_stack(self, store: mir.StoreLStack) -> int:
        return 1 if store.copy else 0

    def visit_load_l_stack(self, load: mir.LoadLStack) -> int:
        return 1 if load.copy else 0

    def visit_store_x_stack(self, _: mir.StoreXStack) -> int:
        return 0

    def visit_load_x_stack(self, _: mir.LoadXStack) -> int:
        return 0

    def visit_store_f_stack(self, _: mir.StoreFStack) -> int:
        return -1

    def visit_load_f_stack(self, _: mir.LoadFStack) -> int:
        return 1

    def visit_load_param(self, _: mir.LoadParam) -> int:
        return 1

    def visit_store_param(self, _: mir.StoreParam) -> int:
        return -1

    def visit_store_virtual(self, _: mir.StoreVirtual) -> int:
        return -1

    def visit_load_virtual(self, _: mir.LoadVirtual) -> int:
        return 1

    def visit_proto(self, _: mir.Proto) -> int:
        return 0

    def visit_allocate(self, allocate: mir.Allocate) -> int:
        return allocate.num_bytes + allocate.num_uints

    def visit_pop(self, pop: mir.Pop) -> int:
        return -pop.n

    def visit_callsub(self, callsub: mir.CallSub) -> int:
        return callsub.returns - callsub.parameters

    def visit_retsub(self, _: mir.RetSub) -> int:
        return 0

    def visit_intrinsic(self, intrinsic: mir.IntrinsicOp) -> int:
        produces = len(intrinsic.produces)
        return produces - intrinsic.consumes

    def visit_virtual_stack(self, _: mir.VirtualStackOp) -> int:
        return 0

    def visit_address(self, _: mir.Address) -> int:
        return 1

    def visit_method(self, _: mir.Method) -> int:
        return 1

    def visit_template_var(self, _: mir.TemplateVar) -> int:
        return 1
