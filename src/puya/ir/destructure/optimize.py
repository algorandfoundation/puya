import contextlib
import itertools

from puya import log
from puya.ir import models
from puya.ir.optimize.collapse_blocks import BlockReferenceReplacer
from puya.utils import unique

logger = log.get_logger(__name__)


def post_ssa_optimizer(sub: models.Subroutine, optimization_level: int) -> None:
    logger.debug(f"Performing post-SSA optimizations at level {optimization_level}")
    if optimization_level >= 1:
        _remove_linear_jumps(sub)
    if optimization_level >= 2:
        _block_deduplication(sub)


def _remove_linear_jumps(subroutine: models.Subroutine) -> None:
    #  P = {p0, p1, ..., pn} -> {j} -> {t}
    # remove {j} from subroutine
    # point P at t:
    #  update references within P from j to t
    #  ensure P are all in predecessors of t
    # This exists here and not in main IR optimization loop because we only want to do it for
    # blocks that are _truly_ empty, not ones that contain phi-node magic that results in copies
    # build a map of any blocks that are just an unconditional branch to their targets
    jumps = dict[models.BasicBlock, models.BasicBlock]()
    for block in subroutine.body.copy():
        match block:
            case models.BasicBlock(
                ops=[], terminator=models.Goto(target=target)
            ) if target is not block:
                jumps[block] = target
                logger.debug(f"Removing jump block {block}")
                with contextlib.suppress(ValueError):
                    target.predecessors.remove(block)
                subroutine.body.remove(block)

    # now back-propagate any chains
    replacements = dict[models.BasicBlock, models.BasicBlock]()
    for src, target in jumps.items():
        while True:
            try:
                target = jumps[target]
            except KeyError:
                break
        logger.debug(f"branching to {src} will be replaced with {target}")
        replacements[src] = target
        BlockReferenceReplacer.apply(find=src, replacement=target, blocks=subroutine.body)
        for pred in src.predecessors:
            if pred not in target.predecessors:
                target.predecessors.append(pred)


def _block_deduplication(subroutine: models.Subroutine) -> None:
    seen = dict[tuple[object, ...], models.BasicBlock]()
    for block in subroutine.body.copy():
        all_ops = tuple(op.freeze() for op in block.all_ops)
        if existing := seen.get(all_ops):
            logger.debug(
                f"Removing duplicated block {block} and updating references to {existing}"
            )
            BlockReferenceReplacer.apply(find=block, replacement=existing, blocks=subroutine.body)
            subroutine.body.remove(block)
            existing.predecessors = unique(
                itertools.chain(existing.predecessors, block.predecessors)
            )
        else:
            seen[all_ops] = block
