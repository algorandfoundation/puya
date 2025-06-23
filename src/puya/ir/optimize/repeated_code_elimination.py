import functools
import operator
from collections.abc import Sequence

import attrs

from puya import log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.optimize.assignments import copy_propagation
from puya.ir.optimize.dead_code_elimination import PURE_AVM_OPS
from puya.ir.visitor import NoOpIRVisitor
from puya.utils import not_none

logger = log.get_logger(__name__)


def repeated_expression_elimination(
    context: CompileContext, subroutine: models.Subroutine
) -> bool:
    any_modified = False
    dom = compute_dominators(subroutine)
    modified = True
    while modified:
        modified = False
        block_asserted = dict[models.BasicBlock, set[models.Value]]()
        block_const_intrinsics = dict[models.BasicBlock, dict[object, Sequence[models.Register]]]()
        for block in subroutine.body:
            visitor = RCEVisitor(block)
            for op in block.ops.copy():
                modified = bool(op.accept(visitor)) or modified
            block_asserted[block] = visitor.asserted
            block_const_intrinsics[block] = visitor.const_intrinsics

        for block in subroutine.body:
            dominators = dom[block]
            if dominators:
                visitor = RCEVisitor(
                    block,
                    # if there is a single dominator then reduce will return the original
                    # collection of that dominator, so copy to ensure original collections are
                    # not modified
                    const_intrinsics=functools.reduce(
                        operator.or_, (block_const_intrinsics[b] for b in dominators)
                    ).copy(),
                    asserted=functools.reduce(
                        operator.or_, (block_asserted[b] for b in dominators)
                    ).copy(),
                )
                for op in block.ops.copy():
                    modified = bool(op.accept(visitor)) or modified
        if modified:
            any_modified = True
            copy_propagation(context, subroutine)
    return any_modified


def compute_dominators(
    subroutine: models.Subroutine,
) -> dict[models.BasicBlock, list[models.BasicBlock]]:
    """
    For each block in the subroutine, compute its dominators (other than itself).

    A block X dominates another block Y if all possible control flow paths to Y must
    pass through X at least once.
    """
    # This is the simple iterative data-flow approach, described as such in the introduction of:
    # https://www.clear.rice.edu/comp512/Lectures/Papers/TR06-33870-Dom.pdf
    # Note that the pseudocode in Figure 1 is somewhat misleading, it omits the important detail
    # that the start node *must* remain as having no dominators other than itself, even if it
    # forms part of a loop (ie has predecessors).
    all_blocks = set(subroutine.body)
    non_root_blocks = list[models.BasicBlock]()
    dom = {subroutine.entry: {subroutine.entry}}
    # Reversed here is not critical but should reduce iterations.
    # Paper calls for reverse post-order traversal, but this is simpler and good enough.
    for b in reversed(subroutine.body[1:]):
        if b.predecessors:
            dom[b] = all_blocks
            non_root_blocks.append(b)
        else:
            # For non-entry blocks with no predecessors (ie unreachable blocks),
            # we can similarly pre-compute the end result.
            # This isn't critical, but without this here we'd need to handle this inside
            # the loop as the reduce result will be undefined, but should be empty.
            dom[b] = {b}
    changes = True
    while changes:
        changes = False
        for block in non_root_blocks:
            pred_dom = functools.reduce(set.intersection, (dom[p] for p in block.predecessors))
            new = pred_dom | {block}
            if new != dom[block]:
                dom[block] = new
                changes = True
    # Dominator sets are defined as including the node itself, but that's not useful to us,
    # so remove it here and also sort the list by block ID.
    return {b: sorted(dom_set - {b}, key=lambda a: not_none(a.id)) for b, dom_set in dom.items()}


@attrs.define
class RCEVisitor(NoOpIRVisitor[bool]):
    block: models.BasicBlock
    const_intrinsics: dict[object, Sequence[models.Register]] = attrs.field(factory=dict)
    asserted: set[models.Value] = attrs.field(factory=set)

    _assignment: models.Assignment | None = None

    def visit_assignment(self, ass: models.Assignment) -> bool | None:
        self._assignment = ass
        remove = ass.source.accept(self)
        self._assignment = None
        return remove

    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> bool:
        modified = False
        if self._assignment is not None:
            # only consider ops with stack args because they're much more likely to
            # produce extra stack manipulations
            if intrinsic.args and intrinsic.op.code in PURE_AVM_OPS:
                key = attrs.evolve(intrinsic, error_message=None).freeze()
                modified = self._cache_or_replace(self._assignment, key)
        elif intrinsic.op.code == "assert":
            (assert_arg,) = intrinsic.args
            if assert_arg in self.asserted:
                logger.debug(f"Removing redundant assert of {assert_arg}")
                modified = True
                self.block.ops.remove(intrinsic)
            else:
                self.asserted.add(assert_arg)
        return modified

    def visit_extract_value(self, read: models.ExtractValue) -> bool:
        modified = False
        if self._assignment is not None:
            key = read.freeze()
            modified = self._cache_or_replace(self._assignment, key)
        return modified

    def visit_bytes_encode(self, encode: models.BytesEncode) -> bool:
        modified = False
        if self._assignment is not None:
            key = encode.freeze()
            modified = self._cache_or_replace(self._assignment, key)
        return modified

    def visit_decode_bytes(self, decode: models.DecodeBytes) -> bool:
        modified = False
        if self._assignment is not None:
            key = decode.freeze()
            modified = self._cache_or_replace(self._assignment, key)
        return modified

    def _cache_or_replace(self, ass: models.Assignment, key: object) -> bool:
        try:
            existing = self.const_intrinsics[key]
        except KeyError:
            self.const_intrinsics[key] = ass.targets
            return False
        logger.debug(
            f"Replacing redundant declaration {ass}" f" with copy of existing registers {existing}"
        )
        if len(existing) == 1:
            ass.source = existing[0]
        else:
            current_idx = self.block.ops.index(ass)
            self.block.ops[current_idx : current_idx + 1] = [
                models.Assignment(targets=[dst], source=src, source_location=ass.source_location)
                for dst, src in zip(ass.targets, existing, strict=True)
            ]
        return True
