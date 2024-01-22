import itertools
from collections.abc import Iterable

from puya.context import CompileContext
from puya.ir import models as ir
from puya.mir import models
from puya.mir.builder import MemoryIRBuilder
from puya.mir.context import ProgramCodeGenContext
from puya.mir.stack_allocation import global_stack_allocation
from puya.utils import attrs_extend


def lower_subroutine_to_mir(
    context: ProgramCodeGenContext, subroutine: ir.Subroutine, *, is_main: bool
) -> models.MemorySubroutine:
    builder = MemoryIRBuilder(context=context, current_subroutine=subroutine, is_main=is_main)
    body = [
        builder.lower_block_to_teal(block, next_block)
        for block, next_block in itertools.zip_longest(subroutine.body, subroutine.body[1:])
    ]
    preamble = models.MemoryBasicBlock(
        context.subroutine_names[subroutine],
        ops=[],
        predecessors=[],
        successors=[body[0].block_name],
        source_location=subroutine.source_location or body[0].source_location,
    )
    if not is_main:
        preamble.ops.append(
            models.Proto(
                parameters=len(subroutine.parameters),
                returns=len(subroutine.returns),
                source_location=subroutine.source_location,
            )
        )
    return models.MemorySubroutine(
        signature=models.Signature(
            name=subroutine.full_name,
            parameters=[
                models.Parameter(name=p.name, local_id=p.local_id, atype=p.atype)
                for p in subroutine.parameters
            ],
            returns=subroutine.returns,
        ),
        is_main=is_main,
        preamble=preamble,
        body=body,
    )


def lower_program_ir_to_memory_ir(ctx: ProgramCodeGenContext) -> Iterable[models.MemorySubroutine]:
    program = ctx.program
    yield lower_subroutine_to_mir(ctx, program.main, is_main=True)
    for subroutine in program.subroutines:
        yield lower_subroutine_to_mir(ctx, subroutine, is_main=False)


def build_mir(context: CompileContext, program: ir.Program) -> list[models.MemorySubroutine]:
    cg_context = attrs_extend(ProgramCodeGenContext, context, program=program)
    subroutines = list(lower_program_ir_to_memory_ir(cg_context))
    for sub in subroutines:
        sub_ctx = cg_context.for_subroutine(sub)
        global_stack_allocation(sub_ctx)

    return subroutines
