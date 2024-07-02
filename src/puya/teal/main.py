from puya import log
from puya.context import CompileContext
from puya.mir import models as mir
from puya.mir.stack import Stack
from puya.teal import models as teal_models
from puya.teal.optimize.main import optimize_teal_program

logger = log.get_logger(__name__)


def mir_to_teal(context: CompileContext, program_mir: mir.Program) -> teal_models.TealProgram:
    teal = _build_teal(context, program_mir)
    if context.options.optimization_level > 0:
        teal = optimize_teal_program(context, teal)
    return teal


def _build_teal(context: CompileContext, mir_program: mir.Program) -> teal_models.TealProgram:
    program = teal_models.TealProgram(
        target_avm_version=context.options.target_avm_version,
        main=_lower_sub(mir_program.main),
        subroutines=[_lower_sub(mir_sub) for mir_sub in mir_program.subroutines],
    )
    for teal_sub in program.all_subroutines:
        for teal_block in teal_sub.blocks:
            teal_block.validate_stack_height()

    return program


def _lower_sub(mir_sub: mir.MemorySubroutine) -> teal_models.TealSubroutine:
    stack = Stack(allow_virtual=False)
    sub = teal_models.TealSubroutine(
        signature=str(mir_sub.signature) if not mir_sub.is_main else ""
    )
    referenced_labels = _get_referenced_labels(mir_sub)
    for block_idx, mir_block in enumerate(mir_sub.all_blocks):
        stack.begin_block(mir_sub, mir_block)
        if block_idx == 0 or mir_block.block_name in referenced_labels:
            sub.blocks.append(
                teal_models.TealBlock(
                    label=(
                        mir_block.block_name
                        if not (mir_sub.is_main and block_idx == 0)
                        else mir_sub.signature.name
                    ),
                    ops=[],
                    entry_stack_height=mir_block.entry_stack_height,
                    exit_stack_height=-1,
                )
            )
        sub.blocks[-1].exit_stack_height = mir_block.exit_stack_height

        sub.blocks[-1].ops.extend(
            teal_op for mir_op in mir_block.ops for teal_op in mir_op.accept(stack)
        )
    return sub


def _get_referenced_labels(subroutine: mir.MemorySubroutine) -> set[str]:
    result = set[str]()
    for b in subroutine.all_blocks:
        for op in b.ops:
            if isinstance(op, mir.BranchingOp):
                result.update(op.targets())
    return result
