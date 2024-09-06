import itertools
from pathlib import Path

from puya.context import CompileContext
from puya.ir import models as ir
from puya.mir import models
from puya.mir.builder import MemoryIRBuilder
from puya.mir.context import ProgramMIRContext
from puya.mir.output import output_memory_ir, output_variable_debug
from puya.mir.stack_allocation import global_stack_allocation
from puya.utils import attrs_extend


def program_ir_to_mir(
    context: CompileContext, program_ir: ir.Program, mir_output_path: Path | None
) -> models.Program:
    ctx = attrs_extend(ProgramMIRContext, context, program=program_ir)
    # TODO: resolve this earlier?
    for sub, sub_name in ctx.subroutine_names.items():
        context.debug.add_function(
            program_id=program_ir.id,
            full_name=sub.full_name,
            subroutine_label=sub_name,
            params={p.name: p.ir_type.name for p in sub.parameters},
            returns=[r.name for r in sub.returns],
        )

    result = models.Program(
        id=program_ir.id,
        main=_lower_subroutine_to_mir(ctx, program_ir.main, is_main=True, name=program_ir.id),
        subroutines=[
            _lower_subroutine_to_mir(ctx, ir_sub, is_main=False, name=ir_sub.full_name)
            for ir_sub in program_ir.subroutines
        ],
    )
    for mir_sub in result.all_subroutines:
        sub_ctx = ctx.for_subroutine(mir_sub)
        global_stack_allocation(sub_ctx)

    if context.options.output_memory_ir and mir_output_path:
        output_memory_ir(context, program_ir, result, mir_output_path)
    if mir_output_path:
        output_variable_debug(context, result, mir_output_path.with_suffix(".mir.dbg"))
    return result


def _lower_subroutine_to_mir(
    context: ProgramMIRContext, subroutine: ir.Subroutine, *, is_main: bool, name: str
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
            name=name,
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
