from collections.abc import Callable

import attrs

from puya.awst import (
    nodes as awst,
    wtypes,
)
from puya.errors import InternalError
from puya.ir import models as ir
from puya.ir.arc4_types import effective_array_encoding
from puya.ir.builder._utils import OpFactory, assign_targets, mktemp
from puya.ir.builder.mem import read_slot
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import Value, ValueProvider
from puya.ir.types_ import ArrayEncoding, EncodedType, wtype_to_encoded_ir_type, wtype_to_ir_types
from puya.parse import SourceLocation, sequential_source_locations_merge


@attrs.frozen(kw_only=True)
class ArrayIterator:
    array_length: ir.Value
    get_value_at_index: Callable[[ir.Value], ir.ValueProvider]


def get_array_length(
    context: IRFunctionBuildContext,
    wtype: wtypes.StackArray | wtypes.ReferenceArray,
    array: Value,
    source_location: SourceLocation,
) -> ValueProvider:
    from puya.ir.builder.arc4 import get_arc4_array_length

    if isinstance(wtype, wtypes.ReferenceArray):
        array_contents = read_slot(context, array, array.source_location)
        return ir.ArrayLength(array=array_contents, source_location=source_location)
    array_encoding = effective_array_encoding(wtype, source_location)
    return get_arc4_array_length(array_encoding, array, source_location)


def get_array_encoded_items(
    context: IRFunctionBuildContext, items: awst.Expression, array_encoding: ArrayEncoding
) -> ir.Value:
    factory = OpFactory(context, items.source_location)
    match items.wtype:
        case wtypes.ARC4StaticArray():
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
        case wtypes.ARC4DynamicArray() | wtypes.StackArray():
            expr_value = context.visitor.visit_and_materialise_single(items)
            # TODO: can omit extract here and just return the correct EncodedType
            #       i.e an array encoding with length header
            return factory.extract_to_end(
                expr_value, 2, "expr_value_trimmed", ir_type=EncodedType(array_encoding)
            )
        case wtypes.ARC4Tuple():
            expr_value = context.visitor.visit_and_materialise_single(items)
            assert expr_value.ir_type == EncodedType(
                array_encoding
            ), "expected tuple items to match array encoding"
            return expr_value
        case wtypes.ReferenceArray():
            slot = context.visitor.visit_and_materialise_single(items)
            return read_slot(context, slot, items.source_location)
        case wtypes.WTuple(types=types):
            try:
                (element_type,) = set(types)
            except ValueError:
                raise InternalError("expected homogenous tuple") from None
            element_ir_types = wtype_to_ir_types(element_type, items.source_location)
            element_encoding = wtype_to_encoded_ir_type(element_type)
            num_values_per_item = len(element_ir_types)
            encoded_array = None
            item_values = context.visitor.visit_and_materialise(items, "items")
            for _ in range(len(types)):
                encode_items = item_values[:num_values_per_item]
                item_values = item_values[num_values_per_item:]
                encoded_item_vp = ir.ValueEncode(
                    values=encode_items,
                    value_types=element_ir_types,
                    encoded_type=element_encoding,
                    source_location=items.source_location,
                )
                encoded_item = factory.assign(encoded_item_vp, "encoded_item")
                if encoded_array is None:
                    encoded_array = encoded_item
                else:
                    encoded_array = ir.ArrayConcat(
                        array=encoded_array,
                        other=encoded_item,
                        source_location=items.source_location,
                    )
            assert encoded_array is not None, "empty loop should not be possible"
            return encoded_array
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

    array_ir_type = wtype_to_encoded_ir_type(array_wtype)
    array_encoding = array_ir_type.encoding

    element_wtype = array_wtype.element_type
    element_ir_types = wtype_to_ir_types(element_wtype, source_location)

    def _read_and_decode(index: ir.Value) -> ir.ValueProvider:
        assert isinstance(array_encoding, ArrayEncoding), "expected array encoding"

        read_item = ir.ArrayReadIndex(
            array=read_slot(context, array_slot, source_location),
            index=index,
            source_location=source_location,
        )
        return ir.ValueDecode(
            value=factory.assign(read_item, "read_item"),
            encoding=array_encoding.element,
            types=element_ir_types,
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
    element_types = wtype_to_ir_types(element_wtype, loc)
    popped_items_vp = ir.ValueDecode(
        value=encoded_item,
        encoding=pop.array_encoding.element,
        types=element_types,
        source_location=loc,
    )

    popped_items = [
        context.new_register(context.next_tmp_name(f"popped_item.{idx}"), item_type, loc)
        for idx, item_type in enumerate(element_types)
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
