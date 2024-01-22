import copy

from puya.context import CompileContext
from puya.teal import models
from puya.teal.optimize.constant_stack_shuffling import perform_constant_stack_shuffling
from puya.teal.optimize.peephole import peephole
from puya.teal.optimize.repeated_rotations import simplify_repeated_rotation_ops
from puya.teal.optimize.repeated_rotations_search import repeated_rotation_ops_search


def optimize_block(block: models.TealBlock, *, level: int) -> None:
    modified = True
    while modified:
        modified = perform_constant_stack_shuffling(block)
        modified = modified or simplify_repeated_rotation_ops(block)
        modified = modified or peephole(block)

    if level >= 2:
        block.ops = repeated_rotation_ops_search(block.ops)


def optimize_teal_program(
    context: CompileContext, teal_program: models.TealProgram
) -> models.TealProgram:
    teal_program = copy.deepcopy(teal_program)
    for teal_sub in teal_program.all_subroutines:
        for teal_block in teal_sub.blocks:
            optimize_block(teal_block, level=context.options.optimization_level)
            teal_block.validate_stack_height()
    return teal_program
