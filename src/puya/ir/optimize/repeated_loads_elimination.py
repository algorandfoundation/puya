from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.types_ import PrimitiveIRType

logger = log.get_logger(__name__)


def constant_reads_and_unobserved_writes_elimination(
    _: CompileContext, subroutine: models.Subroutine
) -> bool:
    any_modified = False
    # TODO: consider dominator blocks
    for block in subroutine.body:
        while _optimise_global_read_write(block):
            any_modified = True
        while _optimise_local_read_write(block):
            any_modified = True
        while _optimise_box_read_write(block):
            any_modified = True
        while _optimise_slot_read_write(block):
            any_modified = True
    return any_modified


def _optimise_global_read_write(block: models.BasicBlock) -> bool:
    modified = False
    read_results = dict[models.Value, tuple[models.Value, models.Value | None]]()
    last_write: models.Intrinsic | None = None
    for op in block.ops:
        match op:
            case models.Assignment(
                targets=[value, exists],
                source=models.Intrinsic(
                    op=AVMOp.app_global_get_ex, args=[models.UInt64Constant(value=0), key]
                ),
            ):
                last_write = None  # doing a read resets
                existing_value, existing_exists = read_results.setdefault(key, (value, exists))
                if existing_exists and (value, exists) != (existing_value, existing_exists):
                    logger.debug(
                        f"removing repeated app_global_get_ex for key: {key}",
                        location=op.source_location,
                    )
                    op.source = models.ValueTuple(
                        values=(existing_value, existing_exists), source_location=None
                    )
                    modified = True
            case models.Assignment(
                targets=[value], source=models.Intrinsic(op=AVMOp.app_global_get, args=[key])
            ):
                last_write = None  # doing a read resets
                existing_read = read_results.setdefault(key, (value, None))
                if value != existing_read[0]:
                    logger.debug(
                        f"removing repeated app_global_get for key: {key}",
                        location=op.source_location,
                    )
                    op.source = existing_read[0]
                    modified = True
            case models.Intrinsic(op=AVMOp.app_global_put, args=[key, value]) as write:
                # update cache with new value.
                # this is conservative to naively avoid the problem when multiple
                # values point to the same slot
                read_results = {
                    key: (
                        value,
                        models.UInt64Constant(
                            value=1, ir_type=PrimitiveIRType.bool, source_location=None
                        ),
                    )
                }
                # remove last_write if it is overwritten with another write, and there
                # are no intervening reads
                if last_write and (key == last_write.args[0]):
                    logger.debug(
                        f"removing repeated app_global_put for key: {key}",
                        location=op.source_location,
                    )
                    block.ops.remove(last_write)
                    modified = True
                last_write = write
            # be conservative and treat any subroutine call or modifications as a barrier
            case (
                models.InvokeSubroutine()
                | models.Assignment(source=models.InvokeSubroutine())
                | models.Intrinsic(op=AVMOp.app_global_del)
            ):
                last_write = None
                read_results = {}
    return modified


def _optimise_local_read_write(block: models.BasicBlock) -> bool:
    modified = False
    read_results = dict[
        tuple[models.Value, models.Value], tuple[models.Value, models.Value | None]
    ]()
    last_write: models.Intrinsic | None = None
    for op in block.ops:
        match op:
            case models.Assignment(
                targets=[value, exists],
                source=models.Intrinsic(
                    op=AVMOp.app_local_get_ex, args=[account, models.UInt64Constant(value=0), key]
                ),
            ):
                last_write = None  # doing a read resets
                existing_value, existing_exists = read_results.setdefault(
                    (account, key), (value, exists)
                )
                if existing_exists and (value, exists) != (existing_value, existing_exists):
                    logger.debug(
                        f"removing repeated app_local_get_ex for key: {key}",
                        location=op.source_location,
                    )
                    op.source = models.ValueTuple(
                        values=(existing_value, existing_exists), source_location=None
                    )
                    modified = True
            case models.Assignment(
                targets=[value],
                source=models.Intrinsic(op=AVMOp.app_local_get, args=[account, key]),
            ):
                last_write = None  # doing a read resets
                existing_read = read_results.setdefault((account, key), (value, None))
                if value != existing_read[0]:
                    logger.debug(
                        f"removing repeated app_local_get for: {account=}, {key=}",
                        location=op.source_location,
                    )
                    op.source = existing_read[0]
                    modified = True
            case models.Intrinsic(op=AVMOp.app_local_put, args=[account, key, value]) as write:
                # update cache with new value.
                # this is conservative to naively avoid the problem when multiple
                # values point to the same slot
                read_results = {
                    (account, key): (
                        value,
                        models.UInt64Constant(
                            value=1, ir_type=PrimitiveIRType.bool, source_location=None
                        ),
                    )
                }
                # remove last_write if it is overwritten with another write, and there
                # are no intervening reads (last_write is None if there are reads)
                if last_write and ((account, key) == tuple(last_write.args[:2])):
                    logger.debug(
                        f"removing repeated app_local_put for: {account=}, {key=}",
                        location=op.source_location,
                    )
                    block.ops.remove(last_write)
                    modified = True
                last_write = write
            # be conservative and treat any subroutine call or modification as a barrier
            case (
                models.InvokeSubroutine()
                | models.Assignment(source=models.InvokeSubroutine())
                | models.Intrinsic(op=AVMOp.app_local_del)
            ):
                last_write = None
                read_results = {}
    return modified


