from puya.mir import models
from puya.mir.context import ProgramMIRContext
from puya.mir.output import output_memory_ir
from puya.mir.stack_allocation.f_stack import f_stack_allocation
from puya.mir.stack_allocation.l_stack import l_stack_allocation
from puya.mir.stack_allocation.peephole import peephole_optimization_single_pass
from puya.mir.stack_allocation.x_stack import x_stack_allocation

# Note: implementation of http://www.euroforth.org/ef06/shannon-bailey06.pdf


def global_stack_allocation(ctx: ProgramMIRContext, program: models.Program) -> None:
    for desc, (method, min_opt_level) in {
        "lstack": (l_stack_allocation, 0),
        "lstack.opt": (peephole_optimization_single_pass, 1),
        "xstack": (x_stack_allocation, 1),
        "xstack.opt": (peephole_optimization_single_pass, 1),
        "fstack": (f_stack_allocation, 0),
        "fstack.opt": (peephole_optimization_single_pass, 1),
    }.items():
        if ctx.options.optimization_level < min_opt_level:
            continue
        for mir_sub in program.all_subroutines:
            method(ctx, mir_sub)
        if ctx.options.output_memory_ir:
            output_memory_ir(ctx, program, qualifier=desc)
    if ctx.options.output_memory_ir:
        output_memory_ir(ctx, program, qualifier="")
