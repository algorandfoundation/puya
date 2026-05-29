import itertools

from puya import algo_constants, log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize._utils import SSAReadTracker

logger = log.get_logger(__name__)


def sink_single_use_intrinsics(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    """Move a never-fail intrinsic assignment to sit immediately before its sole consumer.

    Fires when:
      - the assignment's source is a sinkable intrinsic (see `_is_sinkable`),
      - the assignment has a single target register,
      - that register has exactly one reader in the whole subroutine,
      - the reader consumes the register as its only argument.

    Co-locating the producer with its consumer lets later passes keep the value
    on the stack rather than spilling it. The reorder is safe because the
    intrinsic cannot fail -- so it can't drag an implicit assertion past an
    observable side effect -- and worthwhile because it reads no registers, so
    moving it can't extend another value's live range and add yet more stack
    shuffling.
    """
    ssa_reads = SSAReadTracker()
    for block in subroutine.body:
        for op in block.all_ops:
            ssa_reads.add(op)

    # reader op -> the assignment that should be relocated immediately in front of it
    sink_before = dict[models.Op, models.Op]()
    for block in subroutine.body:
        kept = list[models.Op]()
        for op, next_op in itertools.zip_longest(block.ops, block.ops[1:]):
            reader = _sink_destination(op, ssa_reads)
            if reader is None or reader is next_op:
                # not a candidate, or already adjacent to its consumer
                kept.append(op)
            else:
                sink_before[reader] = op
                logger.debug(f"moving {op} to be co-located with sole usage {reader}")
        block.ops[:] = kept

    if not sink_before:
        return False

    for block in subroutine.body:
        relocated = list[models.Op]()
        for op in block.ops:
            moved = sink_before.pop(op, None)
            if moved is not None:
                relocated.append(moved)
            relocated.append(op)
        block.ops[:] = relocated
    return True


def _sink_destination(op: models.Op, ssa_reads: SSAReadTracker) -> models.Op | None:
    """The consumer `op` should be moved in front of, or None if `op` isn't a candidate."""
    match op:
        case models.Assignment(
            targets=[target], source=models.Intrinsic() as source
        ) if _is_sinkable(source):
            pass
        case _:
            return None

    readers = ssa_reads.get(target)
    try:
        (reader,) = iter(readers)
    except ValueError:
        return None
    # only sink onto a consumer that takes the value as its sole argument, so the
    # relocated push lands directly beneath the consuming op
    match reader:
        case (
            models.Intrinsic(args=[single_arg])
            | models.Assignment(source=models.Intrinsic(args=[single_arg]))
        ):
            assert single_arg == target, "sole reader must consume the sunk register"
            return reader
        case _:
            return None


def _is_sinkable(intrinsic: models.Intrinsic) -> bool:
    """Whether `intrinsic` is both safe and worthwhile to relocate next to its consumer.

    Two conditions, both required:
      - it cannot fail at runtime, so reordering it past an implicit assertion
        can't move that failure relative to an observable side effect;
      - it reads no registers (constant operands, or none at all), so relocating
        it can't extend another value's live range and introduce yet more stack
        shuffling -- which would defeat the point of the pass.

    Each op is matched with its own shape rather than a shared op-code set, since
    there are only a handful.
    """
    match intrinsic:
        # `txn` has no operands (the field is an immediate);
        # `txn FirstValidTime` technically could fail, but shouldn't happen on mainnet
        case models.Intrinsic(op=AVMOp.txn, args=[]):
            return True
        # `itob` never fails for any uint64; the constant operand is what we
        # require here, so the relocation doesn't pull a register read down with it
        case models.Intrinsic(op=AVMOp.itob, args=[models.Constant()]):
            return True
        case models.Intrinsic(op=AVMOp.bzero, args=[models.UInt64Constant(value=length)]):
            # bzero panics if the requested length exceeds the max byte-array size
            return length <= algo_constants.MAX_BYTES_LENGTH
        case _:
            return False
