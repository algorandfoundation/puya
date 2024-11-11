from puya import log
from puya.context import CompileContext
from puya.mir import models as mir
from puya.teal import models as teal_models
from puya.teal.builder import TealBuilder
from puya.teal.optimize.combine_pushes import combine_pushes
from puya.teal.optimize.constant_block import gather_program_constants
from puya.teal.optimize.main import optimize_teal_program

logger = log.get_logger(__name__)


def mir_to_teal(context: CompileContext, program_mir: mir.Program) -> teal_models.TealProgram:
    teal = _build_teal(program_mir)
    before = _get_all_stack_manipulations(teal)

    teal = optimize_teal_program(context, teal)
    gather_program_constants(teal)
    if context.options.optimization_level > 0:
        teal = combine_pushes(teal)
    after = _get_all_stack_manipulations(teal)

    assert before == after, "expected stack manipulations to be preserved after optimization"
    return teal


def _get_all_stack_manipulations(
    teal: teal_models.TealProgram,
) -> list[teal_models.StackManipulation]:
    return [
        sm
        for sub in teal.subroutines
        for block in sub.blocks
        for op in block.ops
        for sm in op.stack_manipulations
    ]


def _build_teal(mir_program: mir.Program) -> teal_models.TealProgram:
    program = teal_models.TealProgram(
        id=mir_program.id,
        avm_version=mir_program.avm_version,
        main=TealBuilder.build_subroutine(mir_program.main),
        subroutines=[TealBuilder.build_subroutine(mir_sub) for mir_sub in mir_program.subroutines],
    )
    for teal_sub in program.all_subroutines:
        for teal_block in teal_sub.blocks:
            teal_block.validate_stack_height()

    return program
