import structlog

from puya.codegen import ops
from puya.codegen.context import ProgramCodeGenContext
from puya.codegen.teal_annotaters import (
    AlignedWriter,
    EmitProgramContext,
    EmitSubroutineContext,
    OpAnnotater,
    SimpleOpAnnotater,
    TealAnnotater,
    debug_annotations,
)
from puya.codegen.vla import VariableLifetimeAnalysis
from puya.utils import attrs_extend

logger = structlog.get_logger(__name__)
# virtual stack ops can generate a lot of noise, so only turn on at highest debug level
VIRTUAL_STACK_DEBUG_LEVEL = 2


def emit_op(context: EmitProgramContext, op: ops.BaseOp, op_annotaters: list[OpAnnotater]) -> None:
    teal_ops = op.accept(context.stack)
    if not teal_ops:
        debug_level = context.options.debug_level
        match op:
            case ops.Comment():
                context.writer.append(f"// {op.comment}")
                if debug_level < 1:
                    context.writer.ignore_line()
            case _ if debug_level < VIRTUAL_STACK_DEBUG_LEVEL:
                context.writer.ignore_line()
    for teal_op_idx, teal_op in enumerate(teal_ops):
        context.writer.append(str(teal_op))
        # omit new line for all but the last op
        if teal_op_idx < len(teal_ops) - 1:
            context.writer.new_line()
    for annotate_op in op_annotaters:
        annotate_op.annotate(context.writer, op)
    context.writer.new_line()


def emit_subroutine(context: EmitProgramContext, subroutine: ops.MemorySubroutine) -> None:
    vla = VariableLifetimeAnalysis.analyze(subroutine)
    subroutine_context = attrs_extend(
        EmitSubroutineContext, context, subroutine=subroutine, vla=vla
    )
    writer = context.writer
    writer.append_line(f"// {subroutine.signature}")
    with writer.indent():
        op_annotaters = [a.create_op_annotater(subroutine_context) for a in context.annotaters]
        for block in subroutine.all_blocks:
            context.stack.begin_block(subroutine, block)
            for annotate_op in op_annotaters:
                annotate_op.begin_block(writer, block)
            writer.append_line(f"{block.block_name}:")

            with writer.indent():
                for op in block.ops:
                    emit_op(context, op, op_annotaters)
            writer.new_line()
        writer.new_line()


class _BeginCommentsAnnotater(TealAnnotater):
    def header(self, writer: AlignedWriter) -> None:
        writer.add_header("//")

    def create_op_annotater(self, _context: EmitSubroutineContext) -> OpAnnotater:
        def annotate(writer: AlignedWriter, _op: ops.BaseOp) -> None:
            writer.append("//")

        return SimpleOpAnnotater(annotate)


def emit_memory_ir_as_teal(
    context: ProgramCodeGenContext, subroutines: list[ops.MemorySubroutine]
) -> list[str]:
    annotaters = debug_annotations.copy() if context.options.debug_level else []
    if annotaters:
        annotaters.insert(0, _BeginCommentsAnnotater())
    emit_context = attrs_extend(EmitProgramContext, context, annotaters=annotaters)

    writer = emit_context.writer
    if annotaters:
        writer.add_header("// Op")
        for annotater in annotaters:
            annotater.header(writer)

        writer.new_line()
    writer.append_line("#pragma version 8")
    writer.new_line()

    for subroutine in subroutines:
        emit_subroutine(emit_context, subroutine)
    return writer.write()
