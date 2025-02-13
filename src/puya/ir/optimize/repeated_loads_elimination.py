from puya import log
from puya.context import CompileContext
from puya.ir import models

logger = log.get_logger(__name__)


def redundant_slot_op_elimination(_: CompileContext, subroutine: models.Subroutine) -> bool:
    any_modified = False
    # TODO: consider dominator blocks
    for block in subroutine.body:
        while _optimise_block(block):
            any_modified = True
    return any_modified


def _optimise_block(block: models.BasicBlock) -> bool:
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
            # be conservative and treat any subroutine call as a barrier to this
            # particular optimisation
            case models.InvokeSubroutine() | models.Assignment(source=models.InvokeSubroutine()):
                slot_read_results = {}
    return modified
