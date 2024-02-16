import functools
import operator
import typing

import attrs
import structlog

from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize.assignments import copy_propagation
from puya.ir.optimize.dead_code_elimination import PURE_AVM_OPS
from puya.ir.visitor import NoOpIRVisitor

logger = structlog.get_logger(__name__)


@attrs.frozen
class IntrinsicData:
    op: AVMOp
    immediates: tuple[str | int, ...]
    args: tuple[models.Value, ...]

    @classmethod
    def from_op(cls, op: models.Intrinsic) -> typing.Self:
        return cls(
            op=op.op,
            immediates=tuple(op.immediates),
            args=tuple(op.args),
        )


def repeated_expression_elimination(
    context: CompileContext, subroutine: models.Subroutine
) -> bool:
    any_modified = False
    dom = compute_dominators(subroutine)
    modified = True
    while modified:
        modified = False
        block_asserted = dict[models.BasicBlock, set[models.Value]]()
        block_const_intrinsics = dict[
            models.BasicBlock, dict[IntrinsicData, list[models.Register]]
        ]()
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
                    const_intrinsics=functools.reduce(
                        operator.or_, (block_const_intrinsics[b] for b in dominators)
                    ),
                    asserted=functools.reduce(
                        operator.or_, (block_asserted[b] for b in dominators)
                    ),
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
    all_blocks = set(subroutine.body)
    dom = {b: all_blocks if b.predecessors else {b} for b in subroutine.body}
    changes = True
    while changes:
        changes = False
        for block in reversed(subroutine.body):
            if block.predecessors:
                pred_dom = functools.reduce(set.intersection, (dom[p] for p in block.predecessors))
                new = pred_dom | {block}
                if new != dom[block]:
                    dom[block] = new
                    changes = True
    return {
        b: sorted(dom_set - {b}, key=lambda a: typing.cast(int, a.id))
        for b, dom_set in dom.items()
    }


@attrs.define
class RCEVisitor(NoOpIRVisitor[bool]):
    block: models.BasicBlock
    const_intrinsics: dict[IntrinsicData, list[models.Register]] = attrs.field(factory=dict)
    asserted: set[models.Value] = attrs.field(factory=set)

    _assignment: models.Assignment | None = None

    def visit_assignment(self, ass: models.Assignment) -> bool | None:
        self._assignment = ass
        remove = ass.source.accept(self)
        self._assignment = None
        return remove

    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> bool:
        modified = False
        if (ass := self._assignment) is not None:
            # only consider ops with stack args because they're much more likely to
            # produce extra stack manipulations
            if intrinsic.args and intrinsic.op.code in PURE_AVM_OPS:
                key = IntrinsicData.from_op(intrinsic)
                try:
                    existing = self.const_intrinsics[key]
                except KeyError:
                    self.const_intrinsics[key] = ass.targets
                else:
                    logger.debug(
                        f"Replacing redundant declaration {ass}"
                        f" with copy of existing registers {existing}"
                    )
                    modified = True
                    if len(existing) == 1:
                        ass.source = existing[0]
                    else:
                        current_idx = self.block.ops.index(ass)
                        self.block.ops[current_idx : current_idx + 1] = [
                            models.Assignment(
                                targets=[dst], source=src, source_location=ass.source_location
                            )
                            for dst, src in zip(ass.targets, existing, strict=True)
                        ]
        elif intrinsic.op.code == "assert":
            (assert_arg,) = intrinsic.args
            if assert_arg in self.asserted:
                logger.debug(f"Removing redundant assert of {assert_arg}")
                modified = True
                self.block.ops.remove(intrinsic)
            else:
                self.asserted.add(assert_arg)
        return modified
