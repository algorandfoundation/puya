import contextlib
import typing
from collections.abc import Iterator, Sequence

import attrs

from puya import log
from puya.awst import nodes as awst_nodes
from puya.errors import InternalError
from puya.ir.models import (
    Assignment,
    BasicBlock,
    ControlOp,
    Goto,
    Op,
    Register,
)
from puya.ir.ssa import BraunSSA
from puya.parse import SourceLocation
from puya.utils import lazy_setdefault

logger = log.get_logger(__name__)


@attrs.frozen(kw_only=True)
class _LoopTargets:
    on_break: BasicBlock
    on_continue: BasicBlock


class BlocksBuilder:
    def __init__(
        self,
        parameters: Sequence[Register],
        default_source_location: SourceLocation,
    ) -> None:
        self._loop_targets_stack: list[_LoopTargets] = []
        blocks = [BasicBlock(id=0, source_location=default_source_location)]
        self._blocks = blocks
        # initialize ssa
        self.ssa = BraunSSA(blocks, parameters, self.active_block)
        self.ssa.seal_block(self.active_block)

        self._pending_labelled_blocks = dict[awst_nodes.Label, BasicBlock]()
        self._created_labelled_blocks = dict[awst_nodes.Label, BasicBlock]()

    @property
    def active_block(self) -> BasicBlock:
        return self._blocks[-1]

    def add(self, op: Op) -> None:
        """Add an op"""
        curr = self.active_block
        if curr.terminated:
            self._unreachable_error(op)
        else:
            curr.ops.append(op)
            if isinstance(op, Assignment):
                for target in op.targets:
                    if not self.ssa.has_write(target.name, curr):
                        raise InternalError(
                            f"ssa.write_variable not called for {target.name} in block {curr}"
                        )

    def maybe_terminate(self, control_op: ControlOp) -> bool:
        """Add the control op for the block, if not already terminated."""
        curr = self.active_block
        if curr.terminated:
            return False

        for target in control_op.targets():
            if self.ssa.is_sealed(target):
                raise InternalError(
                    f"Cannot add predecessor to block, as it is already sealed: "
                    f"predecessor={curr}, block={target}"
                )
            target.predecessors.append(curr)

        curr.terminator = control_op
        logger.debug(f"Terminated {curr}")
        return True

    def terminate(self, control_op: ControlOp) -> None:
        if not self.maybe_terminate(control_op):
            self._unreachable_error(control_op)

    def _unreachable_error(self, op: Op | ControlOp) -> None:
        if op.source_location:
            location = op.source_location
            message = "unreachable code"
        else:
            terminator_location = (
                self.active_block.terminator and self.active_block.terminator.source_location
            )
            location = terminator_location or self.active_block.source_location
            message = "unreachable code follows"
        logger.error(message, location=location)

    def goto(self, target: BasicBlock, source_location: SourceLocation | None = None) -> None:
        """Add goto to a basic block, iff current block is not already terminated"""
        self.maybe_terminate(Goto(target=target, source_location=source_location))

    def goto_label(self, label: awst_nodes.Label, source_location: SourceLocation) -> None:
        try:
            target = self._created_labelled_blocks[label]
        except KeyError:
            target = lazy_setdefault(
                self._pending_labelled_blocks,
                label,
                lambda _: BasicBlock(label=label, source_location=source_location),
            )
        self.goto(target, source_location)

    def activate_block(self, block: BasicBlock) -> None:
        self._activate_block(block)
        self._seal_block_if_unlabelled(block)

    @contextlib.contextmanager
    def activate_open_block(self, block: BasicBlock) -> Iterator[None]:
        self._activate_block(block)
        try:
            yield
        finally:
            self._seal_block_if_unlabelled(block)

    def _activate_block(self, block: BasicBlock) -> None:
        """Add a basic block and make it the active one (target of adds)"""
        if not self.active_block.terminated:
            raise InternalError(
                "Attempted to activate a new block when current block has not been terminated"
            )
        if not block.predecessors:
            raise InternalError("Attempted to add a (non-entry) block with no predecessors")
        assert block.id is None
        block.id = len(self._blocks)
        self._blocks.append(block)

    def try_activate_block(self, block: BasicBlock) -> bool:
        if block.predecessors:
            self.activate_block(block)
            return True
        if not block.is_empty:
            # here as a sanity - there shouldn't've been any modifications of "next" block contents
            raise InternalError("next block has no predecessors but does have op(s)")
        return False

    @contextlib.contextmanager
    def enter_loop(self, on_continue: BasicBlock, on_break: BasicBlock) -> Iterator[None]:
        self._loop_targets_stack.append(_LoopTargets(on_continue=on_continue, on_break=on_break))
        try:
            yield
        finally:
            self._loop_targets_stack.pop()

    def loop_break(self, source_location: SourceLocation) -> None:
        try:
            targets = self._loop_targets_stack[-1]
        except IndexError as ex:
            # TODO: this might be a code error or an internal error
            raise InternalError("break outside of loop", source_location) from ex
        self.goto(target=targets.on_break, source_location=source_location)

    def loop_continue(self, source_location: SourceLocation) -> None:
        try:
            targets = self._loop_targets_stack[-1]
        except IndexError as ex:
            # TODO: this might be a code error or an internal error
            raise InternalError("continue outside of loop", source_location) from ex
        self.goto(target=targets.on_continue, source_location=source_location)

    @typing.overload
    def mkblock(
        self, source_location: SourceLocation, /, description: str | None
    ) -> BasicBlock: ...

    @typing.overload
    def mkblock(
        self, block: awst_nodes.Block, /, description: str | None = None
    ) -> BasicBlock: ...

    @typing.overload
    def mkblock(
        self,
        block: awst_nodes.Block | None,
        /,
        description: str,
        *,
        fallback_location: SourceLocation,
    ) -> BasicBlock: ...

    def mkblock(
        self,
        block_or_source_location: awst_nodes.Block | SourceLocation | None,
        /,
        description: str | None = None,
        *,
        fallback_location: SourceLocation | None = None,
    ) -> BasicBlock:
        if isinstance(block_or_source_location, awst_nodes.Block):
            label = block_or_source_location.label
            comment = block_or_source_location.comment or description
            loc = block_or_source_location.source_location
        else:
            label = None
            comment = description
            loc_ = block_or_source_location or fallback_location
            assert loc_ is not None
            loc = loc_
        if label in self._created_labelled_blocks:
            raise InternalError(
                f"block for label {label} has already been created", fallback_location
            )
        if (label is not None) and (pending := self._pending_labelled_blocks.pop(label, None)):
            result = pending
            result.source_location = loc
            result.comment = comment
        else:
            result = BasicBlock(label=label, comment=comment, source_location=loc)
        if label is not None:
            self._created_labelled_blocks[label] = result
        return result

    def mkblocks(
        self, *descriptions: str, source_location: SourceLocation
    ) -> Iterator[BasicBlock]:
        for description in descriptions:
            yield self.mkblock(source_location, description)

    def finalise(self) -> list[BasicBlock]:
        for pending_label, pending in self._pending_labelled_blocks.items():
            logger.error(
                f"block with label {pending_label} not found", location=pending.source_location
            )
        for block in self._created_labelled_blocks.values():
            self.ssa.seal_block(block)
        self.ssa.verify_complete()
        return self._blocks.copy()

    def _seal_block_if_unlabelled(self, block: BasicBlock) -> None:
        if block.label is None:
            self.ssa.seal_block(block)
