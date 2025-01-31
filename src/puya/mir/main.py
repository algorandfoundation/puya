from puya.context import ArtifactCompileContext
from puya.ir import models as ir
from puya.mir import models
from puya.mir.builder import MemoryIRBuilder
from puya.mir.context import ProgramMIRContext
from puya.mir.stack_allocation import global_stack_allocation
from puya.utils import attrs_extend


def program_ir_to_mir(context: ArtifactCompileContext, program_ir: ir.Program) -> models.Program:
    ctx = attrs_extend(ProgramMIRContext, context, program=program_ir)

    result = models.Program(
        kind=program_ir.kind,
        main=_lower_subroutine_to_mir(ctx, program_ir.main, is_main=True),
        subroutines=[
            _lower_subroutine_to_mir(ctx, ir_sub, is_main=False)
            for ir_sub in program_ir.subroutines
        ],
        avm_version=program_ir.avm_version,
    )
    global_stack_allocation(ctx, result)
    return result


def _lower_subroutine_to_mir(
    context: ProgramMIRContext, subroutine: ir.Subroutine, *, is_main: bool
) -> models.MemorySubroutine:
    builder = MemoryIRBuilder(context=context, current_subroutine=subroutine, is_main=is_main)
    body = [builder.lower_block_to_mir(block) for block in subroutine.body]
    signature = models.Signature(
        name=subroutine.id,
        parameters=[
            models.Parameter(name=p.name, local_id=p.local_id, atype=p.atype)
            for p in subroutine.parameters
        ],
        returns=[r.avm_type for r in subroutine.returns],
    )
    return models.MemorySubroutine(
        id=context.subroutine_names[subroutine],
        signature=signature,
        is_main=is_main,
        body=body,
        source_location=subroutine.source_location,
    )
