from puya.awst import nodes as awst_nodes
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import OpFactory, assign_intrinsic_op, assign_temp
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import Intrinsic, UInt64Constant, Value, ValueProvider
from puya.ir.types_ import PrimitiveIRType
from puya.parse import SourceLocation


def visit_bytes_slice_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.SliceExpression
) -> ValueProvider:
    base = context.visitor.visit_and_materialise_single(expr.base)
    if expr.begin_index is None and expr.end_index is None:
        return base

    if expr.begin_index is not None:
        start_value = context.visitor.visit_and_materialise_single(expr.begin_index)
    else:
        start_value = UInt64Constant(value=0, source_location=expr.source_location)

    if expr.end_index is not None:
        stop_value = context.visitor.visit_and_materialise_single(expr.end_index)
        return Intrinsic(
            op=AVMOp.substring3,
            args=[base, start_value, stop_value],
            source_location=expr.source_location,
        )
    elif isinstance(start_value, UInt64Constant):
        # we can use extract without computing the length when the start index is
        # a constant value and the end index is None (ie end of array)
        return Intrinsic(
            op=AVMOp.extract,
            immediates=[start_value.value, 0],
            args=[base],
            source_location=expr.source_location,
        )
    else:
        base_length = assign_temp(
            context,
            source_location=expr.source_location,
            source=Intrinsic(op=AVMOp.len_, args=[base], source_location=expr.source_location),
            temp_description="base_length",
        )
        return Intrinsic(
            op=AVMOp.substring3,
            args=[base, start_value, base_length],
            source_location=expr.source_location,
        )


def visit_bytes_intersection_slice_expression(
    context: IRFunctionBuildContext, expr: awst_nodes.IntersectionSliceExpression
) -> ValueProvider:
    base = context.visitor.visit_and_materialise_single(expr.base)
    length = assign_intrinsic_op(
        context,
        target="length",
        op=AVMOp.len_,
        args=[base],
        source_location=expr.source_location,
    )
    start = (
        UInt64Constant(value=0, source_location=expr.source_location)
        if expr.begin_index is None
        else get_bounded_value(
            context,
            value=expr.begin_index,
            length=length,
            source_location=expr.source_location,
        )
    )
    end = (
        length
        if expr.end_index is None
        else get_bounded_value(
            context,
            value=expr.end_index,
            length=length,
            source_location=expr.source_location,
        )
    )
    if _is_end_check_required(start_index=expr.begin_index, end_index=expr.end_index):
        end_before_start = assign_intrinsic_op(
            context,
            target="end_before_start",
            op=AVMOp.lt,
            args=[end, start],
            source_location=expr.source_location,
        )
        factory = OpFactory(context, expr.source_location)
        end = factory.select(
            false=end,
            true=start,
            condition=end_before_start,
            temp_desc="end",
            ir_type=PrimitiveIRType.uint64,
        )
    return Intrinsic(
        op=AVMOp.substring3,
        args=[base, start, end],
        source_location=expr.source_location,
    )


def _is_end_check_required(
    *,
    start_index: awst_nodes.Expression | int | None,
    end_index: awst_nodes.Expression | int | None,
) -> bool:
    """
    Returns false if we can statically determine the start is less than or equal to the end (or
    will be once it is bounded between 0 <= index <= len(target) )
    """
    if start_index is None or end_index is None:
        return False

    match start_index:
        case awst_nodes.IntegerConstant(value=start_static):
            pass
        case int(start_static):
            pass
        case _:
            # Start is not statically known so a check is required
            return True

    match end_index:
        case awst_nodes.IntegerConstant(value=end_static):
            pass
        case int(end_static):
            pass
        case _:
            # End is not statically known, a check is required if start is not 0
            return start_static > 0
    # If start is negative
    if start_static < 0:
        # a check is required if end is more_negative, or not negative at all
        return end_static < start_static or end_static > 0
    # If end is negative (and start is not), a check is required
    if end_static < 0:
        return True
    # A check is required if start is greater than end
    return start_static > end_static


def get_bounded_value(
    context: IRFunctionBuildContext,
    *,
    value: awst_nodes.Expression | int,
    length: Value,
    source_location: SourceLocation,
) -> Value:
    if isinstance(value, int) and value < 0:
        # abs(value) >= length
        is_out_of_bounds = assign_intrinsic_op(
            context,
            target="is_out_of_bounds",
            op=AVMOp.gte,
            args=[abs(value), length],
            source_location=source_location,
        )
        # length if is_out_of_bounds else abs(value)
        factory = OpFactory(context, source_location)
        bounded_offset = factory.select(
            false=abs(value),
            true=length,
            condition=is_out_of_bounds,
            temp_desc="bounded_offset",
            ir_type=PrimitiveIRType.uint64,
        )
        # length - bounded_offset
        bounded_index = assign_intrinsic_op(
            context,
            op=AVMOp.sub,
            args=[length, bounded_offset],
            target="bounded_index",
            source_location=source_location,
        )
        return bounded_index
    if isinstance(value, int):
        unbounded: Value = UInt64Constant(value=value, source_location=source_location)
    else:
        unbounded = context.visitor.visit_and_materialise_single(value)

    # unbounded > length
    is_out_of_bounds = assign_intrinsic_op(
        context,
        target="is_out_of_bounds",
        op=AVMOp.gte,
        args=[unbounded, length],
        source_location=source_location,
    )
    # length if is_out_of_bounds else unbounded
    factory = OpFactory(context, source_location)
    bounded_index = factory.select(
        false=unbounded,
        true=length,
        condition=is_out_of_bounds,
        temp_desc="bounded_index",
        ir_type=PrimitiveIRType.uint64,
    )
    return bounded_index
