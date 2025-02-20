import textwrap

import attrs

from puya.context import ArtifactCompileContext
from puya.teal import models


def emit_teal(
    context: ArtifactCompileContext,
    program: models.TealProgram,
    *,
    include_stack_manipulations: bool = False,
) -> str:
    indent = " " * 4

    result = [
        f"#pragma version {program.avm_version}",
        "#pragma typetrack false",
        "",
    ]
    for idx, subroutine in enumerate(program.all_subroutines):
        if idx > 0:
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
                if include_stack_manipulations and teal_op.stack_manipulations:
                    result.append(f"{indent}// stack manipulations = [")
                    result.extend(f"{indent}//   {sm!r}" for sm in teal_op.stack_manipulations)
                    result.append(f"{indent}// ]")
                result.append(f"{indent}{teal_op.teal()}")
            result.append("")
    return "\n".join(result)


def maybe_output_intermediate_teal(
    context: ArtifactCompileContext, program: models.TealProgram, *, qualifier: str
) -> None:
    if context.options.output_teal_intermediates:
        path = context.build_output_path(kind=program.kind, qualifier=qualifier, suffix="teal")
        if path is not None:
            output = emit_teal(context, program, include_stack_manipulations=True)
            path.write_text(output, encoding="utf8")
