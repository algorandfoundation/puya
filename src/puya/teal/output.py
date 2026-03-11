import textwrap
from collections.abc import Sequence

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
                result.append(f"{indent}{teal_op.teal(with_comments=True)}")
            result.append("")
    return "\n".join(result)


def emit_assembly_report(
    context: ArtifactCompileContext,
    program: models.TealProgram,
    bytecode: bytes,
    instruction_boundaries: Sequence[int],
) -> str:
    # Entries are a 5-tuple (pc, bytes, teal, source, location):
    # - When a new line is to be used it has its own row
    # - Teal ops highlight the relevant columns from the last line emitted
    # - Teal labels have its own row
    # - Contract prefixes have their own line
    # - Source locations are only emitted for "line" rows

    # Prefixed by the teal version
    result = [
        (
            "0",
            bytecode[0 : instruction_boundaries[0]].hex(" "),
            f"#pragma version {program.avm_version}",
            "",
            "",
        )
    ]

    src = None
    last_location_indent = 0
    isn_idx = 0
    for subroutine in program.all_subroutines:
        for block_idx, block in enumerate(subroutine.blocks):
            last_location = None
            if block_idx == 0:
                result.append(
                    ("", f"# {block.label}", f"{block.label}:", "", str(subroutine.signature))
                )
            else:
                result.append(("", f"# {block.label}", f"{block.label}:", "", ""))
            for teal_op in block.ops:
                pc = instruction_boundaries[isn_idx]
                teal_bytes = bytecode[pc : instruction_boundaries[isn_idx + 1]]
                op_highlight = ""
                op_loc = teal_op.source_location
                if op_loc is None:
                    op_loc_str = ""
                elif op_loc.line != op_loc.end_line:
                    op_loc_str = repr(op_loc)
                else:
                    op_loc_str = repr(op_loc)
                    whole_lines_location = attrs.evolve(op_loc, column=None, end_column=None)
                    if whole_lines_location != last_location:
                        last_location = whole_lines_location
                        src = context.try_get_source(whole_lines_location)
                        if src is not None:
                            line = src[0]
                            last_location_indent = len(line) - len(line.lstrip())
                            result.append(("", "", "", line.strip(), str(whole_lines_location)))
                    if (
                        op_loc.column is not None
                        and op_loc.end_column is not None
                        and src is not None
                    ):
                        highlight_start = op_loc.column - last_location_indent
                        highlight_width = op_loc.end_column - op_loc.column
                        op_highlight = " " * highlight_start + "-" * highlight_width
                result.append(
                    (
                        str(pc),
                        teal_bytes.hex(" "),
                        teal_op.teal(with_comments=True),
                        op_highlight,
                        op_loc_str,
                    )
                )
                isn_idx += 1

    pc_width = max(len(row[0]) for row in result)
    # cblocks / pushbytes / switch can become too long. Break formatting when that happens.
    bytes_width = min(48, max(len(row[1]) for row in result))
    teal_width = min(64, max(len(row[2]) for row in result))
    source_width = max(len(row[3]) for row in result)
    formatted_rows = (
        f"{row[0].rjust(pc_width)} | {row[1].ljust(bytes_width)} | {row[2].ljust(teal_width)} | "
        f"{row[3].ljust(source_width)} | {row[4]}"
        for row in result
    )

    return "\n".join(formatted_rows)


def maybe_output_intermediate_teal(
    context: ArtifactCompileContext, program: models.TealProgram, *, qualifier: str
) -> None:
    if context.options.output_teal_intermediates:
        path = context.build_output_path(kind=program.kind, qualifier=qualifier, suffix="teal")
        if path is not None:
            output = emit_teal(context, program, include_stack_manipulations=True)
            path.write_text(output, encoding="utf8")
