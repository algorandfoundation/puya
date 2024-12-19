from collections.abc import Sequence

import attrs

from puya.mir import models as mir
from puya.mir.context import SubroutineCodeGenContext


def optimize_pair(
    ctx: SubroutineCodeGenContext,
    a: mir.Op,
    b: mir.Op,
) -> Sequence[mir.Op] | None:
    """Given a pair of ops, returns which ops should be kept including replacements"""
    # this function has been optimized to reduce the number of isinstance checks,
    # consider this when making any modifications

    # move local_ids to produces of previous op where possible
    if (
        isinstance(b, mir.StoreLStack | mir.StoreXStack | mir.StoreFStack)
        and len(a.produces)
        and a.produces[-1] != b.local_id
    ):
        a = attrs.evolve(a, produces=(*a.produces[:-1], b.local_id))
        return a, b

    # remove redundant stores and loads
    if a.produces and a.produces[-1] == _get_local_id_alias(b):
        return (a,)

    if isinstance(b, mir.AbstractStore) and b.local_id not in ctx.vla.get_live_out_variables(b):
        # note l-stack dead store removal occurs during l-stack allocation
        # this handles any other cases
        return a, mir.Pop(n=1, source_location=b.source_location)

    if isinstance(a, mir.LoadOp) and isinstance(b, mir.StoreOp) and a.local_id == b.local_id:
        match a, b:
            case mir.LoadXStack(), mir.StoreXStack():
                return ()
            case mir.LoadFStack(), mir.StoreFStack():
                return ()
            case mir.AbstractLoad(), mir.AbstractStore():
                # this is used see test_cases/bug_load_store_load_store
                return ()
    return None


@attrs.define(kw_only=True)
class PeepholeResult:
    modified: bool
    vla_modified: bool


def peephole_optimization_single_pass(
    ctx: SubroutineCodeGenContext, block: mir.MemoryBasicBlock
) -> PeepholeResult:
    result = block.mem_ops
    op_idx = 0
    modified = False
    vla_modified = False
    while op_idx < len(result) - 1:
        window = slice(op_idx, op_idx + 2)
        curr_op, next_op = result[window]
        pair_result = optimize_pair(ctx, curr_op, next_op)
        if pair_result is not None:
            modified = True
            result[window] = pair_result
            # check if VLA needs updating
            vla_modified = (
                vla_modified
                or (
                    curr_op not in pair_result
                    and isinstance(curr_op, mir.AbstractStore | mir.AbstractLoad)
                )
                or (
                    next_op not in pair_result
                    and isinstance(next_op, mir.AbstractStore | mir.AbstractLoad)
                )
            )
        else:  # if nothing optimized, then advance
            op_idx += 1
    return PeepholeResult(modified=modified, vla_modified=vla_modified)


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
