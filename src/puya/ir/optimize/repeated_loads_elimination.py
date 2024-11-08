from puya import log
from puya.context import CompileContext
from puya.ir import models

logger = log.get_logger(__name__)


def repeated_loads_elimination(_: CompileContext, subroutine: models.Subroutine) -> bool:
    any_modified = False
    modified = True
    while modified:
        modified = False
        # TODO: consider dominator blocks
        for block in subroutine.body:
            slot_to_value = dict[models.Value, models.Value]()
            last_write: models.WriteSlot | None = None
            for op in block.ops:
                if isinstance(op, models.Assignment) and isinstance(op.source, models.ReadSlot):
                    last_write = None
                    (target,) = op.targets
                    try:
                        existing = slot_to_value[op.source.slot]
                    except KeyError:
                        slot_to_value[op.source.slot] = target
                    else:
                        op.source = existing
                        modified = True
                # TODO: this is conservative to avoid the problem when multiple values point to
                #       the same slot
                # update cache with new value
                elif isinstance(op, models.WriteSlot):
                    if not slot_to_value or op.slot in slot_to_value and len(slot_to_value) == 1:
                        slot_to_value[op.slot] = op.value
                    else:
                        slot_to_value = {}
                    if last_write and last_write.slot in slot_to_value:
                        block.ops.remove(last_write)
                    last_write = op
                # reset cache if there is a subroutine call, as this could invalidate anything
                # TODO: examine call graph to see if any WriteSlot's are present? if not the
                #       sub call wouldn't be a problem
                elif (
                    isinstance(op, models.Assignment)
                    and isinstance(op.source, models.InvokeSubroutine)
                    or isinstance(op, models.InvokeSubroutine)
                ):
                    # TODO: this is conservative, but things get tricky
                    #  as multiple values could point ot the same slot
                    slot_to_value = {}
        if modified:
            any_modified = True
    return any_modified
