from collections.abc import Callable

import attrs

from puya.awst import (
    nodes as awst,
    wtypes,
)
from puya.errors import InternalError
from puya.ir import models as ir
from puya.ir.builder._utils import OpFactory, assign_targets, mktemp
from puya.ir.builder.mem import read_slot
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import Value, ValueProvider
from puya.ir.types_ import (
    ArrayEncoding,
    DynamicArrayEncoding,
    EncodedType,
    FixedArrayEncoding,
    SlotType,
    get_type_arity,
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
    context: IRFunctionBuildContext, items: awst.Expression, array_encoding: ArrayEncoding
) -> ir.Value:
    factory = OpFactory(context, items.source_location)
    match array_encoding:
        case ArrayEncoding() if isinstance(items.wtype, wtypes.WTuple):
            try:
                (element_type,) = set(items.wtype.types)
            except ValueError:
                raise InternalError("expected homogenous tuple") from None
            tuple_size = len(items.wtype.types)
            if (
                isinstance(array_encoding, FixedArrayEncoding)
                and array_encoding.size != tuple_size
            ):
                raise InternalError("unexpected tuple size", items.source_location)
            element_ir_type, element_encoding = wtype_to_ir_type_and_encoding(
                element_type, items.source_location
            )
            num_values_per_item = get_type_arity(element_ir_type)
            encoded_array = factory.constant(b"", ir_type=EncodedType(array_encoding))
            item_values = context.visitor.visit_and_materialise(items, "items")
            # TODO: consolidate this and arc4.encode_n_items_as_arc4_items
            #       both take materialized tuples and encode and concat multiple values
            #       for concatenation
            for _ in range(tuple_size):
                encode_items = item_values[:num_values_per_item]
                item_values = item_values[num_values_per_item:]
                if type_has_encoding(element_ir_type, element_encoding):
                    (encoded_item,) = encode_items
                else:
                    encoded_item_vp = ir.ValueEncode(
                        values=encode_items,
                        value_type=element_ir_type,
                        encoding=element_encoding,
                        source_location=items.source_location,
                    )
                    encoded_item = factory.assign(encoded_item_vp, "encoded_item")
                concat = ir.ArrayConcat(
                    array=encoded_array,
                    array_encoding=array_encoding,
                    other=encoded_item,
                    source_location=items.source_location,
                )
                encoded_array = factory.assign(concat, "encoded_array")
            assert encoded_array is not None, "empty loop should not be possible"
            return encoded_array
        case DynamicArrayEncoding(length_header=length_header):
            expr_value = context.visitor.visit_and_materialise_single(items)
            if isinstance(expr_value.ir_type, SlotType):
                expr_value = read_slot(context, expr_value, items.source_location)
            if length_header:
                expr_value = factory.extract_to_end(
                    expr_value, 2, "expr_value_trimmed", ir_type=EncodedType(array_encoding)
                )
            return expr_value
        case FixedArrayEncoding() if not isinstance(items.wtype, wtypes.WTuple):
            value = context.visitor.visit_and_materialise_single(items)
            # TODO: this might not be needed once everything uses EncodedType
            array_type = EncodedType(array_encoding)
            if value.ir_type != array_type:
                target = mktemp(
                    context,
                    array_type,
                    description=f"reinterpret_{array_type.name}",
                    source_location=value.source_location,
                )
                assign_targets(
                    context,
                    source=value,
                    targets=[target],
                    assignment_location=value.source_location,
                )
                value = target
            return value
        case _:
            raise InternalError(
                f"Unexpected operand type for concatenation {items.wtype}", items.source_location
            )


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
    array_length = factory.assign(array_length_vp, "array_length")
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
                value=factory.assign(read_item, "read_item"),
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
