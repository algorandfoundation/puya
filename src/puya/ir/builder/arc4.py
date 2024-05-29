import typing
from collections.abc import Sequence

import attrs

from puya.arc4_util import (
    determine_arc4_tuple_head_size,
    get_arc4_fixed_bit_size,
    is_arc4_dynamic_size,
    is_arc4_static_size,
)
from puya.avm_type import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import (
    assert_value,
    assign,
    assign_intrinsic_op,
    invoke_puya_lib_subroutine,
    mktemp,
    reassign,
)
from puya.ir.builder.assignment import handle_assignment
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import (
    BytesConstant,
    Intrinsic,
    Register,
    UInt64Constant,
    Value,
    ValueProvider,
    ValueTuple,
)
from puya.ir.types_ import AVMBytesEncoding, IRType
from puya.ir.utils import format_tuple_index
from puya.parse import SourceLocation
from puya.utils import bits_to_bytes


@attrs.frozen(kw_only=True)
class ArrayIterator:
    context: IRFunctionBuildContext
    array_wtype: wtypes.ARC4StaticArray | wtypes.ARC4DynamicArray
    array: Value
    array_length: Value
    source_location: SourceLocation

    def get_value_at_index(self, index: Register) -> ValueProvider:
        return arc4_array_index(
            self.context,
            array_wtype=self.array_wtype,
            array=self.array,
            index=index,
            source_location=self.source_location,
            assert_bounds=False,  # iteration is always within bounds
        )


def decode_expr(context: IRFunctionBuildContext, expr: awst_nodes.ARC4Decode) -> ValueProvider:
    value = context.visitor.visit_and_materialise_single(expr.value)
    match expr.value.wtype:
        case wtypes.ARC4UIntN(n=scale) | wtypes.ARC4UFixedNxM(n=scale):
            if scale > 64:
                return value
            else:
                return Intrinsic(
                    op=AVMOp.btoi,
                    args=[value],
                    source_location=expr.source_location,
                )
        case wtypes.arc4_bool_wtype:
            return Intrinsic(
                op=AVMOp.getbit,
                args=[value, UInt64Constant(value=0, source_location=None)],
                source_location=expr.source_location,
            )
        case wtypes.arc4_string_wtype | wtypes.arc4_dynamic_bytes:
            return Intrinsic(
                op=AVMOp.extract,
                immediates=[2, 0],
                args=[value],
                source_location=expr.source_location,
            )
        case wtypes.ARC4Tuple() as arc4_tuple:
            return _visit_arc4_tuple_decode(
                context, arc4_tuple, value, source_location=expr.source_location
            )
        case _:
            raise InternalError(
                f"Unsupported wtype for ARC4Decode: {expr.value.wtype}",
                location=expr.source_location,
            )


def _visit_arc4_tuple_decode(
    context: IRFunctionBuildContext,
    wtype: wtypes.ARC4Tuple | wtypes.ARC4Struct,
    value: Value,
    source_location: SourceLocation,
) -> ValueProvider:
    items = list[Value]()

    for index in range(len(wtype.types)):
        item_value = _read_nth_item_of_arc4_heterogeneous_container(
            context,
            array_head_and_tail=value,
            tuple_type=wtype,
            index=index,
            source_location=source_location,
        )
        (item,) = assign(
            context,
            temp_description=f"item{index}",
            source=item_value,
            source_location=source_location,
        )

        items.append(item)
    return ValueTuple(source_location=source_location, values=items)


def encode_arc4_struct(
    context: IRFunctionBuildContext, expr: awst_nodes.NewStruct, wtype: wtypes.ARC4Struct
) -> ValueProvider:
    assert expr.wtype == wtype
    elements = [
        context.visitor.visit_and_materialise_single(expr.values[field_name])
        for field_name in expr.wtype.fields
    ]
    return _visit_arc4_tuple_encode(context, elements, wtype.types, expr.source_location)


def encode_expr(context: IRFunctionBuildContext, expr: awst_nodes.ARC4Encode) -> ValueProvider:
    match expr.wtype:
        case wtypes.arc4_bool_wtype:
            value = context.visitor.visit_and_materialise_single(expr.value)
            return encode_arc4_bool(value, expr.source_location)
        case wtypes.ARC4UIntN() | wtypes.ARC4UFixedNxM() as wt:
            value = context.visitor.visit_and_materialise_single(expr.value)
            num_bytes = wt.n // 8
            return _itob_fixed(context, value, num_bytes, expr.source_location)
        case wtypes.ARC4Tuple(types=item_types):
            elements = context.visitor.visit_and_materialise(expr.value)
            return _visit_arc4_tuple_encode(context, elements, item_types, expr.source_location)
        case wtypes.arc4_string_wtype | wtypes.arc4_dynamic_bytes:
            if isinstance(expr.value, awst_nodes.BytesConstant):
                ir_const = context.visitor.visit_expr(expr.value)
                if not isinstance(ir_const, BytesConstant):
                    raise InternalError("Expected BytesConstant", expr.value.source_location)
                prefix = len(ir_const.value).to_bytes(2, "big")
                value_prefixed = prefix + ir_const.value
                return BytesConstant(
                    source_location=expr.source_location,
                    value=value_prefixed,
                    encoding=ir_const.encoding,
                )
            value = context.visitor.visit_and_materialise_single(expr.value)
            (length,) = assign(
                context,
                temp_description="length",
                source_location=expr.source_location,
                source=Intrinsic(
                    op=AVMOp.len_,
                    args=[value],
                    source_location=expr.source_location,
                ),
            )
            return Intrinsic(
                op=AVMOp.concat,
                args=[_value_as_uint16(context, length), value],
                source_location=expr.source_location,
            )
        case wtypes.ARC4DynamicArray() | wtypes.ARC4StaticArray():
            raise InternalError(
                "ARC4ArrayEncode should be used instead of ARC4Encode for arrays",
                expr.source_location,
            )
        case _:
            raise InternalError(
                f"Unsupported wtype for ARC4Encode: {expr.wtype}",
                location=expr.source_location,
            )


