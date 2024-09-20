from collections.abc import Mapping, Sequence

import attrs

from puya.context import CompileContext
from puya.models import TemplateValue
from puya.teal import models as teal
from puya.ussemble.build import lower_ops
from puya.ussemble.context import AssembleContext
from puya.ussemble.debug import build_debug_info
from puya.ussemble.output import AssembleVisitor
from puya.ussemble.validate import validate_labels
from puya.utils import attrs_extend


@attrs.frozen
class AssembledProgram:
    bytecode: bytes
    debug_info: bytes


def assemble_program(
    ctx: CompileContext,
    program: teal.TealProgram,
    template_variables: Mapping[str, TemplateValue],
    *,
    debug_only: bool = False,
) -> AssembledProgram:
    if debug_only:
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
    )
    avm_ops = lower_ops(assemble_ctx, program)
    validate_labels(avm_ops)
    assembled = AssembleVisitor.assemble(assemble_ctx, avm_ops)
    return AssembledProgram(
        bytecode=assembled.bytecode,
        debug_info=build_debug_info(
            assembled.source_map,
            assembled.events,
            offset_pc_from_constant_blocks=offset_pc,
        ),
    )


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
