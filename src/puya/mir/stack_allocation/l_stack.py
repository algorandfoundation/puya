import itertools

import attrs

from puya import log
from puya.mir import models as mir
from puya.mir.context import SubroutineCodeGenContext

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


def l_stack_allocation(ctx: SubroutineCodeGenContext) -> None:
    # the following is basically koopmans algorithm
    for block in ctx.subroutine.body:
        usage_pairs = find_usage_pairs(block)
        copy_usage_pairs(block, usage_pairs)
    for block in ctx.subroutine.body:
        dead_store_removal(ctx, block)
    # update vla after dead store removal
    ctx.invalidate_vla()
    # calculate load depths now that l-stack allocations are done
    for block in ctx.subroutine.body:
        calculate_load_depths(block)


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


def dead_store_removal(ctx: SubroutineCodeGenContext, block: mir.MemoryBasicBlock) -> None:
    ops = block.ops
    op_idx = 0
    while op_idx < len(ops) - 1:
        window = slice(op_idx, op_idx + 2)
        a, b = ops[window]
        if (
            isinstance(a, mir.StoreLStack)
            and a.copy
            and isinstance(b, mir.StoreVirtual)
            and b.local_id not in ctx.vla.get_live_out_variables(b)
        ):
            # StoreLStack is used to:
            #   1.) create copy of the value to be immediately stored via virtual store
            #   2.) rotate the value to the bottom of the stack for use in a later op in this block
            # If it is a dead store, then the 1st scenario is no longer needed
            # and instead just need to ensure the value is moved to the bottom of the stack
            a = attrs.evolve(a, copy=False, produces=())
            ops[window] = [a]
        elif (
            isinstance(a, mir.LoadLStack)
            and not a.copy
            and isinstance(b, mir.StoreLStack)
            and b.copy
            and a.local_id == b.local_id
        ):
            a = attrs.evolve(
                a,
                copy=True,
                produces=(f"{a.local_id} (copy)",),
            )
            ops[window] = [a]
        op_idx += 1


def calculate_load_depths(block: mir.MemoryBasicBlock) -> None:
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
                stack.extend(op.produces)
            case _:
                if op.consumes:
                    stack = stack[: -op.consumes]
                stack.extend(op.produces)
