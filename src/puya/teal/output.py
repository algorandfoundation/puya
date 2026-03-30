import textwrap
from collections.abc import Sequence

import attrs
import prettytable

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

    writer = prettytable.PrettyTable(
        field_names=[
            "PC",
            "TEAL Bytes",
            "TEAL",
            "Source",
            "Location",
        ],
        header=True,
        align="l",
    )
    writer.set_style(prettytable.TableStyle.MARKDOWN)
    writer.align["PC"] = "r"
    writer.align["|"] = "c"
    writer.max_width["TEAL Bytes"] = 48
    writer.max_width["TEAL"] = 64

    # Start with the teal version
    writer.add_row(
        [
            "0",
            bytecode[0 : instruction_boundaries[0]].hex(" "),
            f"#pragma version {program.avm_version}",
            "",
            "",
        ]
    )

    indent = " " * 4  # Ident for TEAL code
    src = None
    line_bytes = None
    isn_idx = 0
    for subroutine in program.all_subroutines:
        for block_idx, block in enumerate(subroutine.blocks):
            last_location = None
            if block_idx == 0:
                writer.add_row(
                    ["", f"# {block.label}", f"{block.label}:", "", str(subroutine.signature)]
                )
            else:
                writer.add_row(["", f"# {block.label}", f"{block.label}:", "", ""])
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
                            line_bytes = line.encode("utf8")
                            writer.add_row(["", "", "", line.strip(), str(whole_lines_location)])
                    if (
                        op_loc.column is not None
                        and op_loc.end_column is not None
                        and line_bytes is not None
                    ):
                        highlight_prefix = line_bytes[: op_loc.column].decode("utf8")
                        highlight_start = len(highlight_prefix.lstrip())
                        highlight_chars = line_bytes[op_loc.column : op_loc.end_column].decode(
                            "utf8"
                        )
                        highlight_width = len(highlight_chars)
                        op_highlight = " " * highlight_start + "-" * highlight_width
                writer.add_row(
                    [
                        str(pc),
                        teal_bytes.hex(" "),
                        f"{indent}{teal_op.teal(with_comments=True)}",
                        op_highlight,
                        op_loc_str,
                    ]
                )
                isn_idx += 1

    return writer.get_string()


def maybe_output_intermediate_teal(
    context: ArtifactCompileContext, program: models.TealProgram, *, qualifier: str
) -> None:
    if context.options.output_teal_intermediates:
        path = context.build_output_path(kind=program.kind, qualifier=qualifier, suffix="teal")
        if path is not None:
            output = emit_teal(context, program, include_stack_manipulations=True)
            path.write_text(output, encoding="utf8")
