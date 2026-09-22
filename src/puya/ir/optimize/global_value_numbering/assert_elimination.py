from collections.abc import Set

import attrs

from puya import log
from puya.ir import models
from puya.ir.optimize._utils import DomTree, SSAReadTracker
from puya.ir.optimize.global_value_numbering.tables import VN, GVNTables, UInt64ConstKey
from puya.utils import set_add

__all__ = [
    "eliminate_redundant_asserts",
]

logger = log.get_logger(__name__)


def eliminate_redundant_asserts(
    tables: GVNTables,
    dom_tree: DomTree,
    ssa_reads: SSAReadTracker,
) -> bool:
    """Drop asserts whose condition is constant-true, or whose VN was already asserted
    on this dominator path."""
    eliminator = AssertEliminator(tables, dom_tree, ssa_reads)
    modified = eliminator.run()
    return modified


@attrs.frozen
class AssertEliminator:
    tables: GVNTables
    dom_tree: DomTree
    ssa_reads: SSAReadTracker

    def run(self) -> bool:
        return self._walk(block=self.dom_tree.root, asserted_=set())

    def _walk(self, block: models.BasicBlock, asserted_: Set[VN | models.Value]) -> bool:
        modified = False
        asserted = set(asserted_)
        ops = []
        for op in block.ops:
            ops.append(op)
            if isinstance(op, models.Assert):
                condition = op.condition
                redundant = False
                if isinstance(condition, models.UInt64Constant):
                    redundant = bool(condition.value)
                elif isinstance(condition, models.Register):
                    condition_vn = self.tables.register_vn[condition]
                    maybe_const_defn = self.tables.vn_definition.get(condition_vn)
                    if isinstance(maybe_const_defn, UInt64ConstKey):
                        redundant = bool(maybe_const_defn.value)
                    elif not set_add(asserted, condition_vn):
                        redundant = True
                if redundant:
                    modified = True
                    logger.debug(f"removing redundant assert of {condition}")
                    ops.pop()
                    self.ssa_reads.remove(op)
        block.ops[:] = ops
        for child in self.dom_tree.children(block):
            modified |= self._walk(child, asserted)
        return modified
