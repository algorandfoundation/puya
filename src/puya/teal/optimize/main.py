import itertools
from collections import defaultdict

import attrs

from puya import log
from puya.context import CompileContext
from puya.teal import models
from puya.teal._util import preserve_stack_manipulations
from puya.teal.optimize.combine_pushes import combine_pushes
from puya.teal.optimize.constant_block import gather_program_constants
from puya.teal.optimize.constant_stack_shuffling import (
    constant_dup2_insertion,
    constant_dupn_insertion,
    perform_constant_stack_shuffling,
)
from puya.teal.optimize.peephole import peephole
from puya.teal.optimize.repeated_rotations import simplify_repeated_rotation_ops, simplify_swap_ops
from puya.teal.optimize.repeated_rotations_search import repeated_rotation_ops_search

logger = log.get_logger(__name__)


def optimize_teal_program(context: CompileContext, teal_program: models.TealProgram) -> None:
    for teal_sub in teal_program.all_subroutines:
        _optimize_subroutine(context, teal_sub)
    before = [_get_all_stack_manipulations(sub) for sub in teal_program.subroutines]
    gather_program_constants(teal_program)
    if context.options.optimization_level > 0:
        combine_pushes(teal_program)
    after = [_get_all_stack_manipulations(sub) for sub in teal_program.subroutines]
    assert before == after, "expected stack manipulations to be preserved after optimization"


def _get_all_stack_manipulations(sub: models.TealSubroutine) -> list[models.StackManipulation]:
    return [sm for block in sub.blocks for op in block.ops for sm in op.stack_manipulations]


def _optimize_subroutine(context: CompileContext, teal_sub: models.TealSubroutine) -> None:
    logger.debug(
        f"optimizing TEAL subroutine {teal_sub.signature}", location=teal_sub.source_location
    )
    before = _get_all_stack_manipulations(teal_sub)
    for teal_block in teal_sub.blocks:
        _optimize_block(teal_block, level=context.options.optimization_level)
        teal_block.validate_stack_height()
    after = _get_all_stack_manipulations(teal_sub)
    assert before == after, "expected stack manipulations to be preserved after optimization"
    if context.options.optimization_level > 0:
        # at this point, blocks should still be almost "basic"
        # - control flow should only enter at the start of a block.
        # - control flow should only leave at the end of the block (although this might be
        #   spread over multiple ops in the case of say a switch or match)
        # - the final op must be an unconditional control flow op (e.g. retusb, b, return, err)
        _inline_jump_chains(teal_sub)
        # now all blocks that are just a b should have been inlined/removed.
        # any single-op blocks left must be non-branching control ops, ie ops
        # that terminate either exit the program or the subroutine.
        # inlining these are only possible when they are unconditionally branched to,
        # thus this still maintains the "almost basic" structure as outlined above.
        _inline_single_op_blocks(teal_sub)
        _inline_singly_referenced_blocks(teal_sub)
    _remove_jump_fallthroughs(teal_sub)


def _optimize_block(block: models.TealBlock, *, level: int) -> None:
    modified = True
    while modified:
        modified = False
        if level > 0:
            modified = perform_constant_stack_shuffling(block) or modified
            modified = simplify_repeated_rotation_ops(block) or modified
        modified = peephole(block, level) or modified

    # we don't do dup/dupn collapse in the above loop, but after it.
    # it's easier to deal with expanded dup/dupn instructions above when looking at
    # stack shuffling etc, but once it's done we save ops / program size by collapsing them
    constant_dupn_insertion(block)
    constant_dup2_insertion(block)
    if level >= 2:
        # this is a brute-force search which can be slow at times,
        # so it's only done once and only at higher optimisation levels
        block.ops[:] = repeated_rotation_ops_search(block.ops)

    # simplifying uncover/cover 1 to swap is easier to do after other rotation optimizations
    simplify_swap_ops(block)


def _inline_jump_chains(teal_sub: models.TealSubroutine) -> None:
    # build a map of any blocks that are just an unconditional branch to their targets
    jumps = dict[str, str]()
    for block_idx, block in enumerate(teal_sub.blocks.copy()):
        match block.ops:
            case [models.Branch(target=target_label) as b]:
                if b.stack_manipulations:
                    logger.debug(
                        "not inlining jump-block due to stack manipulations",
                        location=b.source_location,
                    )
                else:
                    jumps[block.label] = target_label
                    logger.debug(f"removing jump-chain block {block.label}")
                    teal_sub.blocks.pop(block_idx)
    # now back-propagate any chains
    replacements = dict[str, str]()
    for src, target in jumps.items():
        while True:
            try:
                target = jumps[target]
            except KeyError:
                break
        replacements[src] = target
        logger.debug(f"branching to {src} will be replaced with {target}")
    for block in teal_sub.blocks:
        for op_idx, op in enumerate(block.ops):
            if isinstance(op, models.Branch | models.BranchNonZero | models.BranchZero):
                if op.target in replacements:
                    block.ops[op_idx] = attrs.evolve(op, target=replacements[op.target])
            elif isinstance(op, models.Switch | models.Match):
                block.ops[op_idx] = attrs.evolve(
                    op, targets=[replacements.get(t, t) for t in op.targets]
                )


