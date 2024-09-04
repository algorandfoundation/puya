from collections.abc import Mapping

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
    ctx: CompileContext, program: teal.TealProgram, template_variables: Mapping[str, TemplateValue]
) -> AssembledProgram:
    assemble_ctx = attrs_extend(
        AssembleContext,
        ctx,
        template_variables=template_variables,
    )
    avm_ops = lower_ops(assemble_ctx, program)
    validate_labels(avm_ops)
    # TODO: move optimization to TEAL
    # avm_ops = optimize_ops(assemble_ctx, avm_ops)

    assembled = AssembleVisitor.assemble(assemble_ctx, avm_ops)
    return AssembledProgram(
        bytecode=assembled.bytecode,
        debug_info=build_debug_info(assembled.source_map, assembled.events),
    )
