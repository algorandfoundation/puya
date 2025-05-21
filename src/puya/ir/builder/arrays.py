from collections.abc import Callable

import attrs

from puya.awst import (
    nodes as awst,
    wtypes,
)
from puya.errors import InternalError
from puya.ir import models as ir
from puya.ir.builder._utils import OpFactory, assign_targets
from puya.ir.builder.mem import read_slot
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import Value, ValueProvider
from puya.ir.types_ import (
    ArrayEncoding,
    DynamicArrayEncoding,
    EncodedType,
    Encoding,
    SlotType,
    TupleEncoding,
    ir_type_to_ir_types,
    type_has_encoding,
    wtype_to_ir_type_and_encoding,
)
from puya.parse import SourceLocation, sequential_source_locations_merge


@attrs.frozen(kw_only=True)
class ArrayIterator:
    array_length: ir.Value
    get_value_at_index: Callable[[ir.Value], ir.ValueProvider]


def get_array_length(
    context: IRFunctionBuildContext,
    array_encoding: ArrayEncoding,
    array: Value,
    source_location: SourceLocation,
) -> ValueProvider:
    if isinstance(array.ir_type, SlotType):
        array = read_slot(context, array, array.source_location)
    return ir.ArrayLength(
        array=array, array_encoding=array_encoding, source_location=source_location
    )


def get_array_encoded_items(
    context: IRFunctionBuildContext, items: awst.Expression, element_encoding: Encoding
) -> ir.Value:
    """Returns a single encoded value representing an concatenation of all encoded items"""
    from puya.ir.builder import arc4

    loc = items.source_location
    if element_encoding.is_dynamic:
        raise InternalError("TODO: support dynamic elements", loc)

    factory = OpFactory(context, loc)

    array_vp = context.visitor.visit_expr(items)
    value_ir_type, _ = wtype_to_ir_type_and_encoding(items.wtype, loc)
    # read slot contents
    if isinstance(value_ir_type, SlotType):
        slot = factory.materialise_single(array_vp, "slot")
        array_vp = read_slot(context, slot, loc)
        value_ir_type = value_ir_type.contents
    # handle already encoded array types
    if isinstance(value_ir_type, EncodedType) and isinstance(
        value_ir_type.encoding, ArrayEncoding | TupleEncoding
    ):
        array = factory.materialise_single(array_vp, "array")
        if (
            isinstance(value_ir_type.encoding, DynamicArrayEncoding)
            and value_ir_type.encoding.length_header
        ):
            array = factory.extract_to_end(array, 2, "array_trimmed")
        return array
    else:
        assert isinstance(
            items.wtype, wtypes.WTuple
        ), f"assuming this is a tuple of elements to concat: {items.wtype}"
        encoded = arc4.encode_value_provider(
            context,
            array_vp,
            value_ir_type,
            DynamicArrayEncoding(element_encoding, length_header=False),
            loc,
        )
        return factory.materialise_single(encoded, "encoded")


def concat_arrays(
    context: IRFunctionBuildContext,
    array: ir.Value,
    other: ir.Value,
    loc: SourceLocation,
) -> ir.Value:
    (result,) = context.visitor.materialise_value_provider(
        ir.ArrayConcat(
            array=array,
            other=other,
            source_location=loc,
        ),
        "extended",
    )
    return result


def build_for_in_array(
    context: IRFunctionBuildContext,
    array_expr: awst.Expression,
    source_location: SourceLocation,
) -> ArrayIterator:
    # TODO: separate array ops from slot ops
    factory = OpFactory(context, source_location)

    array_slot = context.visitor.visit_and_materialise_single(array_expr)
    array_loc = array_expr.source_location
    array_contents = read_slot(context, array_slot, array_loc)
    array_length_vp = ir.ArrayLength(array=array_contents, source_location=array_loc)
    array_length = factory.materialise_single(array_length_vp, "array_length")
    array_wtype = array_expr.wtype
    assert isinstance(
        array_wtype, wtypes.StackArray | wtypes.ReferenceArray | wtypes.ARC4Array
    ), "expected array type"
    element_wtype = array_wtype.element_type

    element_ir_type, element_encoding = wtype_to_ir_type_and_encoding(
        element_wtype, source_location
    )

    def _read_and_decode(index: ir.Value) -> ir.ValueProvider:
        read_item = ir.ArrayReadIndex(
            array=read_slot(context, array_slot, source_location),
            index=index,
            source_location=source_location,
        )
        if type_has_encoding(element_ir_type, element_encoding):
            return read_item
        else:
            return ir.ValueDecode(
                value=factory.materialise_single(read_item, "read_item"),
                encoding=element_encoding,
                decoded_type=element_ir_type,
                source_location=source_location,
            )

    return ArrayIterator(
        array_length=array_length,
        get_value_at_index=_read_and_decode,
    )


def pop_array(
    context: IRFunctionBuildContext,
    element_wtype: wtypes.WType,
    array: ir.Value,
    loc: SourceLocation,
) -> tuple[ir.Value, ir.ValueProvider]:
    pop = ir.ArrayPop(array=array, source_location=loc)
    new_contents, encoded_item = context.visitor.materialise_value_provider(pop, "pop")
    element_ir_type, element_encoding = wtype_to_ir_type_and_encoding(element_wtype, loc)
    popped_items_vp = ir.ValueDecode(
        value=encoded_item,
        encoding=element_encoding,
        decoded_type=element_ir_type,
        source_location=loc,
    )

    popped_items = [
        context.new_register(context.next_tmp_name(f"popped_item.{idx}"), item_type, loc)
        for idx, item_type in enumerate(ir_type_to_ir_types(element_ir_type))
    ]
    assign_targets(
        context,
        source=popped_items_vp,
        targets=popped_items,
        assignment_location=loc,
    )
    popped_item: ir.ValueProvider
    try:
        (popped_item,) = popped_items
    except ValueError:
        popped_item = ir.ValueTuple(
            values=popped_items,
            source_location=sequential_source_locations_merge(
                [i.source_location for i in popped_items]
            ),
        )
    return new_contents, popped_item
