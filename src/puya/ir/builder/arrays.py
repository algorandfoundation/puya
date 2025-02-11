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
from puya.ir.types_ import ArrayType
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
    context: IRFunctionBuildContext, items: awst.Expression, array_type: ArrayType
) -> ir.Value:
    factory = OpFactory(context, items.source_location)
    match items.wtype:
        case wtypes.ARC4StaticArray():
            value = context.visitor.visit_and_materialise_single(items)
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
            return factory.extract_to_end(expr_value, 2, "expr_value_trimmed", ir_type=array_type)
        case wtypes.ReferenceArray():
            slot = context.visitor.visit_and_materialise_single(items)
            return read_slot(context, slot, items.source_location)
        case wtypes.WTuple() | wtypes.ARC4Tuple():
            array_encode = ir.ArrayEncode(
                values=context.visitor.visit_and_materialise(items),
                array_type=array_type,
                source_location=items.source_location,
            )
            return factory.assign(array_encode, "encoded")
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
