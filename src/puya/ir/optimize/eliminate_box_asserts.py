from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.utils import set_add

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
    box_exists = set[models.Value]()
    box_exists_regs = dict[models.Value, models.Value]()
    for op in block.ops.copy():
        if isinstance(op, models.Assignment):
            targets = op.targets
            source = op.source
        elif isinstance(op, models.ValueProvider):
            targets = None
            source = op
        else:
            targets = None
            source = None

        if isinstance(source, models.InvokeSubroutine):
            if not source.target.pure:
                box_exists.clear()
        elif isinstance(source, models.Intrinsic):
            match source.op:
                case (
                    AVMOp.box_create
                    | AVMOp.box_extract
                    | AVMOp.box_put
                    | AVMOp.box_replace
                    | AVMOp.box_resize
                    | AVMOp.box_splice
                ):
                    box_key = source.args[0]
                    box_exists.add(box_key)
                case AVMOp.box_del:
                    # conservative assume could be deleting any box
                    box_exists.clear()
                case AVMOp.box_get | AVMOp.box_len:
                    if targets is not None:
                        (box_key,) = source.args
                        _, exists_reg = targets
                        box_exists_regs[exists_reg] = box_key
                case AVMOp.assert_:
                    (condition,) = source.args
                    maybe_box_key = box_exists_regs.get(condition)
                    if maybe_box_key and not set_add(box_exists, maybe_box_key):
                        logger.debug(
                            f"box_key {maybe_box_key} is known to exist, removing assert",
                            location=op.source_location,
                        )
                        # box exists, so can remove assert
                        block.ops.remove(op)
                        modified = True
    return modified
