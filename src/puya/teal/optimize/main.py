import copy

from puya.context import CompileContext
from puya.teal import models
from puya.teal.optimize.constant_stack_shuffling import (
    constant_dup2_insertion,
    constant_dupn_insertion,
    perform_constant_stack_shuffling,
)
from puya.teal.optimize.peephole import peephole
from puya.teal.optimize.repeated_rotations import simplify_repeated_rotation_ops, simplify_swap_ops
from puya.teal.optimize.repeated_rotations_search import repeated_rotation_ops_search


def optimize_block(block: models.TealBlock, *, level: int) -> None:
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
        block.ops = repeated_rotation_ops_search(block.ops)

    # simplifying uncover/cover 1 to swap is easier to do after other rotation optimizations
    simplify_swap_ops(block)


def optimize_teal_program(
    context: CompileContext, teal_program: models.TealProgram
) -> models.TealProgram:
    teal_program = copy.deepcopy(teal_program)
    for teal_sub in teal_program.all_subroutines:
        for teal_block in teal_sub.blocks:
            optimize_block(teal_block, level=context.options.optimization_level)
            teal_block.validate_stack_height()
    return teal_program
