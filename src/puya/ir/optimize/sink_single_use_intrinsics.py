import itertools
import typing

from puya import algo_constants, log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize._utils import SSAReadTracker

logger = log.get_logger(__name__)


# Keep this list conservative -- a "may fail" op here can re-order an implicit
# assertion past observable side effects.
_NEVER_FAIL_UNARY_OPS: typing.Final = frozenset(
    {
        # `txn FirstValidTime` technically could fail, but shouldn't happen on mainnet
        AVMOp.txn,
        AVMOp.itob,
    }
)


def sink_single_use_intrinsics(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    """Move never-fail intrinsic assignments next to their sole consumer."""
    ssa_reads = SSAReadTracker()
    for block in subroutine.body:
        for op in block.all_ops:
            ssa_reads.add(op)

    modified = False
    moving_assignment = dict[models.Op, models.Assignment]()
    for block in subroutine.body:
        ops = list[models.Op]()
        for op, next_op in itertools.zip_longest(block.ops, block.ops[1:]):
            ops.append(op)
            match op:
                case models.Assignment(
                    targets=[target],
                    source=models.Intrinsic(
                        op=AVMOp.bzero,
                        args=[models.UInt64Constant(value=bzero_value)],
                    ),
                ) if bzero_value <= algo_constants.MAX_BYTES_LENGTH:
                    pass
                case models.Assignment(
                    targets=[target],
                    source=models.Intrinsic(op=intrinsic_op, args=args),
                ) if (
                    intrinsic_op in _NEVER_FAIL_UNARY_OPS
                    and all(isinstance(a, models.Constant) for a in args)
                ):
                    pass
                case _:
                    continue
            if ssa_reads.count(target) != 1:
                continue
            (reader,) = ssa_reads.get(target)
            if reader is next_op:
                continue
            match reader:
                case (
                    models.Intrinsic(args=[single_arg])
                    | models.Assignment(source=models.Intrinsic(args=[single_arg]))
                ):
                    pass
                case _:
                    continue
            assert single_arg == target
            moving_assignment[reader] = op
            ops.pop()
            logger.debug(f"moving {op} to be co-located with sole usage {reader}")
            modified = True
        block.ops[:] = ops
    if moving_assignment:
        for block in subroutine.body:
            ops = []
            for op in block.ops:
                try:
                    moved = moving_assignment.pop(op)
                except KeyError:
                    pass
                else:
                    ops.append(moved)
                ops.append(op)
            block.ops[:] = ops
        assert not moving_assignment, moving_assignment
    return modified
