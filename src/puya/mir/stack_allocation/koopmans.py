import itertools

import attrs

from puya import log
from puya.mir import models as mir
from puya.mir.context import SubroutineCodeGenContext
from puya.mir.stack import Stack

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


def _get_stack_after_op(
    subroutine: mir.MemorySubroutine, block: mir.MemoryBasicBlock, target_op: mir.BaseOp | int
) -> Stack:
    stack = Stack.for_full_stack(subroutine, block)
    if isinstance(target_op, int):
        if target_op == -1:
            return stack
        assert target_op >= 0

    for idx, op in enumerate(block.ops):
        op.accept(stack)
        if target_op in (op, idx):
            break

    return stack


def copy_usage_pairs(
    subroutine: mir.MemorySubroutine, block: mir.MemoryBasicBlock, pairs: list[UsagePair]
) -> None:
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
        # determine stack height at point of insertion
        insert_stack_in = _get_stack_after_op(subroutine, block, insert_index - 1)

        dup = mir.StoreLStack(
            cover=len(insert_stack_in.l_stack) - 1,
            local_id=local_id,
            source_location=a.source_location,
            atype=a.atype,
        )
        block.ops.insert(insert_index, dup)
        logger.debug(f"Inserted {block.block_name}.ops[{insert_index}]: '{dup}'")

        # step 2. replace b usage with instruction to rotate the value from the bottom of the stack
        b = replaced_ops.get(pair.b, pair.b)
        b_index = block.ops.index(b)

        uncover = mir.LoadLStack(
            local_id=local_id,
            source_location=b.source_location,
            atype=b.atype,
        )
        # replace op
        block.ops[b_index] = uncover

        # remember replacement in case it is part of another pair
        replaced_ops[b] = uncover
        logger.debug(f"Replaced {block.block_name}.ops[{b_index}]: '{b}' with '{uncover}'")


def koopmans(ctx: SubroutineCodeGenContext) -> None:
    for block in ctx.subroutine.body:
        usage_pairs = find_usage_pairs(block)
        copy_usage_pairs(ctx.subroutine, block, usage_pairs)
