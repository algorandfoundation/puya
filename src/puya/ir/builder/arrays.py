from collections.abc import Callable, Sequence

import attrs

from puya.awst import (
    nodes as awst,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.ir import models as ir
from puya.ir.builder._utils import OpFactory, assign_temp, invoke_puya_lib_subroutine
from puya.ir.context import IRFunctionBuildContext
from puya.ir.types_ import IRType
from puya.parse import SourceLocation


@attrs.frozen(kw_only=True)
class ArrayIterator:
    array_length: ir.Value
    get_value_at_index: Callable[[ir.Value], ir.ValueProvider]


def check_supported_array(wtype: wtypes.WType, loc: SourceLocation) -> wtypes.WType:
    if not isinstance(wtype, wtypes.WArray) or wtype.element_type != wtypes.uint64_wtype:
        raise CodeError("only uint64 arrays supported", loc)
    # have this check because even if we expand support to other fixed length types
    # mutable types present another problem
    if not wtype.element_type.immutable:
        raise CodeError("Attempted iteration of an ARC4 array of mutable objects", loc)

    return wtype.element_type


def array_length(
    context: IRFunctionBuildContext,
    array: awst.Expression,
    loc: SourceLocation,
) -> ir.Register:
    slot = context.visitor.visit_and_materialise_single(array)
    return _array_length(context, slot, array.wtype, loc)


def _array_length(
    context: IRFunctionBuildContext,
    array: ir.Value,
    array_wtype: wtypes.WType,
    loc: SourceLocation,
) -> ir.Register:
    element_wtype = check_supported_array(array_wtype, loc)
    factory = OpFactory(context, loc)

    contents = factory.assign(
        ir.ReadSlot(slot=array, source_location=loc, type=IRType.bytes),
        "array_contents",
    )
    contents_length = factory.len(contents, "contents_length")
    return factory.div_floor(contents_length, _get_element_size(element_wtype), "array_length")


def read_array_index(
    context: IRFunctionBuildContext,
    array: awst.Expression,
    index_awst: awst.Expression,
    loc: SourceLocation,
) -> ir.Register:
    slot = context.visitor.visit_and_materialise_single(array)
    index = context.visitor.visit_and_materialise_single(index_awst)
    return _read_array_index(context, array_wtype=array.wtype, array=slot, index=index, loc=loc)


def _read_array_index(
    context: IRFunctionBuildContext,
    *,
    array_wtype: wtypes.WType,
    array: ir.Value,
    index: ir.Value,
    loc: SourceLocation,
) -> ir.Register:
    element_wtype = check_supported_array(array_wtype, loc)
    factory = OpFactory(context, loc)
    contents = factory.assign(
        ir.ReadSlot(slot=array, type=IRType.bytes, source_location=loc),
        "array_contents",
    )
    contents_index = factory.mul(index, _get_element_size(element_wtype), "contents_index")
    return factory.extract_uint64(contents, contents_index, "value")


def assign_array_index(
    context: IRFunctionBuildContext,
    array: awst.Expression,
    index_awst: awst.Expression,
    value_provider: ir.ValueProvider,
    loc: SourceLocation,
) -> Sequence[ir.Value]:
    element_wtype = check_supported_array(array.wtype, loc)
    factory = OpFactory(context, loc)
    slot = context.visitor.visit_and_materialise_single(array)
    index = context.visitor.visit_and_materialise_single(index_awst)
    contents = factory.assign(
        ir.ReadSlot(slot=slot, type=IRType.bytes, source_location=loc),
        "array_contents",
    )
    contents_index = factory.mul(index, _get_element_size(element_wtype), "contents_index")
    (value,) = context.visitor.materialise_value_provider(value_provider, "value")
    value_bytes = factory.itob(value, "value_bytes")
    contents = factory.replace(contents, contents_index, value_bytes, "updated_array_contents")
    context.block_builder.add(
        ir.WriteSlot(
            slot=slot,
            value=contents,
            source_location=loc,
        )
    )
    return (value,)


def extend_array(
    context: IRFunctionBuildContext,
    array: awst.Expression,
    items_awst: awst.Expression,
    loc: SourceLocation,
) -> None:
    check_supported_array(array.wtype, loc)
    factory = OpFactory(context, loc)
    slot = context.visitor.visit_and_materialise_single(array)
    contents = factory.assign(
        ir.ReadSlot(slot=slot, source_location=loc, type=IRType.bytes),
        "array_contents",
    )
    # TODO: check types

    # TODO: could this be consolidated with ARC4?
    def array_data(expr: awst.Expression) -> ir.Value:
        match expr.wtype:
            case wtypes.ARC4StaticArray():
                return context.visitor.visit_and_materialise_single(expr)
            case wtypes.WArray():
                slot = context.visitor.visit_and_materialise_single(expr)
                return read_slot(context, slot, loc)
            case wtypes.ARC4DynamicArray():
                expr_value = context.visitor.visit_and_materialise_single(expr)
                return factory.extract_to_end(expr_value, 2, "expr_value_trimmed")
            case wtypes.WTuple():
                values = context.visitor.visit_and_materialise(expr)
                data = factory.constant(b"")
                for item in values:
                    # TODO: handle non uint64
                    item_bytes = factory.itob(item, "item_bytes")
                    data = factory.concat(data, item_bytes, "data")
                return data
            case _:
                raise InternalError(f"Unexpected operand type for concatenation {expr.wtype}", loc)

    right_data = array_data(items_awst)
    contents = factory.concat(
        contents, right_data, "concat", error_message="max array length exceeded"
    )

    context.block_builder.add(
        ir.WriteSlot(
            slot=slot,
            value=contents,
            source_location=loc,
        )
    )


def build_for_in_array(
    context: IRFunctionBuildContext,
    array_wtype: wtypes.WArray,
    array_expr: awst.Expression,
    source_location: SourceLocation,
) -> ArrayIterator:
    check_supported_array(array_wtype, source_location)
    array = context.visitor.visit_and_materialise_single(array_expr)
    return ArrayIterator(
        array_length=_array_length(context, array, array_wtype, source_location),
        get_value_at_index=lambda index: _read_array_index(
            context,
            array=array,
            array_wtype=array_wtype,
            index=index,
            loc=source_location,
        ),
    )


# TODO: have a mem.py?


def new_slot(context: IRFunctionBuildContext, loc: SourceLocation) -> ir.Register:
    if context.allocation is None:
        raise CodeError("no available slots to allocate array", loc)
    return assign_temp(
        context,
        invoke_puya_lib_subroutine(
            context,
            full_name="_puya_lib.mem.new_slot",
            args=[ir.UInt64Constant(value=context.allocation.slot, source_location=None)],
            source_location=loc,
        ),
        temp_description="slot",
        source_location=loc,
    )


def write_slot(
    context: IRFunctionBuildContext, slot: ir.Value, value: ir.Value, loc: SourceLocation
) -> None:
    context.block_builder.add(
        ir.WriteSlot(
            slot=slot,
            value=value,
            source_location=loc,
        )
    )


def read_slot(context: IRFunctionBuildContext, slot: ir.Value, loc: SourceLocation) -> ir.Value:
    return assign_temp(
        context,
        ir.ReadSlot(slot=slot, source_location=loc, type=IRType.bytes),
        temp_description="array_contents",
        source_location=loc,
    )


def _get_element_size(wtype: wtypes.WType) -> int:
    assert wtype == wtypes.uint64_wtype, "TODO: other wtypes"
    return 8