def _optimise_box_read_write(block: models.BasicBlock) -> bool:
    modified = False
    # map of box_get key -> box_get result
    read_results = dict[models.Value, tuple[models.Value, models.Value]]()
    last_write: models.Intrinsic | None = None
    for op in block.ops:
        match op:
            case models.Assignment(
                source=models.Intrinsic(op=AVMOp.box_extract | AVMOp.box_len),
            ):
                # these count as reads
                # TODO: optimize repeats
                last_write = None
            case models.Assignment(
                targets=[value, exists],
                source=models.Intrinsic(op=AVMOp.box_get, args=[key]),
            ):
                last_write = None  # doing a read resets
                existing_value, existing_exists = read_results.setdefault(key, (value, exists))
                if existing_exists and (value, exists) != (existing_value, existing_exists):
                    logger.debug(
                        f"removing repeated box_get for key: {key}",
                        location=op.source_location,
                    )
                    op.source = models.ValueTuple(
                        values=(existing_value, existing_exists), source_location=None
                    )
                    modified = True
            case models.Intrinsic(op=AVMOp.box_put, args=[key, value]) as write:
                # update cache with new value.
                # this is conservative to naively avoid the problem when multiple
                # values point to the same slot
                read_results = {
                    key: (
                        value,
                        models.UInt64Constant(
                            value=1, ir_type=PrimitiveIRType.bool, source_location=None
                        ),
                    )
                }
                # remove last_write if it is overwritten with another write, and there
                # are no intervening reads
                if last_write and (key == last_write.args[0]):
                    logger.debug(
                        f"removing repeated box_put for key: {key}",
                        location=op.source_location,
                    )
                    block.ops.remove(last_write)
                    modified = True
                last_write = write
            # be conservative and treat any subroutine call or box modification as a barrier
            case (
                models.InvokeSubroutine()
                | models.Assignment(source=models.InvokeSubroutine())
                | models.Intrinsic(
                    op=AVMOp.box_del
                    | AVMOp.box_splice
                    | AVMOp.box_resize
                    | AVMOp.box_replace
                    | AVMOp.box_create
                )
            ):
                last_write = None
                read_results = {}
    return modified


def _optimise_slot_read_write(block: models.BasicBlock) -> bool:
    modified = False
    slot_read_results = dict[models.Value, models.Value]()
    last_write: models.WriteSlot | None = None
    for op in block.ops:
        match op:
            case models.Assignment(targets=[target], source=models.ReadSlot(slot=slot)):
                last_write = None  # doing a read resets
                existing_read = slot_read_results.setdefault(slot, target)
                if target != existing_read:
                    op.source = existing_read
                    modified = True
            case models.WriteSlot(slot=slot, value=value) as write:
                # update cache with new value.
                # this is conservative to naively avoid the problem when multiple
                # values point to the same slot
                slot_read_results = {slot: value}
                # remove last_write if it is overwritten with another write, and there
                # are no intervening reads
                if last_write and (slot == last_write.slot):
                    block.ops.remove(last_write)
                    modified = True
                last_write = write
            # be conservative and treat any subroutine call as a barrier
            case models.InvokeSubroutine() | models.Assignment(source=models.InvokeSubroutine()):
                last_write = None
                slot_read_results = {}
    return modified
