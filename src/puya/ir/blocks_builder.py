import contextlib
from collections.abc import Iterator, Sequence

import attrs
import structlog

from puya.errors import InternalError
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import (
    Assignment,
    BasicBlock,
    ControlOp,
    Goto,
    Op,
    SubroutineReturn,
)
from puya.ir.ssa import BraunSSA
from puya.parse import SourceLocation

logger = structlog.get_logger(__name__)


@attrs.frozen(kw_only=True)
class _LoopTargets:
    on_break: BasicBlock
    on_continue: BasicBlock


class BlocksBuilder:
    def __init__(self, context: IRFunctionBuildContext) -> None:
        self.context = context
        self._loop_targets_stack: list[_LoopTargets] = []
        blocks = [BasicBlock(id=0, source_location=context.function.source_location)]
        self._blocks = blocks
        # initialize ssa
        self.ssa = BraunSSA(blocks, context.subroutine.parameters, self.active_block)
        self.ssa.seal_block(self.active_block)

    @property
    def blocks(self) -> Sequence[BasicBlock]:
        return self._blocks

    @property
    def active_block(self) -> BasicBlock:
        return self._blocks[-1]

    def add(self, op: Op) -> None:
        """Add an op"""
        curr = self._get_current_for_addition(op.source_location)
        if curr is not None:
            curr.ops.append(op)
            if isinstance(op, Assignment):
                for target in op.targets:
                    if not self.ssa.has_write(target.name, curr):
                        raise InternalError(
                            f"ssa.write_variable not called for {target.name} in block {curr}"
                        )

    def terminate(self, control_op: ControlOp) -> None:
        """Add the control op for the block, thus terminating it"""
        curr = self._get_current_for_addition(control_op.source_location)
        if curr is None:
            return
        if curr.terminated:
            raise InternalError(f"Block is already terminated: {curr}")

        for target in control_op.targets():
            if self.ssa.is_sealed(target):
                raise InternalError(
                    f"Cannot add predecessor to block, as it is already sealed: "
                    f"predecessor={curr}, block={target}"
                )
            target.predecessors.append(curr)

        curr.terminator = control_op
        logger.debug(f"Terminated {curr}")

    def _get_current_for_addition(
        self, source_location: SourceLocation | None
    ) -> BasicBlock | None:
        curr = self.active_block
        if curr.terminated:
            self.context.errors.error(
                "Unreachable code",
                # function kinda sucks as a fallback, but it'll do for now
                source_location or self.context.function.source_location,
            )
            return None
        return curr

    def goto(self, target: BasicBlock, source_location: SourceLocation | None = None) -> None:
        """Add goto to a basic block, iff current block is not already terminated"""
        curr = self._blocks[-1]
        if not curr.terminated:
            self.terminate(Goto(target=target, source_location=source_location))

    def validate_block_predecessors(self) -> None:
        """
        Validates all blocks bar the entry block have predecessors. Used to check the block
        builder is in a valid state after temporarily being in an invalid state due to
        ignore_predecessor_check
        """
        for non_entry_block in self._blocks[1:]:
            if not non_entry_block.predecessors:
                raise InternalError(
                    f"Unreachable block detected: block@{non_entry_block.id}",
                    non_entry_block.source_location,
                )

    def activate_block(self, block: BasicBlock, *, ignore_predecessor_check: bool = False) -> None:
        """Add a basic block and make it the active one (target of adds)"""
        if not self.active_block.terminated:
            raise InternalError(
                "Attempted to activate a new block when current block has not been terminated"
            )
        if not block.predecessors and not ignore_predecessor_check:
            raise InternalError("Attempted to add a (non-entry) block with no predecessors")
        block.id = len(self._blocks)
        self._blocks.append(block)

    def goto_and_activate(self, block: BasicBlock) -> None:
        """Add goto a block and make it the active block"""
        self.goto(block)
        self.activate_block(block)

    def maybe_add_implicit_subroutine_return(self) -> None:
        if not self._blocks[-1].terminated:
            self.terminate(SubroutineReturn(result=[], source_location=None))

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
