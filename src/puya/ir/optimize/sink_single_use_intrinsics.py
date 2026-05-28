import typing
from collections.abc import Set

from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize._utils import SSAReadTracker
from puya.ir.register_read_collector import RegisterReadCollector

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
        AVMOp.itob,
        AVMOp.not_,
        AVMOp.bitwise_not,
        AVMOp.bitwise_not_bytes,
        AVMOp.len_,
        AVMOp.bitlen,
        AVMOp.sha256,
        AVMOp.sha512_256,
        AVMOp.sha3_256,
        AVMOp.keccak256,
        AVMOp.sqrt,
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
    for block in subroutine.body:
        modified |= _sink_in_block(block, ssa_reads)
    return modified


def _sink_in_block(block: models.BasicBlock, ssa_reads: SSAReadTracker) -> bool:
    modified = False
    ops = block.ops
    i = 0
    while i < len(ops):
        op = ops[i]
        target = _candidate_target(op)
        if target is None or ssa_reads.count(target) != 1:
            i += 1
            continue
        consumer_idx = _find_consumer_in_ops(ops, target, start=i + 1)
        if consumer_idx is not None:
            consumer: models.Op | models.ControlOp = ops[consumer_idx]
        elif block.terminator is not None and target in _reads_of(block.terminator):
            consumer = block.terminator
        else:
            # consumer is in a phi or a successor block; skip
            i += 1
            continue
        if _reads_of(consumer) != {target}:
            i += 1
            continue
        if consumer_idx is None:
            new_idx = len(ops) - 1  # position of the last op after pop
        else:
            new_idx = consumer_idx - 1
        if new_idx == i:
            # already adjacent; nothing to do
            i += 1
            continue
        moved = ops.pop(i)
        ops.insert(new_idx, moved)
        logger.debug(
            f"sunk {moved} to immediately before sole consumer",
            location=moved.source_location,
        )
        modified = True
        # do not advance i: the slot at i now holds a different op.
    return modified


def _candidate_target(op: models.Op) -> models.Register | None:
    match op:
        case models.Assignment(
            targets=[target],
            source=models.Intrinsic(op=intr_op, args=[models.Constant()]),
        ) if intr_op in _NEVER_FAIL_UNARY_OPS:
            return target
    return None


def _find_consumer_in_ops(
    ops: list[models.Op], target: models.Register, *, start: int
) -> int | None:
    for j in range(start, len(ops)):
        if target in _reads_of(ops[j]):
            return j
    return None


def _reads_of(visitable: models.IRVisitable) -> Set[models.Register]:
    collector = RegisterReadCollector()
    visitable.accept(collector)
    return collector.used_registers
