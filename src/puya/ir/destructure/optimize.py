import contextlib
import itertools
from copy import deepcopy

import attrs

from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.optimize.collapse_blocks import BlockReferenceReplacer
from puya.utils import unique

logger = log.get_logger(__name__)


def post_ssa_optimizer(
    context: CompileContext, artifact: models.ModuleArtifact
) -> models.ModuleArtifact:
    logger.debug("Performing post-SSA optimizations")
    cloned = deepcopy(artifact)
    for sub in cloned.all_subroutines():
        remove_linear_jumps(sub)
        if context.options.optimization_level >= 2:
            block_deduplication(sub)
        attrs.validate(sub)
    return cloned


def remove_linear_jumps(subroutine: models.Subroutine) -> None:
    #  P = {p0, p1, ..., pn} -> {j} -> {t}
    # remove {j} from subroutine
    # point P at t:
    #  update references within P from j to t
    #  ensure P are all in predecessors of t
    # This exists here and not in main IR optimization loop because we only want to do it for
    # blocks that are _truly_ empty, not ones that contain phi-node magic that results in copies
    for block in subroutine.body:
        match block:
            case models.BasicBlock(
                ops=[], terminator=models.Goto(target=target)
            ) if target is not block:
                logger.debug(f"Removing jump block {block} and replacing references with {target}")
                BlockReferenceReplacer.apply(
                    find=block, replacement=target, blocks=block.predecessors
                )
                with contextlib.suppress(ValueError):
                    target.predecessors.remove(block)
                for pred in block.predecessors:
                    if pred not in target.predecessors:
                        target.predecessors.append(pred)
                subroutine.body.remove(block)


def block_deduplication(subroutine: models.Subroutine) -> None:
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
