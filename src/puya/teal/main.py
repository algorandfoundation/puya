import structlog

from puya.context import CompileContext
from puya.errors import InternalError
from puya.mir import models as mir
from puya.mir.stack import Stack
from puya.teal import models as teal_models

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(__name__)


def build_teal(
    context: CompileContext, mir_subroutines: list[mir.MemorySubroutine]
) -> teal_models.TealProgram:
    main_name = mir_subroutines[0].signature.name
    program = teal_models.TealProgram(
        target_avm_version=context.options.target_avm_version,
        subroutines=[],
        main=teal_models.TealSubroutine(signature=""),
    )

    for sub_idx, mir_sub in enumerate(mir_subroutines):
        stack = Stack(allow_virtual=False)
        if sub_idx == 0:
            if not mir_sub.is_main:
                raise InternalError("First subroutine for emit should be main")
            sub = program.main
        else:
            sub = teal_models.TealSubroutine(signature=str(mir_sub.signature))
            program.subroutines.append(sub)
        referenced_labels = _get_referenced_labels(mir_sub)
        for block_idx, mir_block in enumerate(mir_sub.all_blocks):
            stack.begin_block(mir_sub, mir_block)
            if block_idx == 0 or mir_block.block_name in referenced_labels:
                sub.blocks.append(
                    teal_models.TealBlock(
                        label=mir_block.block_name if (sub_idx or block_idx) else main_name,
                        ops=[],
                        entry_stack_height=mir_block.entry_stack_height,
                        exit_stack_height=-1,
                    )
                )
            sub.blocks[-1].exit_stack_height = mir_block.exit_stack_height

            sub.blocks[-1].ops.extend(
                teal_op for mir_op in mir_block.ops for teal_op in mir_op.accept(stack)
            )
    for teal_sub in program.all_subroutines:
        for teal_block in teal_sub.blocks:
            teal_block.validate_stack_height()

    return program


def _get_referenced_labels(subroutine: mir.MemorySubroutine) -> set[str]:
    result = set[str]()
    for b in subroutine.all_blocks:
        for op in b.ops:
            if isinstance(op, mir.BranchingOp):
                result.update(op.targets())
    return result
