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
from puya.ir.types_ import ArrayType, EncodedTupleType
from puya.parse import SourceLocation, sequential_source_locations_merge


@attrs.frozen(kw_only=True)
class ArrayIterator:
    array_length: ir.Value
    get_value_at_index: Callable[[ir.Value], ir.ValueProvider]


def serialize_array_items(
    context: IRFunctionBuildContext, items: awst.Expression, array_type: ArrayType
) -> ir.Value:
    factory = OpFactory(context, items.source_location)
    match items.wtype:
        case wtypes.ARC4StaticArray():
            return context.visitor.visit_and_materialise_single(items)
        case wtypes.ARC4DynamicArray():
            expr_value = context.visitor.visit_and_materialise_single(items)
            return factory.extract_to_end(expr_value, 2, "expr_value_trimmed", ir_type=array_type)
        case wtypes.WArray():
            slot = context.visitor.visit_and_materialise_single(items)
            return read_slot(context, slot, items.source_location)
        case wtypes.WTuple():
            # TODO: where should this live?
            from puya.ir.builder.lower_array import encode_array_item

            values = context.visitor.visit_and_materialise(items)
            data = factory.constant(b"", ir_type=array_type)
            element_type = array_type.element
            expanded_element_types = EncodedTupleType.expand_types(element_type)
            num_reg_per_element = len(expanded_element_types)
            while len(values) >= num_reg_per_element:
                item_values = values[:num_reg_per_element]
                values = values[num_reg_per_element:]
                item: ir.Value | ir.ValueTuple
                try:
                    (item,) = item_values
                except ValueError:
                    item = ir.ValueTuple(
                        values=item_values,
                        source_location=sequential_source_locations_merge(
                            [i.source_location for i in item_values]
                        ),
                    )
                item_bytes = encode_array_item(context, item, element_type, item.source_location)
                data = factory.concat(data, item_bytes, "data", ir_type=array_type)
            if values:
                raise InternalError("unexpected number of elements", items.source_location)
            return data
        case _:
            raise InternalError(
                f"Unexpected operand type for concatenation {items.wtype}", items.source_location
            )


def extend_array(
    context: IRFunctionBuildContext,
    array: ir.Value,
    values: ir.Value,
    loc: SourceLocation,
) -> ir.Value:
    (result,) = context.visitor.materialise_value_provider(
        ir.ArrayExtend(
            array=array,
            values=values,
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

    array_slot = context.visitor.visit_and_materialise_single(array_expr)
    array_loc = array_expr.source_location
    array_contents = read_slot(context, array_slot, array_loc)
    array_length_vp = ir.ArrayLength(array=array_contents, source_location=array_loc)
    (array_length,) = context.visitor.materialise_value_provider(array_length_vp, "array_length")
    return ArrayIterator(
        array_length=array_length,
        get_value_at_index=lambda index: ir.ArrayReadIndex(
            array=read_slot(context, array_slot, source_location),
            index=index,
            source_location=source_location,
        ),
    )


def pop_array(
    context: IRFunctionBuildContext, array: ir.Value, loc: SourceLocation | None
) -> tuple[ir.Value, ir.ValueProvider]:
    pop = ir.ArrayPop(array=array, source_location=loc)
    array_type, *element_types = pop.types

    new_contents = context.new_register(context.next_tmp_name("new_contents"), array_type, loc)
    popped_items = [
        context.new_register(context.next_tmp_name(f"popped_item.{idx}"), item_type, loc)
        for idx, item_type in enumerate(element_types)
    ]
    assign_targets(
        context,
        source=pop,
        targets=[new_contents, *popped_items],
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
