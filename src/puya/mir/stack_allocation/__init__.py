from pathlib import Path

from puya.mir import models
from puya.mir.context import ProgramMIRContext, SubroutineCodeGenContext
from puya.mir.output import output_memory_ir, output_memory_ir_simple
from puya.mir.stack_allocation.baileys import baileys
from puya.mir.stack_allocation.frame_allocation import allocate_locals_on_stack
from puya.mir.stack_allocation.koopmans import koopmans
from puya.mir.stack_allocation.peephole import peephole_optimization_single_pass

# Note: implementation of http://www.euroforth.org/ef06/shannon-bailey06.pdf


def global_stack_allocation(
    ctx: ProgramMIRContext, program: models.Program, mir_output_path: Path | None
) -> None:
    passes = {
        "lstack": koopmans,
        "lstack.opt": _peephole_optimization,
        "xstack": baileys,
        "xstack.opt": _peephole_optimization,
        "fstack": allocate_locals_on_stack,
        "fstack.opt": _peephole_optimization,
    }

    for idx, (desc, method) in enumerate(passes.items()):
        for mir_sub in program.all_subroutines:
            sub_ctx = ctx.for_subroutine(mir_sub)
            method(sub_ctx)
        if ctx.options.output_memory_ir and mir_output_path:
            output_memory_ir_simple(
                ctx, program, mir_output_path.with_suffix(f".{idx}.{desc}.mir")
            )
    if ctx.options.output_memory_ir and mir_output_path:
        output_memory_ir(ctx, program, mir_output_path)


def _peephole_optimization(ctx: SubroutineCodeGenContext) -> None:
    # replace sequences of stack manipulations with shorter ones
    vla_modified = False
    for block in ctx.subroutine.body:
        result = peephole_optimization_single_pass(ctx, block)
        vla_modified = vla_modified or result.vla_modified
    if vla_modified:
        ctx.invalidate_vla()
