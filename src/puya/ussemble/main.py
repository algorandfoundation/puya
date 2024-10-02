from collections.abc import Mapping, Sequence

from puya.context import CompileContext
from puya.models import TemplateValue
from puya.teal import models as teal
from puya.ussemble import models
from puya.ussemble.assemble import assemble_bytecode_and_debug_info
from puya.ussemble.context import AssembleContext
from puya.utils import attrs_extend


def assemble_program(
    ctx: CompileContext,
    program: teal.TealProgram,
    template_variables: Mapping[str, TemplateValue],
    *,
    debug_only: bool = False,
) -> models.AssembledProgram:
    if debug_only:
        # use dummy template values to produce a debug map
        program_variables: Mapping[str, TemplateValue] = {
            **{t: (0, None) for t in _gather_template_variables(program, teal.IntBlock)},
            **{t: (b"", None) for t in _gather_template_variables(program, teal.BytesBlock)},
        }
        offset_pc = any(program_variables.keys() - template_variables.keys())
        template_variables = {
            **program_variables,
            **template_variables,
        }
    else:
        offset_pc = False

    assemble_ctx = attrs_extend(
        AssembleContext,
        ctx,
        template_variables=template_variables,
        offset_pc_from_constant_blocks=offset_pc,
    )
    return assemble_bytecode_and_debug_info(assemble_ctx, program)


def _gather_template_variables[
    T: (teal.IntBlock, teal.BytesBlock)
](program: teal.TealProgram, typ: type[T],) -> Sequence[str]:
    return [
        t
        for sub in program.all_subroutines
        for block in sub.blocks
        for op in block.ops
        for t in (op.constants if isinstance(op, typ) else ())
        if isinstance(t, str)
    ]
