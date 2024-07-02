import textwrap

from puya.context import CompileContext
from puya.parse import SourceLocation
from puya.teal import models


def emit_teal(context: CompileContext, program: models.TealProgram) -> str:
    indent = " " * 4

    result = [
        f"#pragma version {context.options.target_avm_version}",
        "",
    ]
    for subroutine in program.all_subroutines:
        if subroutine.signature:
            result.append("")
            result.append(f"// {subroutine.signature}")

        for block in subroutine.blocks:
            last_location = None
            result.append(f"{block.label}:")
            for teal_op in block.ops:
                if context.options.debug_level and teal_op.source_location is not None:
                    whole_lines_location = SourceLocation(
                        file=teal_op.source_location.file,
                        line=teal_op.source_location.line,
                        end_line=teal_op.source_location.end_line,
                    )
                    if whole_lines_location != last_location:
                        last_location = whole_lines_location
                        src = context.try_get_source(whole_lines_location)
                        result.append(f"{indent}// {src.location}")
                        lines = textwrap.dedent("\n".join(src.code or ())).splitlines()
                        result.extend(f"{indent}// {line.rstrip()}" for line in lines)

                result.append(f"{indent}{teal_op.teal()}")
            result.append("")
    return "\n".join(result)
