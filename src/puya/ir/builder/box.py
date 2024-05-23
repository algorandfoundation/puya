from collections.abc import Sequence

from puya.arc4_util import get_arc4_fixed_bit_size
from puya.avm_type import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError
from puya.ir import models as ops
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import assert_value, assign, assign_intrinsic_op
from puya.ir.context import IRFunctionBuildContext
from puya.ir.types_ import wtype_to_ir_type
from puya.parse import SourceLocation


def _box_get(
    context: IRFunctionBuildContext,
    box: awst_nodes.BoxValueExpression,
    source_location: SourceLocation,
) -> tuple[ops.Register, ops.Register]:
    box_key = context.visitor.visit_and_materialise_single(box.key)
    (box_value, box_exists) = assign(
        context=context,
        temp_description=["box_value", "box_exists"],
        source_location=source_location,
        source=ops.Intrinsic(
            op=AVMOp.box_get,
            args=[box_key],
            source_location=source_location,
        ),
    )
    if wtype_to_ir_type(box).avm_type == AVMType.uint64:
        (box_value,) = assign_intrinsic_op(
            op=AVMOp.btoi,
            target="box_value_uint64",
            source_location=source_location,
            context=context,
            args=[box_value],
        )
    return box_value, box_exists


def visit_box_state_exists(
    context: IRFunctionBuildContext, expr: awst_nodes.StateExists
) -> ops.ValueProvider:
    box_key = context.visitor.visit_and_materialise_single(expr.field.key)
    (box_len, box_exists) = assign(
        temp_description=["box_len", "box_exists"],
        source_location=expr.source_location,
        source=ops.Intrinsic(
            op=AVMOp.box_len,
            args=[box_key],
            source_location=expr.source_location,
        ),
        context=context,
    )
    return box_exists


def visit_box_value(
    context: IRFunctionBuildContext, expr: awst_nodes.BoxValueExpression
) -> ops.ValueProvider:
    (box_value, box_exists) = _box_get(context, expr, expr.source_location)

    assert_value(
        context,
        box_exists,
        comment="Box must exist",
        source_location=expr.source_location,
    )
    return box_value


def handle_box_assign(
    *,
    context: IRFunctionBuildContext,
    box: awst_nodes.BoxValueExpression,
    value: ops.ValueProvider,
    assignment_location: SourceLocation,
) -> Sequence[ops.Value]:
    box_key = context.visitor.visit_and_materialise_single(box.key)
    source = context.visitor.materialise_value_provider(value, description="new_box_value")
    if len(source) != 1:
        raise CodeError(
            "Tuples cannot be assigned to a box without being encoded in for example, "
            "an ARC4Tuple type",
            assignment_location,
        )
    (new_box_value,) = source
    if box.wtype == wtypes.uint64_wtype:
        (new_box_value,) = assign(
            context=context,
            source=ops.Intrinsic(
                op=AVMOp.itob,
                args=[new_box_value],
                source_location=assignment_location,
            ),
            source_location=assignment_location,
            temp_description="new_box_value",
        )
    if not _is_fixed_byte_size(box.wtype):
        assign(
            context=context,
            source=ops.Intrinsic(
                op=AVMOp.box_del,
                source_location=assignment_location,
                args=[box_key],
            ),
            source_location=assignment_location,
            temp_description="box_del_res",
        )
    context.block_builder.add(
        ops.Intrinsic(
            op=AVMOp.box_put,
            source_location=assignment_location,
            args=[box_key, new_box_value],
        )
    )
    return source


def _is_fixed_byte_size(wtype: wtypes.WType) -> bool:
    if wtype == wtypes.uint64_wtype:
        return True
    if isinstance(wtype, wtypes.ARC4Type):
        return get_arc4_fixed_bit_size(wtype) is not None
    return False
