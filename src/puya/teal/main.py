from puya import log
from puya.context import CompileContext
from puya.mir import models as mir
from puya.teal import models as teal_models
from puya.teal.builder import TealBuilder
from puya.teal.optimize.main import optimize_teal_program

logger = log.get_logger(__name__)


def mir_to_teal(context: CompileContext, program_mir: mir.Program) -> teal_models.TealProgram:
    main = TealBuilder.build_subroutine(program_mir.main)
    subroutines = [TealBuilder.build_subroutine(mir_sub) for mir_sub in program_mir.subroutines]
    teal = teal_models.TealProgram(
        avm_version=program_mir.avm_version,
        main=main,
        subroutines=subroutines,
    )
    optimize_teal_program(context, teal)
    return teal
