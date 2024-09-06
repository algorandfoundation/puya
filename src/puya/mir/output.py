from pathlib import Path

import attrs

from puya import log
from puya.context import CompileContext
from puya.ir import models as ir
from puya.mir import annotaters, models
from puya.mir.context import ProgramMIRContext
from puya.mir.stack import Stack
from puya.utils import attrs_extend

logger = log.get_logger(__name__)
# virtual stack ops can generate a lot of noise, so only turn on at highest debug level
VIRTUAL_STACK_DEBUG_LEVEL = 2


def _emit_op(
    context: annotaters.EmitProgramContext,
    op: models.BaseOp,
    op_annotaters: list[annotaters.OpAnnotater],
) -> None:
    teal_ops = op.accept(context.stack)
    if not teal_ops:
        debug_level = context.options.debug_level
        match op:
            case models.Comment():
                context.writer.append(f"// {op.comment}")
                if debug_level < 1:
                    context.writer.ignore_line()
            case _ if debug_level < VIRTUAL_STACK_DEBUG_LEVEL:
                context.writer.ignore_line()
    for teal_op_idx, teal_op in enumerate(teal_ops):
        context.writer.append(teal_op.teal())
        # omit new line for all but the last op
        if teal_op_idx < len(teal_ops) - 1:
            context.writer.new_line()
    for annotate_op in op_annotaters:
        annotate_op.annotate(context.writer, op)
    context.writer.new_line()


def _emit_subroutine(
    context: annotaters.EmitProgramContext, subroutine: models.MemorySubroutine
) -> None:
    subroutine_context = attrs_extend(
        annotaters.EmitSubroutineContext, context, subroutine=subroutine
    )
    writer = context.writer
    writer.append_line(f"// {subroutine.signature}")
    op_annotaters = [a.create_op_annotater(subroutine_context) for a in context.annotaters]
    for block in subroutine.all_blocks:
        if block.ops:
            context.stack.begin_block(subroutine, block)
            for annotate_op in op_annotaters:
                annotate_op.begin_block(writer, block)
            writer.append_line(f"{block.block_name}:")

            with writer.indent():
                for op in block.ops:
                    _emit_op(context, op, op_annotaters)
            writer.new_line()
    writer.new_line()


def emit_memory_ir(context: ProgramMIRContext, program: models.Program) -> list[str]:
    mir_annotations = [
        annotaters.BeginCommentsAnnotater(),
        annotaters.OpDescriptionAnnotation(),
        annotaters.StackAnnotation(),
        annotaters.VLAAnnotation(),
        annotaters.XStack(),
        annotaters.SourceAnnotation(),
    ]

    emit_context = attrs_extend(annotaters.EmitProgramContext, context, annotaters=mir_annotations)

    writer = emit_context.writer
    writer.add_header("// Op")
    for annotater in mir_annotations:
        annotater.header(writer)

    writer.new_line()
    writer.append_line(f"#pragma version {context.options.target_avm_version}")
    writer.new_line()

    for subroutine in program.all_subroutines:
        _emit_subroutine(emit_context, subroutine)
    return writer.write()


def output_memory_ir(
    context: CompileContext, ir_program: ir.Program, mir_program: models.Program, output_path: Path
) -> None:
    cg_context = attrs_extend(
        ProgramMIRContext,
        context,
        program=ir_program,
        options=attrs.evolve(context.options, debug_level=2),
    )
    mir_output = emit_memory_ir(cg_context, mir_program)
    output_path.write_text("\n".join(mir_output), "utf8")


def output_variable_debug(
    context: CompileContext, program: models.Program, output_path: Path
) -> None:
    output = []

    stack_state = {}

    def add(file: Path | None, line: int | None, state: str) -> None:
        if file is not None and line is not None:
            stack_state[(file, line)] = state

    stack = Stack(allow_virtual=False)
    for subroutine in program.all_subroutines:
        for block in subroutine.all_blocks:
            output.append(f"{block.block_name}:")
            stack.begin_block(subroutine, block)
            last_file: Path | None = None
            last_line: int | None = None
            for op in block.ops:
                file = last_file
                line = last_line
                if op.source_location:
                    file = op.source_location.file
                    line = op.source_location.line
                if last_file != file or last_line != line:
                    add(last_file, last_line, stack.full_stack_desc)
                    output.append(f"# stack: {stack.full_stack_desc}")
                last_file = file
                last_line = line
                op.accept(stack)
                op_desc = str(op)
                if not op_desc.startswith("virtual"):
                    output.append(f"    {op_desc}")
            add(last_file, last_line, stack.full_stack_desc)
            output.append(f"# stack: {stack.full_stack_desc}")
            output.append("")
        output.append("")
    output_path.write_text("\n".join([stack_state[i] for i in sorted(stack_state)]), "utf8")
