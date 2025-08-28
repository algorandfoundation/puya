import attrs

from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.optimize.collapse_blocks import remove_linear_jumps, retarget_and_simplify

logger = log.get_logger(__name__)


def post_ssa_optimizer(context: CompileContext, sub: models.Subroutine) -> None:
    optimization_level = context.options.optimization_level
    logger.debug(f"Performing post-SSA optimizations at level {optimization_level}")
    modified = False
    if optimization_level >= 1:  # noqa: SIM102
        # re-run jump-block removal now that phis have been removed
        if remove_linear_jumps(context, sub):
            modified = True
    if optimization_level >= 2:  # noqa: SIM102
        # block deduplication is only done at level 2 or above,
        # as it could potentially produce less debuggable code
        if _block_deduplication(context, sub):
            modified = True
    if modified:
        attrs.validate(sub)


def _block_deduplication(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    seen = dict[tuple[object, ...], models.BasicBlock]()
    modified = False
    blocks = []
    for block in subroutine.body:
        blocks.append(block)
        all_ops = tuple(op.freeze() for op in block.all_ops)
        first = seen.setdefault(all_ops, block)
        if first is not block:
            duplicate = block
            modified = True
            blocks.pop()
            logger.debug(
                f"Removing duplicated block {duplicate} and updating references to {first}"
            )
            for succ in duplicate.successors:
                succ.replace_predecessor(old=duplicate, new=first)
            retarget_and_simplify(old=duplicate, new=first)
    if modified:
        subroutine.body[:] = blocks
    return modified
