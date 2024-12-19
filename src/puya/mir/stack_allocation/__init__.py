from puya.mir import models
from puya.mir.context import ProgramMIRContext, SubroutineCodeGenContext
from puya.mir.output import output_memory_ir
from puya.mir.stack_allocation.f_stack import f_stack_allocation
from puya.mir.stack_allocation.l_stack import l_stack_allocation
from puya.mir.stack_allocation.peephole import peephole_optimization_single_pass
from puya.mir.stack_allocation.x_stack import x_stack_allocation

# Note: implementation of http://www.euroforth.org/ef06/shannon-bailey06.pdf


def global_stack_allocation(ctx: ProgramMIRContext, program: models.Program) -> None:
    for desc, method in {
        "lstack": l_stack_allocation,
        "lstack.opt": _peephole_optimization,
        "xstack": x_stack_allocation,
        "xstack.opt": _peephole_optimization,
        "fstack": f_stack_allocation,
        "fstack.opt": _peephole_optimization,
    }.items():
        for mir_sub in program.all_subroutines:
            sub_ctx = ctx.for_subroutine(mir_sub)
            method(sub_ctx)
        if ctx.options.output_memory_ir:
            output_memory_ir(ctx, program, qualifier=desc)
    if ctx.options.output_memory_ir:
        output_memory_ir(ctx, program, qualifier="")


def _peephole_optimization(ctx: SubroutineCodeGenContext) -> None:
    # replace sequences of stack manipulations with shorter ones
    vla_modified = False
    for block in ctx.subroutine.body:
        result = peephole_optimization_single_pass(ctx, block)
        vla_modified = vla_modified or result.vla_modified
    if vla_modified:
        ctx.invalidate_vla()