def _inline_single_op_blocks(teal_sub: models.TealSubroutine) -> None:
    # TODO: this should only encounter exiting ops, so we don't need a traversal to find unused,
    #       just keep track of predecessors??
    single_op_blocks = {b.label: b.ops for b in teal_sub.blocks if len(b.ops) == 1}
    modified = False
    for teal_block, next_block in itertools.zip_longest(teal_sub.blocks, teal_sub.blocks[1:]):
        match teal_block.ops[-1]:
            case models.Branch(target=target_label) as branch_op if (
                (replace_ops := single_op_blocks.get(target_label))
                and (next_block is None or target_label != next_block.label)
            ):
                modified = True
                (replace_op,) = replace_ops
                # we shouldn't encounter any branching ops, since any block that
                # is just an unconditional branch has already been inlined, and
                # at this point blocks should still have an unconditional exit as the final op,
                # which rules out bz/bnz/match/switch, leaving only exiting ops
                # like retsub, return, or err.
                # this also means we can keep track of which blocks to eliminate without having
                # to do a traversal, thus the assertion
                assert isinstance(replace_op, models.ControlOp) and not replace_op.targets
                logger.debug(
                    f"replacing `{branch_op.teal()}` with `{replace_op.teal()}`",
                    location=branch_op.source_location,
                )
                preserve_stack_manipulations(teal_block.ops, slice(-1, None), replace_ops)
    if modified:
        # if any were inlined, they may no longer be referenced and thus removable
        _remove_unreachable_blocks(teal_sub)


def _remove_unreachable_blocks(teal_sub: models.TealSubroutine) -> None:
    entry = teal_sub.blocks[0]
    to_visit = [entry]
    unreachable_blocks_by_label = {b.label: b for b in teal_sub.blocks[1:]}
    while to_visit:
        current_block = to_visit.pop()
        for op in current_block.ops:
            if isinstance(op, models.ControlOp):
                to_visit.extend(
                    target
                    for target_label in op.targets
                    if (target := unreachable_blocks_by_label.pop(target_label, None))
                )
    if unreachable_blocks_by_label:
        logger.debug(f"removing unreachable blocks: {list(map(str, unreachable_blocks_by_label))}")
        teal_sub.blocks[:] = [
            b for b in teal_sub.blocks if b.label not in unreachable_blocks_by_label
        ]


def _inline_singly_referenced_blocks(teal_sub: models.TealSubroutine) -> None:
    predecessors = defaultdict[str, list[str]](list)
    predecessors[teal_sub.blocks[0].label].append("<entrypoint>")
    for block in teal_sub.blocks:
        for op in block.ops:
            if isinstance(op, models.ControlOp):
                for target_label in op.targets:
                    predecessors[target_label].append(block.label)

    pairs = dict[str, str]()
    inlineable = set[str]()
    for block in teal_sub.blocks:
        match block.ops[-1]:
            case models.Branch(target=target_label):
                target_predecessors = predecessors[target_label]
                if len(target_predecessors) == 1:
                    assert target_predecessors == [block.label]
                    pairs[block.label] = target_label
                    inlineable.add(target_label)

    blocks_by_label = {b.label: b for b in teal_sub.blocks}
    result = list[models.TealBlock]()
    for block in teal_sub.blocks:
        this_label = block.label
        if this_label not in inlineable:
            result.append(block)
            while (next_label := pairs.get(this_label)) is not None:
                logger.debug(f"inlining single reference block {next_label} into {block.label}")
                next_block = blocks_by_label[next_label]
                preserve_stack_manipulations(block.ops, slice(-1, None), next_block.ops)
                this_label = next_label
    teal_sub.blocks[:] = result


def _remove_jump_fallthroughs(teal_sub: models.TealSubroutine) -> None:
    for block, next_block in zip(teal_sub.blocks, teal_sub.blocks[1:], strict=False):
        match block.ops[-1]:
            # we guard against having stack manipulations but only one op, thus nowhere to put
            # them, but this should only occur in O0 as in higher levels, blocks with just a b
            # will already be inlined
            case models.Branch(
                target=target_label, stack_manipulations=sm
            ) if target_label == next_block.label and (len(block.ops) > 1 or not sm):
                logger.debug(f"removing explicit jump to fall-through block {next_block.label}")
                block.ops.pop()
                if block.ops:  # guard is only for O0 case
                    block.ops[-1] = attrs.evolve(
                        block.ops[-1],
                        stack_manipulations=(*block.ops[-1].stack_manipulations, *sm),
                    )
