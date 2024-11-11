import itertools
from pathlib import Path

from puya.context import CompileContext
from puya.ir import models as ir
from puya.mir import models
from puya.mir.builder import MemoryIRBuilder
from puya.mir.context import ProgramMIRContext
from puya.mir.stack_allocation import global_stack_allocation
from puya.utils import attrs_extend


def program_ir_to_mir(
    context: CompileContext, program_ir: ir.Program, mir_output_path: Path | None
) -> models.Program:
    ctx = attrs_extend(ProgramMIRContext, context, program=program_ir)

    result = models.Program(
        id=program_ir.id,
        main=_lower_subroutine_to_mir(ctx, program_ir.main, is_main=True, name=program_ir.id),
        subroutines=[
            _lower_subroutine_to_mir(ctx, ir_sub, is_main=False, name=ir_sub.full_name)
            for ir_sub in program_ir.subroutines
        ],
        avm_version=program_ir.avm_version,
    )
    global_stack_allocation(ctx, result, mir_output_path)
    return result


def _lower_subroutine_to_mir(
    context: ProgramMIRContext, subroutine: ir.Subroutine, *, is_main: bool, name: str
) -> models.MemorySubroutine:
    builder = MemoryIRBuilder(context=context, current_subroutine=subroutine, is_main=is_main)
    body = [
        builder.lower_block_to_mir(block, next_block)
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
        id=subroutine.full_name,
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
