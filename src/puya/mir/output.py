import textwrap

import attrs

from puya import log
from puya.context import ArtifactCompileContext, CompileContext
from puya.mir import models
from puya.mir.aligned_writer import AlignedWriter
from puya.mir.stack import Stack
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def output_memory_ir(
    ctx: ArtifactCompileContext, program: models.Program, *, qualifier: str
) -> None:
    output_path = ctx.build_output_path(program.kind, qualifier, "mir")
    if output_path is None:
        return
    writer = AlignedWriter()
    writer.add_header("// Op")
    writer.add_header("Stack (out)", 4)
    for subroutine in program.all_subroutines:
        writer.append_line(f"// {subroutine.signature}")
        writer.append_line(f"subroutine {subroutine.id}:")
        with writer.indent():
            if subroutine.pre_alloc:
                if subroutine.pre_alloc.bytes_vars:
                    writer.append(f"declare bytes {", ".join(subroutine.pre_alloc.bytes_vars)}")
                    writer.new_line()
                if subroutine.pre_alloc.uint64_vars:
                    writer.append(f"declare uint64 {", ".join(subroutine.pre_alloc.uint64_vars)}")
                    writer.new_line()
            for block in subroutine.body:
                stack = Stack.begin_block(subroutine, block)
                last_location = None
                writer.append(f"{block.block_name}:")
                writer.append(stack.full_stack_desc)
                writer.new_line()
                with writer.indent():
                    for op in block.ops:
                        last_location = _output_src_comment(
                            ctx, writer, last_location, op.source_location
                        )
                        op_str = str(op)
                        op.accept(stack)
                        # some ops can be very long (generally due to labels)
                        # in those (rare?) cases bypass the column alignment
                        if len(op_str) > 80:
                            writer.append_line(
                                writer.current_indent + op_str + " " + stack.full_stack_desc
                            )
                        else:
                            writer.append(op_str)
                            writer.append(stack.full_stack_desc)
                            writer.new_line()
                    writer.new_line()
        writer.new_line()
    writer.new_line()
    output_path.write_text("\n".join(writer.write()), "utf8")


def _output_src_comment(
    ctx: CompileContext,
    writer: AlignedWriter,
    last_loc: SourceLocation | None,
    op_loc: SourceLocation | None,
) -> SourceLocation | None:
    if op_loc:
        whole_lines_location = attrs.evolve(op_loc, column=None, end_column=None)
        if whole_lines_location != last_loc:
            last_loc = whole_lines_location
            src = ctx.try_get_source(whole_lines_location)
            if src is not None:
                writer.append(f"// {whole_lines_location}")
                writer.new_line()
                lines = textwrap.dedent("\n".join(src)).splitlines()
                for line in lines:
                    writer.append(f"// {line.rstrip()}")
                    writer.new_line()
    return last_loc
