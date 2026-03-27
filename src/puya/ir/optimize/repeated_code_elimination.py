import typing
from collections.abc import Mapping, Sequence, Set

import attrs

from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.optimize._utils import compute_dominator_tree
from puya.ir.visitor import NoOpIRVisitor

logger = log.get_logger(__name__)


def repeated_expression_elimination(
    _context: CompileContext, subroutine: models.Subroutine
) -> bool:
    # TODO: consider merging this pass with GVN so we only compute this tree once
    start, dom_tree = compute_dominator_tree(subroutine)
    modified = _remove_repeated_assertions(dom_tree, start, asserted=set())
    return modified


def _remove_repeated_assertions(
    dom_tree: Mapping[models.BasicBlock, Sequence[models.BasicBlock]],
    block: models.BasicBlock,
    *,
    asserted: Set[models.Value],
) -> bool:
    visitor = RepeatedAssertVisitor(block=block, asserted=set(asserted))
    for op in block.ops.copy():
        op.accept(visitor)
    modified = visitor.modified
    for child in dom_tree.get(block, []):
        modified |= _remove_repeated_assertions(dom_tree, child, asserted=visitor.asserted)
    return modified


@attrs.define(kw_only=True)
class RepeatedAssertVisitor(NoOpIRVisitor[None]):
    block: models.BasicBlock
    asserted: set[models.Value]
    modified: bool = False

    @typing.override
    def visit_assert(self, assert_: models.Assert) -> None:
        assert_arg = assert_.condition
        if assert_arg in self.asserted:
            logger.debug(f"Removing redundant assert of {assert_arg}")
            self.modified = True
            self.block.ops.remove(assert_)
        else:
            self.asserted.add(assert_arg)
