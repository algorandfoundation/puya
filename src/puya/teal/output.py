import textwrap

import attrs

from puya.context import CompileContext
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
                if context.options.debug_level and (op_loc := teal_op.source_location):
                    whole_lines_location = attrs.evolve(
                        op_loc.with_comments(), column=None, end_column=None
                    )
                    if whole_lines_location != last_location:
                        last_location = whole_lines_location
                        src = context.try_get_source(whole_lines_location)
                        if src is not None:
                            result.append(f"{indent}// {whole_lines_location}")
                            lines = textwrap.dedent("\n".join(src)).splitlines()
                            result.extend(f"{indent}// {line.rstrip()}" for line in lines)

                result.append(f"{indent}{teal_op.teal()}")
            result.append("")
    return "\n".join(result)
