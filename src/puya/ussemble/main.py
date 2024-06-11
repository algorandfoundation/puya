from collections.abc import Mapping

import attrs

from puya.context import CompileContext
from puya.parse import SourceLocation
from puya.teal import models as teal
from puya.ussemble.build import lower_ops
from puya.ussemble.context import AssembleContext
from puya.ussemble.optimize import optimize_ops
from puya.ussemble.output import AssembleVisitor
from puya.ussemble.validate import validate_labels
from puya.utils import attrs_extend


@attrs.frozen
class AssembledProgram:
    bytecode: bytes
    source_map: dict[int, SourceLocation]


def assemble_program(
    ctx: CompileContext, program: teal.TealProgram, template_variables: Mapping[str, int | bytes]
) -> AssembledProgram:
    assemble_ctx = attrs_extend(
        AssembleContext,
        ctx,
        template_variables=template_variables,
    )
    avm_ops = lower_ops(assemble_ctx, program)
    validate_labels(avm_ops)
    avm_ops = optimize_ops(assemble_ctx, avm_ops)

    return AssembledProgram(
        bytecode=AssembleVisitor.assemble(assemble_ctx, avm_ops),
        source_map={},
    )
