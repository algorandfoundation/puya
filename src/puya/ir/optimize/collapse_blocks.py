import contextlib
import itertools
from typing import Iterable

import attrs
import structlog

from puya.context import CompileContext
from puya.ir import models
from puya.ir.visitor_mutator import IRMutator
from puya.utils import unique

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(__name__)


@attrs.define
class BlockReferenceReplacer(IRMutator):
    find: models.BasicBlock
    replacement: models.BasicBlock

    @classmethod
    def apply(
        cls,
        find: models.BasicBlock,
        replacement: models.BasicBlock,
        blocks: Iterable[models.BasicBlock],
    ) -> None:
        replacer = cls(find=find, replacement=replacement)
        for block in blocks:
            replacer.visit_block(block)

    def visit_block(self, block: models.BasicBlock) -> None:
        super().visit_block(block)
        if self.find in block.predecessors:
            block.predecessors = [
                self.replacement if b is self.find else b for b in block.predecessors
            ]
            logger.debug(f"Replaced predecessor {self.find} with {self.replacement} in {block}")

    def visit_phi_argument(self, arg: models.PhiArgument) -> models.PhiArgument:
        if arg.through == self.find:
            arg.through = self.replacement
        return arg

    def visit_conditional_branch(self, branch: models.ConditionalBranch) -> models.ControlOp:
        if branch.zero == self.find:
            branch.zero = self.replacement
        if branch.non_zero == self.find:
            branch.non_zero = self.replacement
        return _replace_single_target_with_goto(branch)

    def visit_goto(self, goto: models.Goto) -> models.Goto:
        if goto.target == self.find:
            goto.target = self.replacement
        return goto

    def visit_goto_nth(self, goto_nth: models.GotoNth) -> models.ControlOp:
        if goto_nth.default == self.find:
            goto_nth.default = self.replacement
        for index, block in enumerate(goto_nth.blocks):
            if block == self.find:
                goto_nth.blocks[index] = self.replacement
        return _replace_single_target_with_goto(goto_nth)

    def visit_switch(self, switch: models.Switch) -> models.ControlOp:
        for case, target in switch.cases.items():
            if target == self.find:
                switch.cases[case] = self.replacement
        if switch.default == self.find:
            switch.default = self.replacement
        return _replace_single_target_with_goto(switch)


def _replace_single_target_with_goto(terminator: models.ControlOp) -> models.ControlOp:
    """
    If a ControlOp has a single target, replace it with a Goto, otherwise return the original op.
    """
    match unique(terminator.targets()):
        case [single_target]:
            return models.Goto(
                source_location=terminator.source_location,
                target=single_target,
            )
        case _:
            return terminator


def remove_linear_jump(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    changes = False
    for block in subroutine.body[1:]:
        match block.predecessors:
            case [models.BasicBlock(successors=[successor]) as predecessor]:
                assert successor is block
                # can merge blocks when there is an unconditional jump between them
                predecessor.phis.extend(block.phis)
                predecessor.ops.extend(block.ops)

                # this will update the predecessors of all block.successors to
                # now point back to predecessor e.g.
                # predecessor <-> block <-> [ss1, ...]
                # predecessor <-> [ss1, ...]
                BlockReferenceReplacer.apply(
                    find=block, replacement=predecessor, blocks=block.successors
                )

                predecessor.terminator = block.terminator

                # update block to reflect modifications
                subroutine.body.remove(block)
                changes = True
                logger.debug(f"Merged linear {block} into {predecessor}")
    return changes


def remove_empty_blocks(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    changes = False
    for block in subroutine.body:
        if not block.phis and not block.ops and isinstance(block.terminator, models.Goto):
            empty_block = block
            target = block.terminator.target

            if not empty_block.predecessors and block is not subroutine.body[0]:
                logger.info(
                    f"Not removing empty block {empty_block} because it's currently unreachable"
                )
                continue

            if target.phis:
                logger.info(
                    f"Not removing empty block {empty_block} because it's used by phi nodes"
                )
                continue

            # for phi in target.phis:
            #     for idx, arg in enumerate(phi.args):
            #         if arg.through == empty_block:
            #             phi.args[idx : idx + 1] = [
            #                 models.PhiArgument(
            #                     value=arg.value,
            #                     through=pred,
            #                 )
            #                 for pred in empty_block.predecessors
            #                 if pred not in target.predecessors
            #             ]
            #             break

            # this will replace any ops that pointed to block
            BlockReferenceReplacer.apply(
                find=empty_block,
                replacement=target,
                blocks=empty_block.predecessors,
            )

            # remove the empty block from the targets predecessors, and add and of the empty block
            # predecessors that aren't already present
            target.predecessors = unique(
                itertools.chain(empty_block.predecessors, target.predecessors)
            )
            # might have already been replaced by BlockReferenceReplacer
            with contextlib.suppress(ValueError):
                target.predecessors.remove(empty_block)

            subroutine.body.remove(empty_block)
            changes = True
            logger.debug(f"Removed empty block: {empty_block}")
    return changes
