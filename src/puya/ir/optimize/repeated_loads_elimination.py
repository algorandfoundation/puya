from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.types_ import SlotType

logger = log.get_logger(__name__)


def redundant_slot_op_elimination(_: CompileContext, subroutine: models.Subroutine) -> bool:
    any_modified = False
    modified = True
    while modified:
        modified = False
        # TODO: consider dominator blocks
        for block in subroutine.body:
            slot_to_value = dict[models.Value, models.Value]()
            last_write: models.WriteSlot | None = None
            for op in block.ops:
                match op:
                    case models.Assignment(targets=[target], source=models.ReadSlot(slot=slot)):
                        last_write = None
                        try:
                            existing = slot_to_value[slot]
                        except KeyError:
                            slot_to_value[slot] = target
                        else:
                            op.source = existing
                            modified = True
                    case models.WriteSlot(slot=slot, value=value) as write:
                        # update cache with new value

                        # TODO: this is conservative to naively avoid the problem when multiple
                        #       values point to the same slot
                        if not slot_to_value or slot in slot_to_value and len(slot_to_value) == 1:
                            slot_to_value[slot] = value
                        else:
                            slot_to_value = {slot: value}
                        # remove last_write if it is overwritten with another write
                        if last_write and last_write.slot in slot_to_value:
                            block.ops.remove(last_write)
                        last_write = write
                    case (
                        models.Assignment(source=models.InvokeSubroutine() as invoke)
                        | (models.InvokeSubroutine() as invoke)
                        # TODO: this condition only works if there are no other ways of
                        #       passing slots around a program
                    ) if any(isinstance(a.ir_type, SlotType) for a in invoke.args):
                        # TODO: examine call graph to see if any WriteSlot's are present?
                        #       if there are no writes then sub call wouldn't be a problem

                        # TODO: this is conservative, but things get tricky
                        #       as multiple values could point ot the same slot
                        slot_to_value = {}
        if modified:
            any_modified = True
    return any_modified
