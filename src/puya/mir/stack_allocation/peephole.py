from collections.abc import Sequence

import attrs

from puya.mir import models as mir
from puya.mir.context import ProgramMIRContext
from puya.mir.vla import VariableLifetimeAnalysis


def peephole_optimization_single_pass(_ctx: ProgramMIRContext, sub: mir.MemorySubroutine) -> bool:
    vla = VariableLifetimeAnalysis(sub)
    modified = False
    for block in sub.body:
        result = block.mem_ops
        op_idx = 0
        while op_idx < len(result) - 1:
            window = slice(op_idx, op_idx + 2)
            curr_op, next_op = result[window]
            pair_result = _optimize_pair(vla, curr_op, next_op)
            if pair_result is not None:
                modified = True
                result[window] = pair_result
            else:  # if nothing optimized, then advance
                op_idx += 1
    return modified


def _optimize_pair(vla: VariableLifetimeAnalysis, a: mir.Op, b: mir.Op) -> Sequence[mir.Op] | None:
    """Given a pair of ops, returns which ops should be kept including replacements"""

    if vla.is_dead_store(b):
        # note l-stack dead store removal occurs during l-stack allocation
        # this handles any other cases
        return a, mir.Pop(n=1, source_location=b.source_location)

    if a.produces and hasattr(b, "local_id"):
        if isinstance(a, mir.LoadOp) and isinstance(b, mir.StoreOp) and a.local_id == b.local_id:
            match a, b:
                case mir.LoadXStack(), mir.StoreXStack():
                    return ()
                case mir.LoadFStack(), mir.StoreFStack():
                    return ()
                case mir.AbstractLoad(), mir.AbstractStore():
                    # this is used see test_cases/bug_load_store_load_store
                    return ()

        # remove redundant stores and loads
        if (
            isinstance(b, mir.StoreLStack | mir.LoadLStack) and b.depth == 0 and not b.copy
        ) and a.produces[-1] == b.local_id:
            return (a,)

        # move local_ids to produces of previous op where possible
        if (
            isinstance(b, mir.StoreLStack | mir.StoreXStack | mir.StoreFStack)
            and a.produces[-1] != b.local_id
        ):
            a = attrs.evolve(a, produces=(*a.produces[:-1], b.local_id))
            return a, b

    return None