def arc4_array_index(
    context: IRFunctionBuildContext,
    *,
    array_wtype: wtypes.ARC4StaticArray | wtypes.ARC4DynamicArray,
    array: Value,
    index: Value,
    source_location: SourceLocation,
    assert_bounds: bool = True,
) -> ValueProvider:
    factory = _OpFactory(context, source_location)
    array_length_vp = _get_arc4_array_length(array_wtype, array, source_location)
    array_head_and_tail_vp = _get_arc4_array_head_and_tail(array_wtype, array, source_location)
    array_head_and_tail = factory.assign(array_head_and_tail_vp, "array_head_and_tail")
    item_wtype = array_wtype.element_type

    if is_arc4_dynamic_size(item_wtype):
        inner_element_size = _maybe_get_inner_element_size(item_wtype)
        if inner_element_size is not None:
            if assert_bounds:
                _assert_index_in_bounds(context, index, array_length_vp, source_location)
            return _read_dynamic_item_using_length_from_arc4_container(
                context,
                array_head_and_tail=array_head_and_tail,
                inner_element_size=inner_element_size,
                index=index,
                source_location=source_location,
            )
        else:
            # no _assert_index_in_bounds here as end offset calculation implicitly checks
            return _read_dynamic_item_using_end_offset_from_arc4_container(
                context,
                array_length_vp=array_length_vp,
                array_head_and_tail=array_head_and_tail,
                index=index,
                source_location=source_location,
            )
    if item_wtype == wtypes.arc4_bool_wtype:
        if assert_bounds:
            # this catches the edge case of bit arrays that are not a multiple of 8
            # e.g. reading index 6 & 7 of an array that has a length of 6
            _assert_index_in_bounds(context, index, array_length_vp, source_location)
        return _read_nth_bool_from_arc4_container(
            context,
            data=array_head_and_tail,
            index=index,
            source_location=source_location,
        )
    else:
        item_bit_size = get_arc4_fixed_bit_size(item_wtype)
        # no _assert_index_in_bounds here as static items will error on read if past end of array
        return _read_static_item_from_arc4_container(
            data=array_head_and_tail,
            offset=factory.mul(index, item_bit_size // 8, "item_offset"),
            item_wtype=item_wtype,
            source_location=source_location,
        )


def _maybe_get_inner_element_size(item_wtype: wtypes.ARC4Type) -> int | None:
    match item_wtype:
        case wtypes.arc4_string_wtype:
            inner_static_element_type = wtypes.arc4_byte_type
        case wtypes.ARC4Array(element_type=inner_static_element_type) if is_arc4_static_size(
            inner_static_element_type
        ):
            pass
        case _:
            return None
    return get_arc4_fixed_bit_size(inner_static_element_type) // 8


def _read_dynamic_item_using_length_from_arc4_container(
    context: IRFunctionBuildContext,
    *,
    array_head_and_tail: Value,
    inner_element_size: int,
    index: Value,
    source_location: SourceLocation,
) -> ValueProvider:
    factory = _OpFactory(context, source_location)
    item_offset_offset = factory.mul(index, 2, "item_offset_offset")
    item_start_offset = factory.extract_uint16(
        array_head_and_tail, item_offset_offset, "item_offset"
    )
    item_length = factory.extract_uint16(array_head_and_tail, item_start_offset, "item_length")
    item_length_in_bytes = factory.mul(item_length, inner_element_size, "item_length_in_bytes")
    item_total_length = factory.add(item_length_in_bytes, 2, "item_head_tail_length")
    return Intrinsic(
        op=AVMOp.extract3,
        args=[array_head_and_tail, item_start_offset, item_total_length],
        source_location=source_location,
    )


def _read_dynamic_item_using_end_offset_from_arc4_container(
    context: IRFunctionBuildContext,
    *,
    array_length_vp: ValueProvider,
    array_head_and_tail: Value,
    index: Value,
    source_location: SourceLocation,
) -> ValueProvider:
    factory = _OpFactory(context, source_location)
    item_offset_offset = factory.mul(index, 2, "item_offset_offset")
    item_start_offset = factory.extract_uint16(
        array_head_and_tail, item_offset_offset, "item_offset"
    )

    array_length = factory.assign(array_length_vp, "array_length")
    next_item_index = factory.add(index, 1, "next_index")
    # three possible outcomes of this op will determine the end offset
    # next_item_index < array_length -> has_next is true, use next_item_offset
    # next_item_index == array_length -> has_next is false, use array_length
    # next_item_index > array_length -> op will fail, comment provides context to error
    has_next = factory.assign(
        Intrinsic(
            op=AVMOp.sub,
            args=[array_length, next_item_index],
            source_location=source_location,
            comment="on error: Index access is out of bounds",
        ),
        "has_next",
    )
    end_of_array = factory.len(array_head_and_tail, "end_of_array")
    next_item_offset_offset = factory.mul(next_item_index, 2, "next_item_offset_offset")
    # next_item_offset_offset will be past the array head when has_next is false, but this is ok as
    # the value will not be used. Additionally, next_item_offset_offset will always be a valid
    # offset in the overall array, because there will be at least 1 element (due to has_next
    # checking out of bounds) and this element will be dynamically sized,
    # which means it's data has at least one u16 in its header
    # e.g. reading here...   has at least one u16 ........
    #                    v                               v
    # ArrayHead(u16, u16) ArrayTail(DynamicItemHead(... u16, ...), ..., DynamicItemTail, ...)
    next_item_offset = factory.extract_uint16(
        array_head_and_tail, next_item_offset_offset, "next_item_offset"
    )

    item_end_offset = factory.select(end_of_array, next_item_offset, has_next, "end_offset")
    return Intrinsic(
        op=AVMOp.substring3,
        args=[array_head_and_tail, item_start_offset, item_end_offset],
        source_location=source_location,
    )


def arc4_tuple_index(
    context: IRFunctionBuildContext,
    base: Value,
    index: int,
    wtype: wtypes.ARC4Tuple | wtypes.ARC4Struct,
    source_location: SourceLocation,
) -> ValueProvider:
    return _read_nth_item_of_arc4_heterogeneous_container(
        context,
        array_head_and_tail=base,
        index=index,
        tuple_type=wtype,
        source_location=source_location,
    )


def _value_as_uint16(
    context: IRFunctionBuildContext, value: Value, source_location: SourceLocation | None = None
) -> Value:
    source_location = source_location or value.source_location
    (value_as_bytes,) = assign(
        context,
        source_location=source_location,
        source=Intrinsic(op=AVMOp.itob, args=[value], source_location=source_location),
        temp_description="value_as_bytes",
    )
    (value_as_uint16,) = assign(
        context,
        source_location=source_location,
        source=Intrinsic(
            op=AVMOp.extract,
            args=[value_as_bytes],
            immediates=[6, 2],
            source_location=source_location,
        ),
        temp_description="value_as_uint16",
    )
    return value_as_uint16


def _visit_arc4_tuple_encode(
    context: IRFunctionBuildContext,
    elements: Sequence[Value],
    tuple_items: Sequence[wtypes.ARC4Type],
    expr_loc: SourceLocation,
) -> ValueProvider:
    header_size = determine_arc4_tuple_head_size(tuple_items, round_end_result=True)

    (current_tail_offset,) = assign(
        context,
        temp_description="current_tail_offset",
        source=UInt64Constant(value=header_size // 8, source_location=expr_loc),
        source_location=expr_loc,
    )

    (encoded_tuple_buffer,) = assign(
        context,
        temp_description="encoded_tuple_buffer",
        source_location=expr_loc,
        source=BytesConstant(
            value=b"", encoding=AVMBytesEncoding.base16, source_location=expr_loc
        ),
    )

    def assign_buffer(source: ValueProvider) -> None:
        nonlocal encoded_tuple_buffer
        encoded_tuple_buffer = reassign(context, encoded_tuple_buffer, source, expr_loc)

    def append_to_buffer(item: Value) -> None:
        assign_buffer(
            Intrinsic(op=AVMOp.concat, args=[encoded_tuple_buffer, item], source_location=expr_loc)
        )

    for index, (element, el_wtype) in enumerate(zip(elements, tuple_items, strict=True)):
        if el_wtype == wtypes.arc4_bool_wtype:
            # Pack boolean
            before_header = determine_arc4_tuple_head_size(
                tuple_items[0:index], round_end_result=False
            )
            if before_header % 8 == 0:
                append_to_buffer(element)
            else:
                (is_true,) = assign(
                    context,
                    temp_description="is_true",
                    source=Intrinsic(
                        op=AVMOp.getbit,
                        args=[element, UInt64Constant(value=0, source_location=None)],
                        source_location=expr_loc,
                    ),
                    source_location=expr_loc,
                )

                assign_buffer(
                    _set_bit(
                        value=encoded_tuple_buffer,
                        index=before_header,
                        bit=is_true,
                        source_location=expr_loc,
                    )
                )
        elif not is_arc4_dynamic_size(el_wtype):
            # Append value
            append_to_buffer(element)
        else:
            # Append pointer
            offset_as_uint16b = _value_as_uint16(context, current_tail_offset)
            append_to_buffer(offset_as_uint16b)
            # Update Pointer
            (data_length,) = assign(
                context,
                temp_description="data_length",
                source=Intrinsic(op=AVMOp.len_, args=[element], source_location=expr_loc),
                source_location=expr_loc,
            )
            next_tail_offset = Intrinsic(
                op=AVMOp.add,
                args=[current_tail_offset, data_length],
                source_location=expr_loc,
            )
            current_tail_offset = reassign(
                context, current_tail_offset, next_tail_offset, expr_loc
            )

    for element, el_wtype in zip(elements, tuple_items, strict=True):
        if is_arc4_dynamic_size(el_wtype):
            append_to_buffer(element)
    return encoded_tuple_buffer


def _set_bit(
    *, value: Value, index: int, bit: Value, source_location: SourceLocation | None
) -> Intrinsic:
    index_const = UInt64Constant(value=index, source_location=source_location)
    return Intrinsic(
        op=AVMOp.setbit,
        args=[value, index_const, bit],
        types=[value.ir_type],
        source_location=source_location,
    )


def encode_arc4_array(context: IRFunctionBuildContext, expr: awst_nodes.NewArray) -> ValueProvider:
    if not isinstance(expr.wtype, wtypes.ARC4Array):
        raise InternalError("Expected ARC4 Array expression", expr.source_location)
    len_prefix = (
        len(expr.values).to_bytes(2, "big")
        if isinstance(expr.wtype, wtypes.ARC4DynamicArray)
        else b""
    )

    expr_loc = expr.source_location
    if not expr.values:
        return BytesConstant(
            value=len_prefix, encoding=AVMBytesEncoding.base16, source_location=expr_loc
        )

    elements = [context.visitor.visit_and_materialise_single(value) for value in expr.values]
    element_type = expr.wtype.element_type

    (array_data,) = assign(
        context,
        temp_description="array_data",
        source=BytesConstant(
            value=len_prefix, encoding=AVMBytesEncoding.base16, source_location=expr_loc
        ),
        source_location=expr_loc,
    )
    if element_type == wtypes.arc4_bool_wtype:
        for index, el in enumerate(elements):
            if index % 8 == 0:
                new_array_data_value = Intrinsic(
                    op=AVMOp.concat, args=[array_data, el], source_location=expr_loc
                )
            else:
                (is_true,) = assign(
                    context,
                    temp_description="is_true",
                    source=Intrinsic(
                        op=AVMOp.getbit,
                        args=[el, UInt64Constant(value=0, source_location=None)],
                        source_location=expr_loc,
                    ),
                    source_location=expr_loc,
                )
                new_array_data_value = _set_bit(
                    value=array_data,
                    index=index + 8 * len(len_prefix),
                    bit=is_true,
                    source_location=expr_loc,
                )
            array_data = reassign(context, array_data, new_array_data_value, expr_loc)

        return array_data

    if is_arc4_dynamic_size(element_type):
        (next_offset,) = assign(
            context,
            temp_description="next_offset",
            source=UInt64Constant(value=(2 * len(elements)), source_location=expr_loc),
            source_location=expr_loc,
        )
        for element in elements:
            updated_array_data = Intrinsic(
                op=AVMOp.concat,
                args=[array_data, _value_as_uint16(context, next_offset)],
                source_location=expr_loc,
            )
            array_data = reassign(context, array_data, updated_array_data, expr_loc)

            (element_length,) = assign(
                context,
                temp_description="element_length",
                source=Intrinsic(op=AVMOp.len_, args=[element], source_location=expr_loc),
                source_location=expr_loc,
            )
            next_offset_value = Intrinsic(
                op=AVMOp.add, args=[next_offset, element_length], source_location=expr_loc
            )
            next_offset = reassign(context, next_offset, next_offset_value, expr_loc)

    for element in elements:
        array_data_value = Intrinsic(
            op=AVMOp.concat, args=[array_data, element], source_location=expr_loc
        )
        array_data = reassign(context, array_data, array_data_value, expr_loc)
    return array_data


def _arc4_replace_struct_item(
    context: IRFunctionBuildContext,
    base_expr: awst_nodes.Expression,
    field_name: str,
    wtype: wtypes.ARC4Struct,
    value: ValueProvider,
    source_location: SourceLocation,
) -> Value:
    if not isinstance(wtype, wtypes.ARC4Struct):
        raise InternalError("Unsupported indexed assignment target", source_location)

    base = context.visitor.visit_and_materialise_single(base_expr)
    (value,) = assign(
        context,
        source_location=source_location,
        temp_description="assigned_value",
        source=value,
    )
    element_type = wtype.fields.get(field_name)
    if element_type is None:
        raise CodeError(f"Invalid arc4.Struct field name {field_name}", source_location)
    index_int = wtype.names.index(field_name)

    header_up_to_item = determine_arc4_tuple_head_size(
        wtype.types[0:index_int],
        round_end_result=element_type != wtypes.arc4_bool_wtype,
    )
    if element_type == wtypes.arc4_bool_wtype:
        # Use Set bit
        (is_true,) = assign_intrinsic_op(
            context,
            target="is_true",
            source_location=source_location,
            op=AVMOp.getbit,
            args=[value, 0],
        )
        (updated_data,) = assign_intrinsic_op(
            context,
            target="updated_data",
            source_location=source_location,
            op=AVMOp.setbit,
            args=(base, header_up_to_item, is_true),
            return_type=[base.ir_type],
        )
        return updated_data
    elif is_arc4_static_size(element_type):
        (updated_data,) = assign_intrinsic_op(
            context,
            target="updated_data",
            source_location=source_location,
            op=AVMOp.replace2,
            immediates=[header_up_to_item // 8],
            args=[base, value],
        )
        return updated_data
    else:
        dynamic_indices = [index for index, t in enumerate(wtype.types) if is_arc4_dynamic_size(t)]

        (item_offset,) = assign_intrinsic_op(
            context,
            target="item_offset",
            source_location=source_location,
            op=AVMOp.extract_uint16,
            args=[
                base,
                header_up_to_item // 8,
            ],
        )
        (data_up_to_item,) = assign_intrinsic_op(
            context,
            target="data_up_to_item",
            source_location=source_location,
            op=AVMOp.extract3,
            args=[
                base,
                0,
                item_offset,
            ],
        )
        proceeding_dynamic_indices = [i for i in dynamic_indices if i > index_int]

        if not proceeding_dynamic_indices:
            # This is the last dynamic type in the tuple
            # No need to update headers - just replace the data
            (updated_data,) = assign_intrinsic_op(
                context,
                target="updated_data",
                source_location=source_location,
                op=AVMOp.concat,
                args=[data_up_to_item, value],
            )
            return updated_data
        header_up_to_next_dynamic_item = determine_arc4_tuple_head_size(
            types=wtype.types[0 : proceeding_dynamic_indices[0]],
            round_end_result=True,
        )

        (next_item_offset,) = assign_intrinsic_op(
            context,
            target="next_item_offset",
            source_location=source_location,
            op=AVMOp.extract_uint16,
            args=[
                base,
                header_up_to_next_dynamic_item // 8,
            ],
        )
        (total_data_length,) = assign_intrinsic_op(
            context,
            target="total_data_length",
            source_location=source_location,
            op=AVMOp.len_,
            args=[
                base,
            ],
        )
        (data_beyond_item,) = assign_intrinsic_op(
            context,
            target="data_beyond_item",
            source_location=source_location,
            op=AVMOp.substring3,
            args=[
                base,
                next_item_offset,
                total_data_length,
            ],
        )
        (updated_data,) = assign_intrinsic_op(
            context,
            target="updated_data",
            source_location=source_location,
            op=AVMOp.concat,
            args=[
                data_up_to_item,
                value,
            ],
        )
        (updated_data,) = assign_intrinsic_op(
            context,
            target=updated_data,
            source_location=source_location,
            op=AVMOp.concat,
            args=[
                updated_data,
                data_beyond_item,
            ],
        )

        (new_value_length,) = assign_intrinsic_op(
            context,
            target="new_value_length",
            source_location=source_location,
            op=AVMOp.len_,
            args=[value],
        )
        (tail_cursor,) = assign_intrinsic_op(
            context,
            target="tail_cursor",
            source_location=source_location,
            op=AVMOp.add,
            args=[
                item_offset,
                new_value_length,
            ],
        )
        for dynamic_index in proceeding_dynamic_indices:
            header_up_to_dynamic_item = determine_arc4_tuple_head_size(
                types=wtype.types[0:dynamic_index],
                round_end_result=True,
            )

            (updated_header_bytes,) = assign_intrinsic_op(
                context,
                target="updated_header_bytes",
                source_location=source_location,
                op=AVMOp.itob,
                args=[
                    tail_cursor,
                ],
            )
            (updated_header_bytes,) = assign_intrinsic_op(
                context,
                target=updated_header_bytes,
                source_location=source_location,
                op=AVMOp.substring,
                immediates=[6, 8],
                args=[updated_header_bytes],
            )

            (updated_data,) = assign_intrinsic_op(
                context,
                target=updated_data,
                source_location=source_location,
                op=AVMOp.replace2,
                immediates=[header_up_to_dynamic_item // 8],
                args=[
                    updated_data,
                    updated_header_bytes,
                ],
            )
            if dynamic_index == proceeding_dynamic_indices[-1]:
                break
            (dynamic_item_length,) = assign_intrinsic_op(
                context,
                target="dynamic_item_length",
                source_location=source_location,
                op=AVMOp.extract_uint16,
                args=[updated_data, tail_cursor],
            )
            (tail_cursor,) = assign_intrinsic_op(
                context,
                target=tail_cursor,
                source_location=source_location,
                op=AVMOp.add,
                args=[tail_cursor, dynamic_item_length],
            )
            (tail_cursor,) = assign_intrinsic_op(
                context,
                target=tail_cursor,
                source_location=source_location,
                op=AVMOp.add,
                args=[tail_cursor, 2],
            )
        return updated_data


def _read_nth_item_of_arc4_heterogeneous_container(
    context: IRFunctionBuildContext,
    *,
    array_head_and_tail: Value,
    tuple_type: wtypes.ARC4Tuple | wtypes.ARC4Struct,
    index: int,
    source_location: SourceLocation,
) -> ValueProvider:
    tuple_item_types = tuple_type.types

    item_wtype = tuple_item_types[index]
    head_up_to_item = determine_arc4_tuple_head_size(
        tuple_item_types[:index], round_end_result=False
    )
    if item_wtype == wtypes.arc4_bool_wtype:
        return _read_nth_bool_from_arc4_container(
            context,
            data=array_head_and_tail,
            index=UInt64Constant(
                value=head_up_to_item,
                source_location=source_location,
            ),
            source_location=source_location,
        )
    head_offset = UInt64Constant(
        value=bits_to_bytes(head_up_to_item), source_location=source_location
    )
    if is_arc4_dynamic_size(item_wtype):
        (item_start_offset,) = assign_intrinsic_op(
            context,
            target="item_start_offset",
            op=AVMOp.extract_uint16,
            args=[array_head_and_tail, head_offset],
            source_location=source_location,
        )

        next_index = index + 1
        for tuple_item_index, tuple_item_type in enumerate(
            tuple_item_types[next_index:], start=next_index
        ):
            if is_arc4_dynamic_size(tuple_item_type):
                head_up_to_next_dynamic_item = determine_arc4_tuple_head_size(
                    tuple_item_types[:tuple_item_index], round_end_result=False
                )
                next_dynamic_head_offset = UInt64Constant(
                    value=bits_to_bytes(head_up_to_next_dynamic_item),
                    source_location=source_location,
                )
                (item_end_offset,) = assign_intrinsic_op(
                    context,
                    target="item_end_offset",
                    op=AVMOp.extract_uint16,
                    args=[array_head_and_tail, next_dynamic_head_offset],
                    source_location=source_location,
                )
                break
        else:
            (item_end_offset,) = assign_intrinsic_op(
                context,
                target="item_end_offset",
                op=AVMOp.len_,
                args=[array_head_and_tail],
                source_location=source_location,
            )
        return Intrinsic(
            op=AVMOp.substring3,
            args=[array_head_and_tail, item_start_offset, item_end_offset],
            source_location=source_location,
        )
    else:
        return _read_static_item_from_arc4_container(
            data=array_head_and_tail,
            offset=head_offset,
            item_wtype=item_wtype,
            source_location=source_location,
        )


def _read_nth_bool_from_arc4_container(
    context: IRFunctionBuildContext,
    *,
    data: Value,
    index: Value,
    source_location: SourceLocation,
) -> ValueProvider:
    # index is the bit position
    (is_true,) = assign(
        context,
        temp_description="is_true",
        source=Intrinsic(op=AVMOp.getbit, args=[data, index], source_location=source_location),
        source_location=source_location,
    )
    return encode_arc4_bool(is_true, source_location)


def _read_static_item_from_arc4_container(
    *,
    data: Value,
    offset: Value,
    item_wtype: wtypes.ARC4Type,
    source_location: SourceLocation,
) -> ValueProvider:
    item_bit_size = get_arc4_fixed_bit_size(item_wtype)
    item_length = UInt64Constant(value=item_bit_size // 8, source_location=source_location)
    return Intrinsic(
        op=AVMOp.extract3,
        args=[data, offset, item_length],
        source_location=source_location,
        comment="on error: Index access is out of bounds",
    )


def build_for_in_array(
    context: IRFunctionBuildContext,
    array_wtype: wtypes.ARC4DynamicArray | wtypes.ARC4StaticArray,
    array_expr: awst_nodes.Expression,
    source_location: SourceLocation,
) -> ArrayIterator:
    array = context.visitor.visit_and_materialise_single(array_expr)
    length_vp = _get_arc4_array_length(array_wtype, array, source_location)
    (array_length,) = assign(
        context,
        length_vp,
        temp_description="array_length",
        source_location=source_location,
    )
    return ArrayIterator(
        context=context,
        array=array,
        array_length=array_length,
        array_wtype=array_wtype,
        source_location=source_location,
    )


def _get_arc4_array_tail_data_and_item_count(
    context: IRFunctionBuildContext, expr: awst_nodes.Expression, source_location: SourceLocation
) -> tuple[Value, Value]:
    """
    For ARC4 containers (dynamic array, static array) will return the tail data and item count
    For native tuples will return the tuple items packed into the equivalent static array
    of tail data and item count
    """
    match expr:
        case awst_nodes.Expression(
            wtype=wtypes.ARC4DynamicArray() | wtypes.ARC4StaticArray() as arr_wtype
        ):
            array = context.visitor.visit_and_materialise_single(expr)
            (array_length,) = assign(
                context,
                _get_arc4_array_length(arr_wtype, array, source_location),
                temp_description="array_length",
                source_location=source_location,
            )
            (array_head_and_tail,) = assign(
                context,
                _get_arc4_array_head_and_tail(arr_wtype, array, source_location),
                temp_description="array_head_and_tail",
                source_location=source_location,
            )
            array_tail = _get_arc4_array_tail(
                context,
                element_wtype=arr_wtype.element_type,
                array_head_and_tail=array_head_and_tail,
                array_length=array_length,
                source_location=source_location,
            )
            return array_tail, array_length
        case awst_nodes.TupleExpression() as tuple_expr:
            if not all(isinstance(t, wtypes.ARC4Type) for t in tuple_expr.wtype.types):
                raise InternalError("Expected tuple to contain only ARC4 types", source_location)

            values = context.visitor.visit_and_materialise(tuple_expr)
            tuple_length = UInt64Constant(
                value=len(values),
                source_location=source_location,
            )
            (data,) = assign(
                context,
                temp_description="data",
                source_location=source_location,
                source=BytesConstant(
                    value=b"",
                    source_location=source_location,
                    encoding=AVMBytesEncoding.base16,
                ),
            )
            for val in values:
                (data,) = assign_intrinsic_op(
                    context,
                    target=data,
                    source_location=source_location,
                    op=AVMOp.concat,
                    args=[data, val],
                )
            return data, tuple_length
        case awst_nodes.Expression(wtype=wtypes.arc4_string_wtype) as str_expr:
            str_value = context.visitor.visit_and_materialise_single(str_expr)
            (array_length,) = assign_intrinsic_op(
                context,
                target="array_length",
                op=AVMOp.extract_uint16,
                args=[
                    str_value,
                    0,
                ],
                source_location=source_location,
            )
            (data,) = assign_intrinsic_op(
                context,
                target="data",
                op=AVMOp.extract,
                immediates=[2, 0],
                args=[
                    str_value,
                ],
                source_location=source_location,
            )
            return data, array_length
        case _:
            raise InternalError(f"Unsupported array type: {expr.wtype}")


def _get_arc4_array_as_dynamic_array(
    context: IRFunctionBuildContext, expr: awst_nodes.Expression
) -> Value:
    match expr:
        case awst_nodes.Expression(wtype=wtypes.ARC4DynamicArray()):
            return context.visitor.visit_and_materialise_single(expr)
        case awst_nodes.Expression(wtype=wtypes.ARC4StaticArray(array_size=array_size)):
            array_length = BytesConstant(
                value=array_size.to_bytes(2, "big"),
                encoding=AVMBytesEncoding.base16,
                source_location=expr.source_location,
            )
            static_array = context.visitor.visit_and_materialise_single(expr)
            (as_dynamic,) = assign_intrinsic_op(
                context,
                target="as_dynamic",
                op=AVMOp.concat,
                source_location=expr.source_location,
                args=[array_length, static_array],
            )
            return as_dynamic
        case _:
            raise InternalError(f"Unsupported array type: {expr.wtype}")


def _itob_fixed(
    context: IRFunctionBuildContext, value: Value, num_bytes: int, source_location: SourceLocation
) -> ValueProvider:
    if value.atype == AVMType.uint64:
        (val_as_bytes,) = assign(
            context,
            temp_description="val_as_bytes",
            source=Intrinsic(op=AVMOp.itob, args=[value], source_location=source_location),
            source_location=source_location,
        )

        if num_bytes == 8:
            return val_as_bytes
        if num_bytes < 8:
            return Intrinsic(
                op=AVMOp.extract,
                immediates=[8 - num_bytes, num_bytes],
                args=[val_as_bytes],
                source_location=source_location,
            )
        bytes_value: Value = val_as_bytes
    else:
        (len_,) = assign(
            context,
            temp_description="len_",
            source=Intrinsic(op=AVMOp.len_, args=[value], source_location=source_location),
            source_location=source_location,
        )
        (no_overflow,) = assign(
            context,
            temp_description="no_overflow",
            source=Intrinsic(
                op=AVMOp.lte,
                args=[
                    len_,
                    UInt64Constant(value=num_bytes, source_location=source_location),
                ],
                source_location=source_location,
            ),
            source_location=source_location,
        )

        context.block_builder.add(
            Intrinsic(
                op=AVMOp.assert_,
                args=[no_overflow],
                source_location=source_location,
                comment="overflow",
            )
        )
        bytes_value = value

    (b_zeros,) = assign(
        context,
        temp_description="b_zeros",
        source=Intrinsic(
            op=AVMOp.bzero,
            args=[UInt64Constant(value=num_bytes, source_location=source_location)],
            source_location=source_location,
        ),
        source_location=source_location,
    )
    return Intrinsic(
        op=AVMOp.bitwise_or_bytes,
        args=[bytes_value, b_zeros],
        source_location=source_location,
    )


def handle_arc4_assign(
    context: IRFunctionBuildContext,
    target: awst_nodes.Expression,
    value: ValueProvider,
    source_location: SourceLocation,
) -> Value:
    match target:
        case awst_nodes.VarExpression(name=var_name, source_location=var_loc):
            (register,) = assign(
                context,
                source=value,
                names=[(var_name, var_loc)],
                source_location=source_location,
            )
            return register
        case awst_nodes.AppAccountStateExpression() | awst_nodes.AppStateExpression():
            (result,) = handle_assignment(
                context, target, value=value, assignment_location=source_location
            )
            return result

        case awst_nodes.IndexExpression(
            base=awst_nodes.Expression(
                wtype=wtypes.ARC4DynamicArray() | wtypes.ARC4StaticArray() as array_wtype
            ) as base_expr,
            index=index_value,
        ):
            return handle_arc4_assign(
                context,
                target=base_expr,
                value=_arc4_replace_array_item(
                    context,
                    base_expr=base_expr,
                    index_value_expr=index_value,
                    wtype=array_wtype,
                    value=value,
                    source_location=source_location,
                ),
                source_location=source_location,
            )
        case awst_nodes.FieldExpression(
            base=awst_nodes.Expression(wtype=wtypes.ARC4Struct() as struct_wtype) as base_expr,
            name=field_name,
        ):
            return handle_arc4_assign(
                context,
                target=base_expr,
                value=_arc4_replace_struct_item(
                    context,
                    base_expr=base_expr,
                    field_name=field_name,
                    wtype=struct_wtype,
                    value=value,
                    source_location=source_location,
                ),
                source_location=source_location,
            )
        case awst_nodes.TupleItemExpression(
            base=awst_nodes.VarExpression(wtype=wtypes.WTuple(types=items_types)) as base_expr,
            index=index_value,
        ) if not items_types[index_value].immutable:
            (result,) = assign(
                context=context,
                names=[(format_tuple_index(base_expr.name, index_value), source_location)],
                source=value,
                source_location=source_location,
            )

            return result
        case _:
            raise CodeError("Not a valid assignment target", source_location)


def _arc4_replace_array_item(
    context: IRFunctionBuildContext,
    *,
    base_expr: awst_nodes.Expression,
    index_value_expr: awst_nodes.Expression,
    wtype: wtypes.ARC4DynamicArray | wtypes.ARC4StaticArray,
    value: ValueProvider,
    source_location: SourceLocation,
) -> Value:
    base = context.visitor.visit_and_materialise_single(base_expr)

    (value,) = assign(
        context,
        source_location=source_location,
        temp_description="assigned_value",
        source=value,
    )

    index = context.visitor.visit_and_materialise_single(index_value_expr)

    if is_arc4_dynamic_size(wtype.element_type):
        if isinstance(wtype, wtypes.ARC4DynamicArray):
            (updated_value,) = assign(
                context,
                temp_description="updated_value",
                source=invoke_puya_lib_subroutine(
                    context,
                    method_name="dynamic_array_replace_variable_size",
                    module_name="algopy_lib_arc4",
                    source_location=source_location,
                    args=[
                        base,
                        value,
                        index,
                    ],
                ),
                source_location=source_location,
            )
            return updated_value
        else:
            (updated_value,) = assign(
                context,
                temp_description="updated_value",
                source=invoke_puya_lib_subroutine(
                    context,
                    method_name="static_array_replace_variable_size",
                    module_name="algopy_lib_arc4",
                    source_location=source_location,
                    args=[
                        base,
                        value,
                        index,
                        UInt64Constant(value=wtype.array_size, source_location=source_location),
                    ],
                ),
                source_location=source_location,
            )
            return updated_value

    array_length = (
        UInt64Constant(value=wtype.array_size, source_location=source_location)
        if isinstance(wtype, wtypes.ARC4StaticArray)
        else Intrinsic(
            source_location=source_location,
            op=AVMOp.extract_uint16,
            args=[base, UInt64Constant(value=0, source_location=source_location)],
        )
    )
    _assert_index_in_bounds(
        context,
        index,
        array_length,
        source_location,
    )

    element_size = get_arc4_fixed_bit_size(wtype.element_type)
    dynamic_offset = 0 if isinstance(wtype, wtypes.ARC4StaticArray) else 2
    if element_size == 1:
        dynamic_offset *= 8
        offset_per_item = element_size
    else:
        offset_per_item = element_size // 8

    if isinstance(index_value_expr, awst_nodes.IntegerConstant):
        write_offset: Value = UInt64Constant(
            value=index_value_expr.value * offset_per_item + dynamic_offset,
            source_location=source_location,
        )
    else:
        (write_offset,) = assign_intrinsic_op(
            context,
            target="write_offset",
            op=AVMOp.mul,
            source_location=source_location,
            args=[index, offset_per_item],
        )
        if dynamic_offset:
            assert isinstance(write_offset, Register)
            (write_offset,) = assign_intrinsic_op(
                context,
                target=write_offset,
                op=AVMOp.add,
                source_location=source_location,
                args=[write_offset, dynamic_offset],
            )

    if element_size == 1:
        (is_true,) = assign_intrinsic_op(
            context,
            target="is_true",
            source_location=source_location,
            op=AVMOp.getbit,
            args=[value, 0],
        )
        (updated_target,) = assign_intrinsic_op(
            context,
            target="updated_target",
            source_location=source_location,
            op=AVMOp.setbit,
            args=(base, write_offset, is_true),
            return_type=[base.ir_type],
        )
    else:
        (updated_target,) = assign_intrinsic_op(
            context,
            target="updated_target",
            source_location=source_location,
            op=AVMOp.replace3,
            args=[
                base,
                write_offset,
                value,
            ],
        )
    return updated_target


def _concat_dynamic_array_fixed_size(
    context: IRFunctionBuildContext,
    *,
    left: awst_nodes.Expression,
    right: awst_nodes.Expression,
    source_location: SourceLocation,
    byte_size: int,
) -> Value:
    def array_data(expr: awst_nodes.Expression) -> Value:
        match expr.wtype:
            case wtypes.ARC4StaticArray():
                return context.visitor.visit_and_materialise_single(expr)
            case wtypes.ARC4DynamicArray() | wtypes.arc4_string_wtype:
                expr_value = context.visitor.visit_and_materialise_single(expr)
                (expr_value_trimmed,) = assign_intrinsic_op(
                    context,
                    source_location=source_location,
                    op=AVMOp.extract,
                    immediates=[2, 0],
                    args=[expr_value],
                    target="expr_value_trimmed",
                )
                return expr_value_trimmed
            case wtypes.WTuple():
                values = context.visitor.visit_and_materialise(expr)
                (data,) = assign(
                    context,
                    temp_description="data",
                    source_location=source_location,
                    source=BytesConstant(
                        value=b"",
                        source_location=source_location,
                        encoding=AVMBytesEncoding.base16,
                    ),
                )
                for val in values:
                    (data,) = assign_intrinsic_op(
                        context,
                        target=data,
                        source_location=source_location,
                        op=AVMOp.concat,
                        args=[data, val],
                    )
                return data
            case _:
                raise InternalError(
                    f"Unexpected operand type for concatenation {expr.wtype}", source_location
                )

    left_data = array_data(left)
    right_data = array_data(right)
    (concatenated,) = assign_intrinsic_op(
        context,
        source_location=source_location,
        op=AVMOp.concat,
        args=[left_data, right_data],
        target="concatenated",
    )
    if byte_size == 1:
        (len_,) = assign_intrinsic_op(
            context,
            source_location=source_location,
            op=AVMOp.len_,
            args=[concatenated],
            target="len_",
        )
    else:
        (byte_len,) = assign_intrinsic_op(
            context,
            source_location=source_location,
            op=AVMOp.len_,
            args=[concatenated],
            target="byte_len",
        )
        (len_,) = assign_intrinsic_op(
            context,
            source_location=source_location,
            op=AVMOp.div_floor,
            args=[byte_len, byte_size],
            target="len_",
        )

    (len_bytes,) = assign_intrinsic_op(
        context,
        source_location=source_location,
        op=AVMOp.itob,
        args=[len_],
        target="len_bytes",
    )
    (len_16_bit,) = assign_intrinsic_op(
        context,
        source_location=source_location,
        op=AVMOp.extract,
        args=[len_bytes],
        immediates=[6, 0],
        target="len_16_bit",
    )
    (concat_result,) = assign_intrinsic_op(
        context,
        source_location=source_location,
        op=AVMOp.concat,
        args=[len_16_bit, concatenated],
        target="concat_result",
    )
    return concat_result


def concat_values(
    context: IRFunctionBuildContext,
    left: awst_nodes.Expression,
    right: awst_nodes.Expression,
    source_location: SourceLocation,
) -> Value:
    match (left, right):
        case (
            awst_nodes.Expression(wtype=wtypes.ARC4Array(element_type=left_element_type)),
            awst_nodes.Expression(wtype=wtypes.ARC4Array(element_type=right_element_type)),
        ) if left_element_type == right_element_type:
            if left_element_type == wtypes.arc4_bool_wtype:
                method_name = "dynamic_array_concat_bits"
                additional_args: list[Value] = [
                    UInt64Constant(value=1, source_location=source_location)
                ]
            elif is_arc4_dynamic_size(left_element_type):
                method_name = "dynamic_array_concat_variable_size"
                additional_args = []
            else:
                element_size = get_arc4_fixed_bit_size(left_element_type)
                return _concat_dynamic_array_fixed_size(
                    context,
                    left=left,
                    right=right,
                    source_location=source_location,
                    byte_size=element_size // 8,
                )
            (r_data, r_length) = _get_arc4_array_tail_data_and_item_count(
                context, right, source_location
            )
            l_value = _get_arc4_array_as_dynamic_array(context, left)
            (concat_result,) = assign(
                context,
                temp_description="concat_result",
                source_location=source_location,
                source=invoke_puya_lib_subroutine(
                    context,
                    method_name=method_name,
                    source_location=source_location,
                    module_name="algopy_lib_arc4",
                    args=[l_value, r_data, r_length, *additional_args],
                ),
            )
            return concat_result
        case (
            awst_nodes.Expression(wtype=wtypes.ARC4Array(element_type=left_element_type)),
            awst_nodes.Expression(wtype=wtypes.WTuple(types=tuple_types)),
        ) if all(t == left_element_type for t in tuple_types):
            if left_element_type == wtypes.arc4_bool_wtype:
                method_name = "dynamic_array_concat_bits"
                additional_args = [UInt64Constant(value=0, source_location=source_location)]
            elif is_arc4_dynamic_size(left_element_type):
                method_name = "dynamic_array_concat_variable_size"
                additional_args = []
            else:
                element_size = get_arc4_fixed_bit_size(left_element_type)
                return _concat_dynamic_array_fixed_size(
                    context,
                    left=left,
                    right=right,
                    source_location=source_location,
                    byte_size=element_size // 8,
                )
            (r_data, r_length) = _get_arc4_array_tail_data_and_item_count(
                context, right, source_location
            )
            l_value = _get_arc4_array_as_dynamic_array(context, left)
            (concat_result,) = assign(
                context,
                temp_description="concat_result",
                source_location=source_location,
                source=invoke_puya_lib_subroutine(
                    context,
                    method_name=method_name,
                    module_name="algopy_lib_arc4",
                    source_location=source_location,
                    args=[l_value, r_data, r_length, *additional_args],
                ),
            )
            return concat_result
        case (
            awst_nodes.Expression(wtype=wtypes.arc4_string_wtype),
            awst_nodes.Expression(wtype=wtypes.arc4_string_wtype),
        ):
            return _concat_dynamic_array_fixed_size(
                context, left=left, right=right, source_location=source_location, byte_size=1
            )
        case _:
            raise CodeError(
                f"Unexpected operand types or order for concatenation: "
                f"{left.wtype} and {right.wtype}",
                source_location,
            )


def pop_arc4_array(
    context: IRFunctionBuildContext,
    expr: awst_nodes.ArrayPop,
    array_wtype: wtypes.ARC4DynamicArray,
) -> ValueProvider:
    source_location = expr.source_location
    popped = mktemp(context, IRType.bytes, source_location, description="popped")
    data = mktemp(context, IRType.bytes, source_location, description="data")
    base = context.visitor.visit_and_materialise_single(expr.base)
    if array_wtype.element_type == wtypes.arc4_bool_wtype:
        method_name = "dynamic_array_pop_bit"
        args: list[Value] = [base]
    elif is_arc4_dynamic_size(array_wtype.element_type):
        method_name = "dynamic_array_pop_variable_size"
        args = [base]
    else:
        fixed_size = get_arc4_fixed_bit_size(array_wtype.element_type)
        method_name = "dynamic_array_pop_fixed_size"
        args = [
            base,
            UInt64Constant(
                value=fixed_size // 8,
                source_location=source_location,
            ),
        ]

    (popped, data) = assign(
        context,
        source_location=source_location,
        names=[(popped.name, None), (data.name, None)],
        source=invoke_puya_lib_subroutine(
            context,
            method_name=method_name,
            args=args,
            source_location=source_location,
            module_name="algopy_lib_arc4",
        ),
    )

    handle_arc4_assign(context, target=expr.base, value=data, source_location=source_location)

    return popped


def encode_arc4_bool(bit: Value, source_location: SourceLocation) -> ValueProvider:
    value = BytesConstant(
        value=0x00.to_bytes(1, "big"),
        source_location=source_location,
        encoding=AVMBytesEncoding.base16,
    )
    return _set_bit(value=value, index=0, bit=bit, source_location=source_location)


def _assert_index_in_bounds(
    context: IRFunctionBuildContext,
    index: Value,
    length: ValueProvider,
    source_location: SourceLocation,
) -> None:
    if isinstance(index, UInt64Constant) and isinstance(length, UInt64Constant):
        if 0 <= index.value < length.value:
            return
        raise CodeError("Index access is out of bounds", source_location)

    (array_length,) = assign(
        context,
        source_location=source_location,
        temp_description="array_length",
        source=length,
    )

    (index_is_in_bounds,) = assign(
        context,
        source_location=source_location,
        temp_description="index_is_in_bounds",
        source=Intrinsic(
            op=AVMOp.lt,
            args=[index, array_length],
            source_location=source_location,
        ),
    )

    assert_value(
        context,
        index_is_in_bounds,
        source_location=source_location,
        comment="Index access is out of bounds",
    )


def _get_arc4_array_length(
    wtype: wtypes.ARC4StaticArray | wtypes.ARC4DynamicArray,
    array: Value,
    source_location: SourceLocation,
) -> ValueProvider:
    match wtype:
        case wtypes.ARC4StaticArray(array_size=array_size):
            return UInt64Constant(value=array_size, source_location=source_location)
        case wtypes.ARC4DynamicArray():
            return Intrinsic(
                op=AVMOp.extract_uint16,
                args=[
                    array,
                    UInt64Constant(value=0, source_location=source_location),
                ],
                source_location=source_location,
            )
        case _:
            typing.assert_never(wtype)


def _get_arc4_array_head_and_tail(
    wtype: wtypes.ARC4StaticArray | wtypes.ARC4DynamicArray,
    array: Value,
    source_location: SourceLocation,
) -> ValueProvider:
    match wtype:
        case wtypes.ARC4StaticArray():
            return array
        case wtypes.ARC4DynamicArray():
            return Intrinsic(
                op=AVMOp.extract,
                args=[array],
                immediates=[2, 0],
                source_location=source_location,
            )
        case _:
            typing.assert_never(wtype)


def _get_arc4_array_tail(
    context: IRFunctionBuildContext,
    *,
    element_wtype: wtypes.ARC4Type,
    array_length: Value,
    array_head_and_tail: Value,
    source_location: SourceLocation,
) -> Value:
    if not is_arc4_dynamic_size(element_wtype):
        # no header for static sized elements
        return array_head_and_tail

    # special case to use extract with immediate length of 0 where possible
    # TODO: have an IR pseudo op, extract_to_end that handles this for non constant values?
    if isinstance(array_length, UInt64Constant) and array_length.value <= 127:
        (data,) = assign_intrinsic_op(
            context,
            target="data",
            op=AVMOp.extract,
            immediates=[array_length.value * 2, 0],
            args=[array_head_and_tail],
            source_location=source_location,
        )
        return data
    (start_of_tail,) = assign_intrinsic_op(
        context,
        target="start_of_tail",
        op=AVMOp.mul,
        args=[array_length, 2],
        source_location=source_location,
    )
    (total_length,) = assign_intrinsic_op(
        context,
        target="total_length",
        op=AVMOp.len_,
        args=[array_head_and_tail],
        source_location=source_location,
    )
    (data,) = assign_intrinsic_op(
        context,
        target="data",
        op=AVMOp.substring3,
        args=[array_head_and_tail, start_of_tail, total_length],
        source_location=source_location,
    )
    return data


@attrs.frozen
class _OpFactory:
    context: IRFunctionBuildContext
    source_location: SourceLocation

    def assign(self, value: ValueProvider, temp_desc: str) -> Register:
        (register,) = assign(
            self.context,
            value,
            temp_description=temp_desc,
            source_location=self.source_location,
        )
        return register

    def add(self, a: Value, b: Value | int, temp_desc: str) -> Register:
        (result,) = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.add,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def mul(self, a: Value, b: Value | int, temp_desc: str) -> Register:
        (result,) = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.mul,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def len(self, value: Value, temp_desc: str) -> Register:
        (result,) = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.len_,
            args=[value],
            source_location=self.source_location,
        )
        return result

    def eq(self, a: Value, b: Value, temp_desc: str) -> Register:
        (result,) = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.eq,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def select(self, false: Value, true: Value, condition: Value, temp_desc: str) -> Register:
        (result,) = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.select,
            args=[false, true, condition],
            return_type=(true.ir_type,),
            source_location=self.source_location,
        )
        return result

    def extract_uint16(self, a: Value, b: Value, temp_desc: str) -> Register:
        (result,) = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.extract_uint16,
            args=[a, b],
            source_location=self.source_location,
        )
        return result
