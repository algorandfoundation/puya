from puya import log
from puya.context import CompileContext
from puya.mir import models as mir
from puya.mir.stack import Stack
from puya.teal import models as teal_models
from puya.teal._util import preserve_stack_manipulations
from puya.teal.optimize.combine_pushes import combine_pushes
from puya.teal.optimize.constant_block import gather_program_constants
from puya.teal.optimize.main import optimize_teal_program

logger = log.get_logger(__name__)


def mir_to_teal(context: CompileContext, program_mir: mir.Program) -> teal_models.TealProgram:
    teal = _build_teal(context, program_mir)
    before = [
        sm
        for sub in teal.subroutines
        for block in sub.blocks
        for op in block.ops
        for sm in op.stack_manipulations
    ]
    if context.options.optimization_level > 0:
        teal = optimize_teal_program(context, teal)
    gather_program_constants(context, teal)
    if context.options.optimization_level > 0:
        teal = combine_pushes(teal)
    after = [
        sm
        for sub in teal.subroutines
        for block in sub.blocks
        for op in block.ops
        for sm in op.stack_manipulations
    ]
    assert before == after, "expected stack manipulations to be preserved after optimization"
    return teal


def _build_teal(context: CompileContext, mir_program: mir.Program) -> teal_models.TealProgram:
    program = teal_models.TealProgram(
        id=mir_program.id,
        target_avm_version=context.options.target_avm_version,
        main=_lower_sub(mir_program.main),
        subroutines=[_lower_sub(mir_sub) for mir_sub in mir_program.subroutines],
    )
    for teal_sub in program.all_subroutines:
        for teal_block in teal_sub.blocks:
            teal_block.validate()

    return program


def _lower_sub(mir_sub: mir.MemorySubroutine) -> teal_models.TealSubroutine:
    sub = teal_models.TealSubroutine(
        is_main=mir_sub.is_main,
        signature=mir_sub.signature,
    )

    stack = Stack(allow_virtual=False)
    referenced_labels = _get_referenced_labels(mir_sub)

    virtual_stack_manipulations_to_prepend = list[teal_models.StackManipulation]()
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
                    x_stack=mir_block.x_stack_in or (),
                    entry_stack_height=mir_block.entry_stack_height,
                    exit_stack_height=-1,
                )
            )
        last_block = sub.blocks[-1]
        last_block.exit_stack_height = mir_block.exit_stack_height

        for mir_op in mir_block.ops:
            if isinstance(mir_op, mir.VirtualStackOp):
                virtual_teal_ops = mir_op.original.accept(stack)
                if last_block.ops:
                    # extend previous teal op with stack manipulations in virtual op
                    last_op = last_block.ops[-1]
                    last_block.ops[-1:] = preserve_stack_manipulations(
                        [last_op], [last_op, *virtual_teal_ops]
                    )
                else:
                    virtual_stack_manipulations_to_prepend.extend(
                        [sm for teal_op in virtual_teal_ops for sm in teal_op.stack_manipulations]
                    )
            else:
                teal_ops = mir_op.accept(stack)
                if virtual_stack_manipulations_to_prepend and teal_ops:
                    first_op = teal_ops[0]
                    teal_ops[:1] = preserve_stack_manipulations(
                        [first_op], [*virtual_stack_manipulations_to_prepend, first_op]
                    )
                    virtual_stack_manipulations_to_prepend = []
                last_block.ops.extend(teal_ops)
    assert not virtual_stack_manipulations_to_prepend, "expected all virtual ops to be handled"

    stack = Stack(allow_virtual=False)
    mir_sm = list[teal_models.StackManipulation]()
    for mir_block in mir_sub.all_blocks:
        stack.begin_block(mir_sub, mir_block)
        for mir_op in mir_block.ops:
            if isinstance(mir_op, mir.VirtualStackOp):
                mir_op = mir_op.original
            teal_ops = mir_op.accept(stack)
            mir_sm.extend(sm for teal_op in teal_ops for sm in teal_op.stack_manipulations)

    teal_sm = [sm for block in sub.blocks for op in block.ops for sm in op.stack_manipulations]
    assert mir_sm == teal_sm, "expected stack manipulations to be preserved when lowering mir"
    return sub


def _get_referenced_labels(subroutine: mir.MemorySubroutine) -> set[str]:
    result = set[str]()
    for b in subroutine.all_blocks:
        for op in b.ops:
            if isinstance(op, mir.BranchingOp):
                result.update(op.targets())
    return result
