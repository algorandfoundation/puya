import copy
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


def optimize_teal_program(
    context: CompileContext, teal_program: models.TealProgram
) -> models.TealProgram:
    teal_program = copy.deepcopy(teal_program)
    for teal_sub in teal_program.all_subroutines:
        _optimize_subroutine(context, teal_sub)
    before = [_get_all_stack_manipulations(sub) for sub in teal_program.subroutines]
    gather_program_constants(teal_program)
    if context.options.optimization_level > 0:
        combine_pushes(teal_program)
    after = [_get_all_stack_manipulations(sub) for sub in teal_program.subroutines]
    assert before == after, "expected stack manipulations to be preserved after optimization"
    return teal_program


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
        _inline_jump_chains(teal_sub)
        _inline_single_op_blocks(teal_sub)
        _remove_unreachable_blocks(teal_sub)
        while _inline_singly_referenced_blocks(teal_sub):
            pass
        _remove_unreachable_blocks(teal_sub)
    _remove_jump_fallthroughs(teal_sub)
    _collapse_empty_blocks(teal_sub)


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
            case [models.Branch(target=target_label)]:
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
    _replace_labels(teal_sub, replacements)


def _inline_single_op_blocks(teal_sub: models.TealSubroutine) -> None:
    single_op_blocks = {b.label: b.ops for b in teal_sub.blocks if len(b.ops) == 1}
    for teal_block, next_block in itertools.zip_longest(teal_sub.blocks, teal_sub.blocks[1:]):
        while True:  # loop in case the inlined jump is to a block with a single jump itself
            match teal_block.ops[-1]:
                case models.Branch(target=target_label) as branch_op if (
                    (replace_ops := single_op_blocks.get(target_label))
                    and (next_block is None or target_label != next_block.label)
                ):
                    (replace_op,) = replace_ops
                    logger.debug(
                        f"replacing `{branch_op.teal()}` with `{replace_op.teal()}`",
                        location=branch_op.source_location,
                    )
                    preserve_stack_manipulations(teal_block.ops, slice(-1, None), replace_ops)
                case _:
                    break


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


def _inline_singly_referenced_blocks(teal_sub: models.TealSubroutine) -> bool:
    jump_targets = defaultdict[str, list[str]](list)
    for block in teal_sub.blocks:
        for op in block.ops:
            if isinstance(op, models.ControlOp):
                for target_label in op.targets:
                    jump_targets[target_label].append(op.op_code)

    inline_label_ops = {b.label: b.ops for b in teal_sub.blocks if jump_targets[b.label] == ["b"]}
    modified = False
    for block in teal_sub.blocks:
        if block.label in inline_label_ops:
            continue
        while True:
            match block.ops[-1]:
                case models.Branch(target=target_label) if (
                    replace_ops := inline_label_ops.get(target_label)
                ) is not None:
                    preserve_stack_manipulations(block.ops, slice(-1, None), replace_ops)
                    logger.debug(
                        f"inlining single reference block {target_label} into {block.label}"
                    )
                    modified = True
                case _:
                    break
    return modified


def _remove_jump_fallthroughs(teal_sub: models.TealSubroutine) -> None:
    for block, next_block in zip(teal_sub.blocks, teal_sub.blocks[1:], strict=False):
        match block.ops[-1]:
            case models.Branch(target=target_label) if target_label == next_block.label:
                logger.debug(f"removing explicit jump to fall-through block {next_block.label}")
                block.ops.pop()
                # preserve_stack_manipulations(
                #     block.ops, slice(len(block.ops) - 1, len(block.ops)), []
                # )


def _collapse_empty_blocks(teal_sub: models.TealSubroutine) -> None:
    blocks = teal_sub.blocks
    replacements = dict[str, str]()
    next_idx = len(blocks) - 1
    while next_idx > 0:
        next_label = blocks[next_idx].label
        curr_idx = next_idx - 1
        assert curr_idx >= 0
        for curr_idx in range(next_idx - 1, 0, -1):
            curr = blocks[curr_idx]
            if curr.ops:
                next_idx = curr_idx
                break
            blocks.pop(curr_idx)
            logger.debug(
                f"removing empty block {curr.label}, label will be replaced by {next_label}"
            )
            replacements[curr.label] = next_label
        else:
            break
    _replace_labels(teal_sub, replacements)


def _replace_labels(teal_sub: models.TealSubroutine, replacements: dict[str, str]) -> None:
    for block in teal_sub.blocks:
        for op_idx, op in enumerate(block.ops):
            if isinstance(op, models.Branch | models.BranchNonZero | models.BranchZero):
                if op.target in replacements:
                    block.ops[op_idx] = attrs.evolve(op, target=replacements[op.target])
            elif isinstance(op, models.Switch | models.Match):
                block.ops[op_idx] = attrs.evolve(
                    op, targets=[replacements.get(t, t) for t in op.targets]
                )
