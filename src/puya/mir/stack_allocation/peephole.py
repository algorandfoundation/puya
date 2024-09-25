from collections.abc import Sequence

import attrs

from puya.mir import models as mir
from puya.mir.context import SubroutineCodeGenContext


def optimize_pair(
    ctx: SubroutineCodeGenContext,
    a: mir.BaseOp,
    # represents virtual ops that may be between a and b
    maybe_virtuals: Sequence[mir.BaseOp],
    b: mir.BaseOp,
) -> Sequence[mir.BaseOp] | None:
    """Given a pair of ops, returns which ops should be kept including replacements"""

    # this function has been optimized to reduce the number of isinstance checks,
    # consider this when making any modifications

    # goal: get rid of VirtualStackOp
    # goal: remove usage of stack in mir
    # goal: stack can then be refactored into a teal op builder?
    #       minimal stack manipulations on teal ops?
    # move local_id into produces of previous op, and eliminate redundant stores where possible
    # TODO: can we simplify a sequence of Stores following a tuple load?
    # TODO: other stores
    # move local_ids to source where possible
    if (
        not maybe_virtuals
        and isinstance(b, mir.StoreLStack | mir.StoreXStack | mir.StoreFStack)
        and len(a.produces)
        and a.produces[-1] != b.local_id
    ):
        a = attrs.evolve(a, produces=(*a.produces[:-1], b.local_id))
        return a, b

    # remove redundant stores and loads
    if not maybe_virtuals and a.produces and a.produces[-1] == _get_local_id_alias(b):
        return (a,)

    if isinstance(b, mir.StoreVirtual) and b.local_id not in ctx.vla.get_live_out_variables(b):
        # aka dead store removal
        match a:
            case mir.StoreLStack(copy=True) as cover:
                assert not ctx.l_stack_depth_calculated, "dead store no longer allowed"
                # StoreLStack is used to:
                #   1.) store a variable for retrieval later via a load
                #   2.) store a copy at the bottom of the stack for use in a later op
                # If it is a dead store, then the 1st scenario is no longer needed
                # and instead just need to ensure the value is moved to the bottom of the stack
                return attrs.evolve(cover, copy=False, produces=()), *maybe_virtuals
        return a, mir.Pop(n=1, source_location=b.source_location), *maybe_virtuals

    # optimization: cases after here are only applicable if "a" is a MemoryOp
    if not isinstance(a, mir.MemoryOp):
        return None

    if isinstance(b, mir.Pop) and b.n == 1 and isinstance(a, mir.LoadOp):
        return mir.VirtualStackOp(a), *maybe_virtuals, mir.VirtualStackOp(b)

    # optimization: cases after here are only applicable if "b" is a MemoryOp
    if not isinstance(b, mir.MemoryOp):
        return None

    if _is_redundant_rotate(a, b):
        return mir.VirtualStackOp(a), *maybe_virtuals, mir.VirtualStackOp(b)

    if isinstance(a, mir.LoadOp) and isinstance(b, mir.StoreOp) and a.local_id == b.local_id:
        match a, b:
            case mir.LoadLStack(copy=False) as load, mir.StoreLStack(copy=True):
                assert not ctx.l_stack_depth_calculated
                return (
                    attrs.evolve(
                        load,
                        copy=True,
                        produces=(f"{load.local_id} (copy)",),
                    ),
                    *maybe_virtuals,
                )
            # consider this sequence Load*, Virtual(Store*), Virtual(Load*), Store*
            # can't just remove outer virtuals because inner virtual ops assume "something"
            # loaded a value onto the stack, so need to keep entire sequence around as
            # virtual ops
            case mir.LoadXStack(), mir.StoreXStack():
                if maybe_virtuals:
                    return mir.VirtualStackOp(a), *maybe_virtuals, mir.VirtualStackOp(b)
                else:
                    return ()
            case mir.LoadFStack(), mir.StoreFStack():
                if maybe_virtuals:
                    return mir.VirtualStackOp(a), *maybe_virtuals, mir.VirtualStackOp(b)
                else:
                    return ()
            case mir.LoadVirtual(), mir.StoreVirtual():
                if maybe_virtuals:
                    return mir.VirtualStackOp(a), *maybe_virtuals, mir.VirtualStackOp(b)
                else:
                    return ()
    return None


@attrs.define(kw_only=True)
class PeepholeResult:
    modified: bool
    vla_modified: bool


def peephole_optimization_single_pass(
    ctx: SubroutineCodeGenContext, block: mir.MemoryBasicBlock
) -> PeepholeResult:
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
            pair_result = optimize_pair(ctx, curr_op, virtuals, next_op)
            if pair_result is not None:
                modified = modified_pair = True
                result[curr_op_idx : next_op_idx + 1] = pair_result
                # check if "next" was a virtual store/load and was removed/modified,
                # if so VLA needs updating
                # note we check the "current" at the end of the loop
                vla_modified = vla_modified or (
                    next_op not in pair_result[-1:]
                    and isinstance(next_op, mir.StoreVirtual | mir.LoadVirtual)
                )

        # optimize the "current" op, if possible
        # result[curr_op_idx] = optimize_single(stack, result[curr_op_idx])
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
            # so we can advance to the next
            curr_op_idx += 1

    return PeepholeResult(modified=modified, vla_modified=vla_modified)


def _is_redundant_rotate(a: mir.MemoryOp, b: mir.MemoryOp) -> bool:
    rot_a = _get_rotation(a)
    if rot_a is None:
        return False
    rot_b = _get_rotation(b)
    if rot_b is None:
        return False
    # rotate left + rotate right
    if rot_a + rot_b == 0:
        return True
    # two swaps
    return rot_a == rot_b and rot_a in (1, -1)


def _get_rotation(op: mir.MemoryOp) -> int | None:
    match op:
        case (
            mir.StoreLStack(copy=False) | mir.StoreXStack() | mir.StoreFStack(insert=True) as store
        ):
            return store.depth
        case mir.LoadLStack(copy=False, depth=int(depth)) | mir.LoadXStack(depth=depth):
            return depth
    return None


def _get_local_id_alias(op: mir.BaseOp) -> str | None:
    """Returns the local_id of a memory op if it has no effect
    apart from renaming the top variable on the stack"""
    if isinstance(op, mir.StoreLStack | mir.LoadLStack) and not op.copy and not op.depth:
        return op.local_id
    # TODO: the following can only be done if the movement between l-stack and the other stack
    #       is captured somehow (also check assumption that it needs to be captured...)
    # if isinstance(op, mir.StoreXStack | mir.LoadXStack) and not op.depth:
    #    return op.local_id
    # if isinstance(op, mir.StoreFStack) and op.insert and not op.depth:
    #    return op.local_id
    return None
