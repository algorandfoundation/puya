import itertools

import attrs

from puya import log
from puya.mir import models as mir
from puya.mir.context import ProgramMIRContext
from puya.mir.stack import Stack
from puya.mir.vla import VariableLifetimeAnalysis

logger = log.get_logger(__name__)


@attrs.define
class UsagePair:
    a: mir.AbstractLoad | mir.AbstractStore
    b: mir.AbstractLoad
    a_index: int
    b_index: int

    @staticmethod
    def by_distance(pair: "UsagePair") -> tuple[int, int, int]:
        return pair.b_index - pair.a_index, pair.a_index, pair.b_index


def l_stack_allocation(ctx: ProgramMIRContext, sub: mir.MemorySubroutine) -> None:
    # the following is basically koopmans algorithm
    # done as part of http://www.euroforth.org/ef06/shannon-bailey06.pdf
    # see also https://users.ece.cmu.edu/~koopman/stack_compiler/stack_co.html#appendix
    for block in sub.body:
        usage_pairs = _find_usage_pairs(block)
        _copy_usage_pairs(sub, block, usage_pairs)
    _dead_store_removal(sub)
    if ctx.options.optimization_level:
        _implicit_store_removal(sub)
    # calculate load depths now that l-stack allocations are done
    _calculate_load_depths(sub)


def _find_usage_pairs(block: mir.MemoryBasicBlock) -> list[UsagePair]:
    # find usage pairs of variables within the block
    # the first element of the pair is an op that defines or uses a variable
    # the second element of the pair is an op that uses the variable
    # return pairs in ascending order, based on the number of instruction between each pair
    variables = dict[str, list[tuple[int, mir.AbstractStore | mir.AbstractLoad]]]()
    for index, op in enumerate(block.ops):
        match op:
            case mir.AbstractStore(local_id=local_id) | mir.AbstractLoad(local_id=local_id):
                variables.setdefault(local_id, []).append((index, op))

    pairs = list[UsagePair]()
    for uses in variables.values():
        # pairwise iteration means an op can only be in at most 2 pairs
        for (a_index, a), (b_index, b) in itertools.pairwise(uses):
            if isinstance(b, mir.AbstractStore):
                continue  # skip redefines, if they are used they will be picked up in next pair
            pairs.append(UsagePair(a=a, b=b, a_index=a_index, b_index=b_index))

    return sorted(pairs, key=UsagePair.by_distance)


def _copy_usage_pairs(
    sub: mir.MemorySubroutine, block: mir.MemoryBasicBlock, pairs: list[UsagePair]
) -> None:
    # 1. copy define or use to bottom of l-stack
    # 2. replace usage with instruction to rotate the value from the bottom of l-stack to the top

    # to copy: dup, cover {stack_height}
    # to rotate: uncover {stack_height} - 1
    replaced_ops = dict[mir.StoreOp | mir.LoadOp, mir.LoadOp]()
    for pair in pairs:
        # note: pairs may refer to ops that have been replaced by an earlier iteration
        a = replaced_ops.get(pair.a, pair.a)
        b = replaced_ops.get(pair.b, pair.b)
        local_id = a.local_id
        # step 1. copy define or use to bottom of stack

        # redetermine index as block ops may have changed
        a_index = block.mem_ops.index(a)

        # insert replacement before store, or after load
        insert_index = a_index if isinstance(a, mir.AbstractStore) else a_index + 1
        stack = Stack.begin_block(sub, block)
        for op in block.mem_ops[:insert_index]:
            op.accept(stack)
        dup = mir.StoreLStack(
            depth=len(stack.l_stack) - 1,
            local_id=local_id,
            # leave a copy for the original consumer of this value which is either:
            #   a.) the virtual store we are inserting before
            #   b.) whatever came after the virtual load we are inserting after
            # The copy will be eliminated during dead store removal if no longer required
            copy=True,
            source_location=a.source_location,
            atype=a.atype,
        )
        block.mem_ops.insert(insert_index, dup)
        logger.debug(f"Inserted {block.block_name}.ops[{insert_index}]: '{dup}'")

        # step 2. replace b usage with instruction to rotate the value from the bottom of the stack
        # determine index of b, as inserts may have shifted its location
        b_index = block.mem_ops.index(b)

        uncover = mir.LoadLStack(
            # can not determine depth yet
            # as it depends on any other l-stack operations between the store and this load
            # which could change until after dead store removal is complete
            depth=None,
            local_id=local_id,
            copy=False,
            source_location=b.source_location,
            atype=b.atype,
        )
        # replace op
        block.mem_ops[b_index] = uncover

        # remember replacement in case it is part of another pair
        # an op can only be at most in 2 pairs, so don't need to do this recursively
        replaced_ops[b] = uncover
        logger.debug(f"Replaced {block.block_name}.ops[{b_index}]: '{b}' with '{uncover}'")


def _dead_store_removal(sub: mir.MemorySubroutine) -> None:
    vla = VariableLifetimeAnalysis(sub)
    for block in sub.body:
        ops = block.mem_ops
        op_idx = 0
        while op_idx < len(ops) - 1:
            window = slice(op_idx, op_idx + 2)
            a, b = ops[window]
            # StoreLStack is used to:
            #   1.) create copy of the value to be immediately stored via virtual store
            #   2.) rotate the value to the bottom of the stack for use in a later op in this block
            # If it is a dead store, then the 1st scenario is no longer needed
            # and instead just need to ensure the value is moved to the bottom of the stack
            if isinstance(a, mir.StoreLStack):
                if a.copy and vla.is_dead_store(b):
                    a = attrs.evolve(a, copy=False, produces=())
                    ops[window] = [a]
            elif (
                (isinstance(a, mir.LoadLStack) and not a.copy)
                and (isinstance(b, mir.StoreLStack) and b.copy)
                and a.local_id == b.local_id
            ):
                a = attrs.evolve(
                    a,
                    copy=True,
                    produces=(f"{a.local_id} (copy)",),
                )
                ops[window] = [a]
            op_idx += 1


def _implicit_store_removal(sub: mir.MemorySubroutine) -> None:
    """
    This handles the case where some operation (such as subroutine calls) is evaluated to
    temporary register(s), which are then immediately assigned to other variables, we can eliminate
    the assignment of temporaries and just make the operation assign the other variables directly.
    """
    for block in sub.body:
        ops = block.mem_ops
        op_idx = 0
        while op_idx < len(ops):
            op = ops[op_idx]
            # see if ops immediately after this are all storing to l-stack what this op produces
            next_op_idx = op_idx + 1
            if op.produces:
                produces_window = slice(next_op_idx, next_op_idx + len(op.produces))
                store_ids = [
                    (
                        maybe_store.local_id
                        if isinstance(maybe_store, mir.StoreLStack) and not maybe_store.copy
                        else None
                    )
                    for maybe_store in ops[produces_window]
                ]
                store_ids.reverse()
                # If they all match then this means all values are implicitly on the l-stack
                # and we can safely remove the store ops.
                # We don't need to check the depths since the load depths are not calculated yet.
                if store_ids == op.produces:
                    ops[produces_window] = []
            op_idx = next_op_idx


def _calculate_load_depths(sub: mir.MemorySubroutine) -> None:
    for block in sub.body:
        stack = Stack.begin_block(sub, block)
        for idx, op in enumerate(block.mem_ops):
            if isinstance(op, mir.LoadLStack):
                local_id_index = stack.l_stack.index(op.local_id)
                block.mem_ops[idx] = attrs.evolve(
                    op, depth=len(stack.l_stack) - local_id_index - 1
                )
            op.accept(stack)
