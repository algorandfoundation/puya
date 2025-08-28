from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.utils import not_none

logger = log.get_logger(__name__)


def _replace_single_target_with_goto(terminator: models.ControlOp) -> models.ControlOp:
    """
    If a ControlOp has a single target, replace it with a Goto, otherwise return the original op.
    """
    if type(terminator) is models.Goto:
        return terminator
    match terminator:
        case models.ControlOp(unique_targets=[single_target]):
            replacement = models.Goto(
                source_location=terminator.source_location,
                target=single_target,
            )
            logger.debug(f"replaced {terminator} with {replacement}")
            return replacement
        case _:
            return terminator


def merge_blocks(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    modified = False
    blocks = [subroutine.body[0]]
    for block in subroutine.body[1:]:
        blocks.append(block)
        if len(block.predecessors) == 1:
            (predecessor,) = block.predecessors
            if type(predecessor.terminator) is models.Goto:
                assert predecessor.terminator.target is block
                # can merge blocks when there is an unconditional jump between them
                predecessor.phis.extend(block.phis)
                predecessor.ops.extend(block.ops)
                predecessor.terminator = block.terminator

                # this will update the predecessor lists of all block.successors to
                # now point back to predecessor e.g.
                # predecessor <-> block <-> [ss1, ...]
                # predecessor <-> [ss1, ...]
                for succ in block.successors:
                    succ.replace_predecessor(old=block, new=predecessor)

                blocks.pop()
                modified = True
                logger.debug(f"Merged linear {block} into {predecessor}")
    if modified:
        subroutine.body[:] = blocks
    return modified


def remove_linear_jumps(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    #  P = {p0, p1, ..., pn} -> {j} -> {t}
    # remove {j} from subroutine
    # point P at t:
    #  update references within P from j to t
    #  ensure P are all in predecessors of t
    jumps = dict[models.BasicBlock, models.BasicBlock]()
    blocks = []
    for block in subroutine.body:
        blocks.append(block)
        match block:
            case models.BasicBlock(phis=[], ops=[], terminator=models.Goto(target=target)):
                if target is block:
                    logger.debug(f"Unconditional infinite loop detected in {block}")
                    continue
                if target.phis:
                    logger.debug(
                        f"Not removing empty block {block} because it's used by phi nodes"
                    )
                    continue
                jumps[block] = target
                logger.debug(f"Removing jump block {block}")
                blocks.pop()

    if not jumps:
        return False

    # now back-propagate any chains
    for src, target in jumps.items():
        while True:
            target.discard_predecessor(src)
            try:
                target = jumps[target]
            except KeyError:
                break
        retarget_and_simplify(old=src, new=target)
    subroutine.body[:] = blocks
    return True


def retarget_and_simplify(*, old: models.BasicBlock, new: models.BasicBlock) -> None:
    logger.debug(f"branching to {old} will be replaced with {new}")
    for pred in old.predecessors:
        terminator = not_none(pred.terminator)
        terminator.replace_target(find=old, replace=new)
        maybe_simplified = _replace_single_target_with_goto(terminator)
        pred.terminator = maybe_simplified
        new.add_predecessor(pred)
