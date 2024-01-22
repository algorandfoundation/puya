from puya.mir.context import SubroutineCodeGenContext
from puya.mir.stack_allocation.baileys import baileys
from puya.mir.stack_allocation.frame_allocation import allocate_locals_on_stack
from puya.mir.stack_allocation.koopmans import koopmans
from puya.mir.stack_allocation.peephole import peephole_optimization_single_pass

# Note: implementation of http://www.euroforth.org/ef06/shannon-bailey06.pdf


def global_stack_allocation(sub_ctx: SubroutineCodeGenContext) -> None:
    koopmans(sub_ctx)
    _peephole_optimization(sub_ctx)
    baileys(sub_ctx)
    _peephole_optimization(sub_ctx)
    allocate_locals_on_stack(sub_ctx)
    _peephole_optimization(sub_ctx)


def _peephole_optimization(ctx: SubroutineCodeGenContext) -> None:
    # replace sequences of stack manipulations with shorter ones
    vla_modified = False
    for block in ctx.subroutine.body:
        result = peephole_optimization_single_pass(ctx, block)
        vla_modified = vla_modified or result.vla_modified
    if vla_modified:
        ctx.invalidate_vla()
