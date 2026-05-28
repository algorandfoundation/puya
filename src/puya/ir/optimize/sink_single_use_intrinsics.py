import itertools
import typing

from puya import algo_constants, log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize._utils import SSAReadTracker
from puya.utils import is_list_of

logger = log.get_logger(__name__)


# Single-input, single-output AVM ops that cannot fail on any input the IR's
# type system already considers valid. Excluded on purpose:
#   - btoi              panics if the input is > 8 bytes
#   - extract/substring panics on out-of-bounds indices
#   - bzero             panics if the requested length > 4096
#   - bsqrt             panics on inputs encoding > 2^512
# Keep this list conservative -- a "may fail" op here can re-order an implicit
# assertion past observable side effects.
_NEVER_FAIL_UNARY_OPS: typing.Final = frozenset(
    {
        # group: ops that can't fail at runtime
        # `txn FirstValidTime` technically could fail, but shouldn't happen on mainnet?
        "txn",
        "sha256",
        "keccak256",
        "sha3_256",
        "sha512_256",
        "bitlen",
        # group: could only fail on a type error
        "!",
        "!=",
        "&",
        "&&",
        "<",
        "<=",
        "==",
        ">",
        ">=",
        "|",
        "||",
        "~",
        "addw",
        "mulw",
        "itob",
        "len",
        "select",
        "sqrt",
        "shl",
        "shr",
        "b&",
        "b|",
        "b~",
    }
)


def sink_single_use_intrinsics(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    """Move never-fail single-input intrinsic assignments next to their sole consumer.

    Fires when:
      - the assignment's source is an Intrinsic in `_NEVER_FAIL_UNARY_OPS` with
        exactly one Value argument,
      - the assignment has exactly one target register,
      - that register has exactly one reader in the whole subroutine,
      - the reader lives in the same block, after the assignment,
      - the reader's register-read set is exactly {target}.

    The intrinsic's *input* register is not touched. SSA guarantees it is
    defined before the original position, so it is still in scope at the new
    position.
    """
    ssa_reads = SSAReadTracker()
    for block in subroutine.body:
        for op in block.all_ops:
            ssa_reads.add(op)

    modified = False
    moving_assignment = {}
    for block in subroutine.body:
        ops = []
        for op, next_op in itertools.zip_longest(block.ops, block.ops[1:]):
            ops.append(op)
            match op:
                case models.Assignment(
                    targets=[target],
                    source=models.Intrinsic(op=intrinsic_op, args=[*args]),
                ) if (
                    (
                        intrinsic_op.code in _NEVER_FAIL_UNARY_OPS
                        or (
                            intrinsic_op is AVMOp.bzero
                            and len(args) == 1
                            and isinstance((bzero_arg := args[0]), models.UInt64Constant)
                            and bzero_arg.value <= algo_constants.MAX_BYTES_LENGTH
                        )
                    )
                    and len(readers := list(ssa_reads.get(target))) == 1
                    and is_list_of(args, models.Constant)  # type: ignore[type-abstract]
                ):
                    (reader,) = readers
                    if reader is next_op:
                        continue
                    match reader:
                        case models.Intrinsic(args=[single_arg]):
                            pass
                        case models.Assignment(source=models.Intrinsic(args=[single_arg])):
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
                    moved = moving_assignment.pop(op)  # type: ignore[call-overload]
                except KeyError:
                    pass
                else:
                    ops.append(moved)
                ops.append(op)
            block.ops[:] = ops

    return modified
