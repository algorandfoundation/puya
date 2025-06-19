from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp

logger = log.get_logger(__name__)


def minimize_box_exist_asserts(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    modified = False
    for block in subroutine.body:
        if _remove_box_exists_asserts(block):
            modified = True
    return modified


def _remove_box_exists_asserts(block: models.BasicBlock) -> bool:
    #   for any box op that returns an exist flag that is asserted
    #   can remove any asserts after the first one as long as the box register is the same
    #   and no box_del op is called
    #   begin block | subroutine call
    #       exist state of all box keys are unknown
    #   box_create | box_extract | box_put | box_replace | box_resize | box_splice key
    #       set box key as known to exist
    #   box_del key
    #       sett box key as known to not exist
    #   box_get | box_len
    #       if unknown if box exists then keep the assert, assume box exists after assert
    #       if known that box exists then remove any asserts
    #       if known that box does not exist then replace asserts with err

    modified = False
    box_exists = dict[models.Value, bool]()

    box_exists_regs = dict[models.Value, models.Value]()
    for op in block.ops.copy():
        maybe_ass = None
        if isinstance(op, models.Assignment):
            maybe_ass = op
            maybe_intrinsic: models.IRVisitable = op.source
        else:
            maybe_intrinsic = op
        if isinstance(maybe_intrinsic, models.Intrinsic):
            if maybe_intrinsic.op in (
                AVMOp.box_create,
                AVMOp.box_extract,
                AVMOp.box_put,
                AVMOp.box_replace,
                AVMOp.box_resize,
                AVMOp.box_splice,
            ):
                box_key = maybe_intrinsic.args[0]
                box_exists[box_key] = True
            elif maybe_intrinsic.op == AVMOp.box_del:
                # conservative assume could be deleting any box
                box_exists.clear()
            elif maybe_ass and maybe_intrinsic.op in (AVMOp.box_get, AVMOp.box_len):
                box_key = maybe_intrinsic.args[0]
                _, exists_reg = maybe_ass.targets
                box_exists_regs[exists_reg] = box_key
            elif (
                maybe_intrinsic.op == AVMOp.assert_
                and (box_exists_reg := maybe_intrinsic.args[0]) in box_exists_regs
            ):
                box_key = box_exists_regs[box_exists_reg]
                try:
                    box_does_exist = box_exists[box_key]
                except KeyError:
                    # current state of box is unknown, but can assume it exists after this op
                    box_exists[box_key] = True
                    continue
                if box_does_exist:
                    logger.debug(
                        f"box_key {box_key} is known to exist, removing assert",
                        location=op.source_location,
                    )
                    # box exists, so can remove assert
                    block.ops.remove(op)
                    modified = True
        elif isinstance(maybe_intrinsic, models.InvokeSubroutine):
            box_exists.clear()
    return modified
