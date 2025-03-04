from puya.mir import models
from puya.mir.context import ProgramMIRContext
from puya.mir.output import output_memory_ir
from puya.mir.stack_allocation.f_stack import f_stack_allocation
from puya.mir.stack_allocation.l_stack import l_stack_allocation
from puya.mir.stack_allocation.peephole import peephole_optimization_single_pass
from puya.mir.stack_allocation.x_stack import x_stack_allocation

# Note: implementation of http://www.euroforth.org/ef06/shannon-bailey06.pdf


def global_stack_allocation(ctx: ProgramMIRContext, program: models.Program) -> None:
    for desc, method in {
        "lstack": l_stack_allocation,
        "lstack.opt": peephole_optimization_single_pass,
        "xstack": x_stack_allocation,
        "xstack.opt": peephole_optimization_single_pass,
        "fstack": f_stack_allocation,
        "fstack.opt": peephole_optimization_single_pass,
    }.items():
        for mir_sub in program.all_subroutines:
            method(ctx, mir_sub)
        if ctx.options.output_memory_ir:
            output_memory_ir(ctx, program, qualifier=desc)
    if ctx.options.output_memory_ir:
        output_memory_ir(ctx, program, qualifier="")
