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
    int_template_vars = _gather_template_variables(program, teal.IntBlock)
    bytes_template_vars = _gather_template_variables(program, teal.BytesBlock)
    program_template_vars = {*int_template_vars, *bytes_template_vars}
    if debug_only:
        # use dummy template values to produce a debug map
        mocked_template_variables: Mapping[str, TemplateValue] = {
            **{t: (0, None) for t in int_template_vars if t not in template_variables},
            **{t: (b"", None) for t in bytes_template_vars if t not in template_variables},
        }
    else:
        mocked_template_variables = {}

    assemble_ctx = attrs_extend(
        AssembleContext,
        ctx,
        provided_template_variables={
            t: v for t, v in template_variables.items() if t in program_template_vars
        },
        mocked_template_variables=mocked_template_variables,
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
