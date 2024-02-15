import functools
import operator
import typing

import attrs
import structlog

from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize.assignments import copy_propagation
from puya.ir.optimize.collapse_blocks import BlockReferenceReplacer
from puya.ir.optimize.dead_code_elimination import PURE_AVM_OPS
from puya.ir.visitor import NoOpIRVisitor
from puya.utils import StableSet, unique

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
    dom = {k: v - StableSet(k) for k, v in dom.items()}
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
                modified = modified or bool(op.accept(visitor))
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
                    modified = modified or bool(op.accept(visitor))
        if modified:
            any_modified = True
            copy_propagation(context, subroutine)
    return any_modified


def compute_dominators(
    subroutine: models.Subroutine,
) -> dict[models.BasicBlock, StableSet[models.BasicBlock]]:
    all_blocks = StableSet(*subroutine.body)
    dom = {b: all_blocks if b.predecessors else StableSet(b) for b in subroutine.body}
    changes = True
    while changes:
        changes = False
        for block in reversed(subroutine.body):
            if block.predecessors:
                new = functools.reduce(
                    StableSet.intersection, (dom[p] for p in block.predecessors)
                ) | StableSet(block)
                old = dom[block]
                dom[block] = new
                if old != new:
                    changes = True
    return dom


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


def block_deduplication(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    modified = False
    seen = dict[tuple[object, ...], models.BasicBlock]()
    for block in subroutine.body.copy():
        all_ops = tuple(op.freeze() for op in block.all_ops)
        if existing := seen.get(all_ops):
            logger.debug(
                f"Removing duplicated block {block} and updating references to {existing}"
            )
            modified = True
            BlockReferenceReplacer.apply(find=block, replacement=existing, blocks=subroutine.body)
            subroutine.body.remove(block)
            existing.predecessors = unique([*existing.predecessors, *block.predecessors])
        else:
            seen[all_ops] = block
    return modified
