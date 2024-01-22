from typing import Sequence

import attrs

from puya.mir import models as mir
from puya.mir.context import SubroutineCodeGenContext
from puya.mir.stack import Stack
from puya.teal import models as teal
from puya.teal.optimize.peephole import is_redundant_rotate as is_redundant_rotate_teal


def optimize_single(stack_before_a: Stack, a: mir.BaseOp) -> mir.BaseOp:
    if isinstance(a, mir.MemoryOp):
        teal_ops = a.accept(stack_before_a.copy())
        match teal_ops:
            case [teal.Cover(0) | teal.Uncover(0)]:
                return mir.VirtualStackOp(a)
    return a


def is_redundant_rotate_mir(
    stack: Stack, a: mir.MemoryOp, maybe_virtuals: Sequence[mir.BaseOp], b: mir.MemoryOp
) -> bool:
    stack_after_a = stack.copy()
    a_teal = a.accept(stack_after_a)
    try:
        (a_op,) = a_teal
    except ValueError:
        return False

    # optimization: the virtual op is applied here instead of outside optimize_pair
    # as it is a hot path so deferring it until it is actually required saves some time

    stack = stack_after_a.copy()
    for virtual in maybe_virtuals:
        virtual.accept(stack)
    b_teal = b.accept(stack)
    try:
        (b_op,) = b_teal
    except ValueError:
        return False
    return is_redundant_rotate_teal(a_op, b_op)


def optimize_pair(
    ctx: SubroutineCodeGenContext,
    stack: Stack,  # stack state before a
    a: mir.BaseOp,
    # represents virtual ops that may be between a and b
    maybe_virtuals: Sequence[mir.BaseOp],
    b: mir.BaseOp,
) -> Sequence[mir.BaseOp] | None:
    """Given a pair of ops, returns which ops should be kept including replacements"""

    # this function has been optimized to reduce the number of isinstance checks,
    # consider this when making any modifications

    if isinstance(b, mir.StoreVirtual) and b.local_id not in ctx.vla.get_live_out_variables(b):
        # aka dead store removal
        match a:
            case mir.StoreLStack(copy=True) | mir.StoreXStack(copy=True) as cover:
                # this should handle both x-stack and l-stack cases StoreLStack is used to:
                #   1.) store a variable for retrieval later via a load
                #   2.) store a copy at the bottom of the stack for use in a later op
                # If it is a dead store, then the 1st scenario is no longer needed
                # and instead just need to ensure the value is moved to the bottom of the stack
                return attrs.evolve(cover, copy=False), *maybe_virtuals
        return a, mir.Pop(n=1, source_location=b.source_location), *maybe_virtuals

    # optimization: cases after here are only applicable if "a" is a MemoryOp
    if not isinstance(a, mir.MemoryOp):
        return None

    if isinstance(b, mir.Pop) and b.n == 1 and isinstance(a, mir.LoadOp):
        return mir.VirtualStackOp(a), *maybe_virtuals, mir.VirtualStackOp(b)

    # optimization: cases after here are only applicable if "b" is a MemoryOp
    if not isinstance(b, mir.MemoryOp):
        return None

    if is_redundant_rotate_mir(stack, a, maybe_virtuals, b):
        match a, b:
            case (
                mir.LoadLStack(copy=False, local_id=a_local_id),
                mir.StoreLStack(copy=False, local_id=b_local_id),
            ) if a_local_id == b_local_id:
                # loading and storing to the same spot in the same stack can be removed entirely
                # if the local_id does not change
                return maybe_virtuals
        # otherwise keep around as virtual stack op
        return mir.VirtualStackOp(a), *maybe_virtuals, mir.VirtualStackOp(b)

    if isinstance(a, mir.LoadOp) and isinstance(b, mir.StoreOp):
        if a.local_id == b.local_id:
            match a, b:
                case mir.LoadLStack(copy=False) as load, mir.StoreLStack(copy=True):
                    return attrs.evolve(load, copy=True), *maybe_virtuals
                case mir.LoadXStack(), mir.StoreXStack(copy=False):
                    return maybe_virtuals
                case mir.LoadFStack(), mir.StoreFStack():
                    return maybe_virtuals
                case mir.LoadVirtual(), mir.StoreVirtual():
                    return maybe_virtuals
    else:
        match a, b:
            case (
                mir.StoreParam(copy=False, local_id=a_local_id) as store_param,
                mir.LoadParam(local_id=b_local_id),
            ) if a_local_id == b_local_id:
                # if we have a store to param and then read from param,
                # we can reduce the program size byte 1 byte by copying
                # and then storing instead
                # i.e. frame_bury -x; frame_dig -x
                # =>   dup; frame_bury -x
                store_with_copy = attrs.evolve(store_param, copy=True)
                return store_with_copy, *maybe_virtuals
    return None


@attrs.define(kw_only=True)
class PeepholeResult:
    modified: bool
    vla_modified: bool


def peephole_optimization_single_pass(
    ctx: SubroutineCodeGenContext, block: mir.MemoryBasicBlock
) -> PeepholeResult:
    stack = Stack.for_full_stack(ctx.subroutine, block)

    result = block.ops
    curr_op_idx = 0
    modified = False
    vla_modified = False
    while curr_op_idx < len(result):
        # find the "current" non-virtual op
        while curr_op_idx < len(result):
            original_op = result[curr_op_idx]
            if type(original_op) is not mir.VirtualStackOp:
                break
            # we still need to visit the op, to update the virtual stack
            original_op.accept(stack)
            curr_op_idx += 1
        else:
            break  # all remaining ops are virtual, we're done

        # find the "next" non-virtual op, if there is one remaining
        next_op_idx = curr_op_idx + 1
        while next_op_idx < len(result) and type(result[next_op_idx]) is mir.VirtualStackOp:
            # don't visit the ops because they're not processed yet,
            # stack should always be the state _before_ the "current" op
            next_op_idx += 1

        # if we have a "next" op, try and optimize the pair, crossing but retaining
        # any virtual ops in between
        modified_pair = False
        if next_op_idx < len(result):
            curr_op, *virtuals, next_op = result[curr_op_idx : next_op_idx + 1]
            pair_result = optimize_pair(ctx, stack, curr_op, virtuals, next_op)
            if pair_result is not None:
                modified = modified_pair = True
                result[curr_op_idx : next_op_idx + 1] = pair_result
                # check if "next" was a virtual store/load and was removed/modified,
                # if so VLA needs updating
                # note we check the "current" at the end of the loop
                vla_modified = vla_modified or (
                    next_op is not pair_result[-1]
                    and isinstance(next_op, mir.StoreVirtual | mir.LoadVirtual)
                )

        # optimize the "current" op, if possible
        result[curr_op_idx] = optimize_single(stack, result[curr_op_idx])
        # check if we've updated "current" at all, in this iteration,
        # note this could have been done in optimize_pair
        if original_op is not result[curr_op_idx]:
            modified = True
            # now we check (once) if "current" has changed such that VLA requires an update
            vla_modified = vla_modified or isinstance(
                original_op, mir.StoreVirtual | mir.LoadVirtual
            )
            # we will visit this "current" again in the next iteration now,
            # in case there are further pair/single optimizations to be made this pass
        elif not modified_pair:
            # otherwise, "current" has not been changed by this loop iteration,
            # and neither has any "next" if it existed,
            # so we can visit current and advance to the next
            original_op.accept(stack)
            curr_op_idx += 1

    return PeepholeResult(modified=modified, vla_modified=vla_modified)
