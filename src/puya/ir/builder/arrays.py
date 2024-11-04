from collections.abc import Callable

import attrs

from puya.awst import (
    nodes as awst,
    wtypes,
)
from puya.errors import InternalError
from puya.ir import models as ir
from puya.ir.builder._utils import OpFactory, assign_targets
from puya.ir.builder.mem import read_slot, write_slot
from puya.ir.context import IRFunctionBuildContext
from puya.ir.types_ import ArrayType, SlotType, wtype_to_ir_type
from puya.parse import SourceLocation


@attrs.frozen(kw_only=True)
class ArrayIterator:
    array_length: ir.Value
    get_value_at_index: Callable[[ir.Value], ir.ValueProvider]


def array_length(
    _context: IRFunctionBuildContext,
    array: ir.Value,
    loc: SourceLocation,
) -> ir.ArrayLength:
    return ir.ArrayLength(array=array, source_location=loc)


def read_array_index(
    _context: IRFunctionBuildContext,
    array: ir.Value,
    index: ir.Value,
    loc: SourceLocation,
) -> ir.ArrayReadIndex:
    return ir.ArrayReadIndex(
        array=array,
        index=index,
        source_location=loc,
    )


def assign_array_index(
    _context: IRFunctionBuildContext,
    array: ir.Value,
    index: ir.Value,
    value: ir.Value,
    loc: SourceLocation,
) -> ir.ArrayWriteIndex:
    return ir.ArrayWriteIndex(
        array=array,
        index=index,
        value=value,
        source_location=loc,
    )


def extend_array(
    context: IRFunctionBuildContext,
    # TODO: separate array manipulation from memory ops
    array: awst.Expression,
    items_awst: awst.Expression,
    loc: SourceLocation,
) -> None:
    slot_type = wtype_to_ir_type(array.wtype)
    assert isinstance(slot_type, SlotType)
    array_type = slot_type.contents
    assert isinstance(array_type, ArrayType)
    factory = OpFactory(context, loc)
    slot = context.visitor.visit_and_materialise_single(array)

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
                data = factory.constant(b"", ir_type=array_type)
                for item in values:
                    # TODO: handle non uint64
                    item_bytes = factory.itob(item, "item_bytes", return_type=array_type)
                    data = factory.concat(data, item_bytes, "data", return_type=array_type)
                return data
            case _:
                raise InternalError(f"Unexpected operand type for concatenation {expr.wtype}", loc)

    # evaluate RHS before reading slot, incase RHS modifies slot
    to_extend = array_data(items_awst)
    contents = read_slot(context, slot, loc)
    (contents,) = context.visitor.materialise_value_provider(
        ir.ArrayExtend(
            array=contents,
            values=to_extend,
            source_location=loc,
        ),
        "extended_contents",
    )
    write_slot(context, slot, contents, loc)


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
) -> tuple[ir.Register, ir.Register]:
    pop = ir.ArrayPop(array=array, source_location=loc)
    array_type, element_type = pop.types

    new_contents = context.new_register(context.next_tmp_name("new_contents"), array_type, loc)
    popped_item = context.new_register(context.next_tmp_name("popped_item"), element_type, loc)
    assign_targets(
        context,
        source=pop,
        targets=[new_contents, popped_item],
        assignment_location=loc,
    )
    return new_contents, popped_item
