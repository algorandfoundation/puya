import itertools
from pathlib import Path

from puya.context import CompileContext
from puya.ir import models as ir
from puya.mir import models
from puya.mir.builder import MemoryIRBuilder
from puya.mir.context import ProgramMIRContext
from puya.mir.output import output_memory_ir
from puya.mir.stack_allocation import global_stack_allocation
from puya.utils import attrs_extend


def program_ir_to_mir(
    context: CompileContext, program_ir: ir.Program, mir_output_path: Path | None
) -> models.Program:
    ctx = attrs_extend(ProgramMIRContext, context, program=program_ir)

    result = models.Program(
        main=_lower_subroutine_to_mir(ctx, program_ir.main, is_main=True),
        subroutines=[
            _lower_subroutine_to_mir(ctx, ir_sub, is_main=False)
            for ir_sub in program_ir.subroutines
        ],
    )
    for mir_sub in result.all_subroutines:
        sub_ctx = ctx.for_subroutine(mir_sub)
        global_stack_allocation(sub_ctx)

    if context.options.output_memory_ir and mir_output_path:
        output_memory_ir(context, program_ir, result, mir_output_path)
    return result


def _lower_subroutine_to_mir(
    context: ProgramMIRContext, subroutine: ir.Subroutine, *, is_main: bool
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
            returns=[r.avm_type for r in subroutine.returns],
        ),
        is_main=is_main,
        preamble=preamble,
        body=body,
    )
