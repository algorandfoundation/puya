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
    assign_targets,
    assign_temp,
    invoke_puya_lib_subroutine,
    mktemp,
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
    array_wtype: wtypes.ARC4Array
    array: Value
    array_length: Value
    source_location: SourceLocation

    def get_value_at_index(self, index: Value) -> ValueProvider:
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
                types=(IRType.bool,),
            )
        case wtypes.ARC4DynamicArray(element_type=wtypes.ARC4UIntN(n=8)):
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
            return _encode_arc4_bool(context, value, expr.source_location)
        case wtypes.ARC4UIntN(n=bits):
            value = context.visitor.visit_and_materialise_single(expr.value)
            num_bytes = bits // 8
            return _itob_fixed(context, value, num_bytes, expr.source_location)
        case wtypes.ARC4Tuple(types=item_types):
            elements = context.visitor.visit_and_materialise(expr.value)
            return _visit_arc4_tuple_encode(context, elements, item_types, expr.source_location)
        case wtypes.ARC4DynamicArray(element_type=wtypes.ARC4UIntN(n=8)):
            value = context.visitor.visit_and_materialise_single(expr.value)
            factory = _OpFactory(context, expr.source_location)
            length = factory.len(value, "length")
            length_uint16 = factory.as_u16_bytes(length, "length_uint16")
            return factory.concat(length_uint16, value, "encoded_value")
        case wtypes.ARC4DynamicArray() | wtypes.ARC4StaticArray():
            raise InternalError(
                "NewArray should be used instead of ARC4Encode for arrays",
                expr.source_location,
            )
        case _:
            raise InternalError(
                f"Unsupported wtype for ARC4Encode: {expr.wtype}",
                location=expr.source_location,
            )


def encode_arc4_array(context: IRFunctionBuildContext, expr: awst_nodes.NewArray) -> ValueProvider:
    if not isinstance(expr.wtype, wtypes.ARC4Array):
        raise InternalError("Expected ARC4 Array expression", expr.source_location)
    len_prefix = (
        len(expr.values).to_bytes(2, "big")
        if isinstance(expr.wtype, wtypes.ARC4DynamicArray)
        else b""
    )

    factory = _OpFactory(context, expr.source_location)
    elements = [context.visitor.visit_and_materialise_single(value) for value in expr.values]
    element_type = expr.wtype.element_type

    if element_type == wtypes.arc4_bool_wtype:
        array_head_and_tail = factory.constant(b"")
        for index, el in enumerate(elements):
            if index % 8 == 0:
                array_head_and_tail = factory.concat(
                    array_head_and_tail, el, temp_desc="array_head_and_tail"
                )
            else:
                is_true = factory.get_bit(el, 0, "is_true")

                array_head_and_tail = factory.set_bit(
                    value=array_head_and_tail,
                    index=index,
                    bit=is_true,
                    temp_desc="array_head_and_tail",
                )
    else:
        array_head_and_tail = _arc4_items_as_arc4_tuple(
            context, element_type, elements, expr.source_location
        )

    return factory.concat(len_prefix, array_head_and_tail, "array_data")


def arc4_array_index(
    context: IRFunctionBuildContext,
    *,
    array_wtype: wtypes.ARC4Array,
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


def build_for_in_array(
    context: IRFunctionBuildContext,
    array_wtype: wtypes.ARC4Array,
    array_expr: awst_nodes.Expression,
    source_location: SourceLocation,
) -> ArrayIterator:
    if not array_wtype.element_type.immutable:
        raise InternalError(
            "Attempted iteration of an ARC4 array of mutable objects", source_location
        )
    array = context.visitor.visit_and_materialise_single(array_expr)
    length_vp = _get_arc4_array_length(array_wtype, array, source_location)
    array_length = assign_temp(
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


def handle_arc4_assign(
    context: IRFunctionBuildContext,
    target: awst_nodes.Expression,
    value: ValueProvider,
    source_location: SourceLocation,
    *,
    is_mutation: bool = False,
) -> Value:
    result: Value
    match target:
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
                is_mutation=True,
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
                is_mutation=True,
            )
        case awst_nodes.TupleItemExpression(
            base=awst_nodes.Expression(wtype=wtypes.ARC4Tuple() as tuple_wtype) as base_expr,
            index=index_value,
        ):
            return handle_arc4_assign(
                context,
                target=base_expr,
                value=_arc4_replace_tuple_item(
                    context,
                    base_expr=base_expr,
                    index_int=index_value,
                    wtype=tuple_wtype,
                    value=value,
                    source_location=source_location,
                ),
                source_location=source_location,
                is_mutation=True,
            )
        # this function is sometimes invoked outside an assignment expr/stmt, which
        # is how a non l-value expression can be possible
        # TODO: refactor this so that this special case is handled where it originates
        case awst_nodes.TupleItemExpression(
            wtype=item_wtype,
        ) as ti_expr if not item_wtype.immutable:
            result = assign(
                context=context,
                name=_get_tuple_var_name(ti_expr),
                source=value,
                register_location=ti_expr.source_location,
                assignment_location=source_location,
            )
            return result
        case _:
            (result,) = handle_assignment(
                context,
                target,
                value=value,
                assignment_location=source_location,
                is_mutation=is_mutation,
            )
            return result


def _get_tuple_var_name(expr: awst_nodes.TupleItemExpression) -> str:
    if isinstance(expr.base, awst_nodes.TupleItemExpression):
        return format_tuple_index(_get_tuple_var_name(expr.base), expr.index)
    if isinstance(expr.base, awst_nodes.VarExpression):
        return format_tuple_index(expr.base.name, expr.index)
    raise CodeError("Invalid assignment target", expr.base.source_location)


def concat_values(
    context: IRFunctionBuildContext,
    left_expr: awst_nodes.Expression,
    right_expr: awst_nodes.Expression,
    source_location: SourceLocation,
) -> Value:
    factory = _OpFactory(context, source_location)
    # check left is a valid ARC4 array to concat with
    left_wtype = left_expr.wtype
    if not isinstance(left_wtype, wtypes.ARC4DynamicArray):
        raise InternalError("Expected left expression to be a dynamic ARC4 array", source_location)
    left_element_type = left_wtype.element_type

    # check right is a valid type to concat
    right_wtype = right_expr.wtype
    if isinstance(right_wtype, wtypes.ARC4Array):
        right_element_type = right_wtype.element_type
    elif isinstance(right_wtype, wtypes.WTuple) and all(
        t == left_element_type for t in right_wtype.types
    ):
        right_element_type = left_element_type
    else:
        right_element_type = None

    if left_element_type != right_element_type:
        raise CodeError(
            f"Unexpected operand types or order for concatenation:"
            f" {left_wtype} and {right_wtype}",
            source_location,
        )

    if left_element_type == wtypes.arc4_bool_wtype:
        left = context.visitor.visit_and_materialise_single(left_expr)
        (r_data, r_length) = _get_arc4_array_tail_data_and_item_count(
            context, right_expr, source_location
        )
        is_packed = UInt64Constant(
            value=1 if isinstance(right_wtype, wtypes.ARC4Array) else 0,
            source_location=source_location,
        )
        return factory.assign(
            invoke_puya_lib_subroutine(
                context,
                method_name="dynamic_array_concat_bits",
                source_location=source_location,
                module_name="algopy_lib_arc4",
                args=[
                    left,
                    r_data,
                    r_length,
                    is_packed,
                ],
            ),
            "concat_result",
        )
    if is_arc4_static_size(left_element_type):
        element_size = get_arc4_fixed_bit_size(left_element_type)
        return _concat_dynamic_array_fixed_size(
            context,
            left=left_expr,
            right=right_expr,
            source_location=source_location,
            byte_size=element_size // 8,
        )
    if _is_byte_length_header(left_element_type):
        left = context.visitor.visit_and_materialise_single(left_expr)
        (r_data, r_length) = _get_arc4_array_tail_data_and_item_count(
            context, right_expr, source_location
        )
        return factory.assign(
            invoke_puya_lib_subroutine(
                context,
                method_name="dynamic_array_concat_byte_length_head",
                source_location=source_location,
                module_name="algopy_lib_arc4",
                args=[
                    left,
                    r_data,
                    r_length,
                ],
            ),
            "concat_result",
        )
    if is_arc4_dynamic_size(left_element_type):
        assert isinstance(left_wtype, wtypes.ARC4DynamicArray)
        left = context.visitor.visit_and_materialise_single(left_expr)
        if isinstance(right_wtype, wtypes.WTuple):
            right_values = context.visitor.visit_and_materialise(right_expr)
            r_count_vp: ValueProvider = UInt64Constant(
                value=len(right_wtype.types), source_location=source_location
            )
            r_head_and_tail_vp: ValueProvider = _arc4_items_as_arc4_tuple(
                context, left_element_type, right_values, source_location
            )
        elif isinstance(right_wtype, wtypes.ARC4Array):
            right = context.visitor.visit_and_materialise_single(right_expr)
            r_count_vp = _get_arc4_array_length(right_wtype, right, source_location)
            r_head_and_tail_vp = _get_arc4_array_head_and_tail(right_wtype, right, source_location)
        else:
            raise InternalError("Expected array", source_location)
        args = factory.assign_multiple(
            l_count=_get_arc4_array_length(left_wtype, left, source_location),
            l_head_and_tail=_get_arc4_array_head_and_tail(left_wtype, left, source_location),
            r_count=r_count_vp,
            r_head_and_tail=r_head_and_tail_vp,
        )
        return factory.assign(
            invoke_puya_lib_subroutine(
                context,
                method_name="dynamic_array_concat_dynamic_element",
                source_location=source_location,
                module_name="algopy_lib_arc4",
                args=list(args),
            ),
            "concat_result",
        )

    raise InternalError("Unexpected element type", source_location)


def pop_arc4_array(
    context: IRFunctionBuildContext,
    expr: awst_nodes.ArrayPop,
    array_wtype: wtypes.ARC4DynamicArray,
) -> ValueProvider:
    source_location = expr.source_location

    base = context.visitor.visit_and_materialise_single(expr.base)
    args: list[Value | int | bytes] = [base]
    if array_wtype.element_type == wtypes.arc4_bool_wtype:
        method_name = "dynamic_array_pop_bit"
    elif _is_byte_length_header(array_wtype.element_type):  # TODO: multi_byte_length prefix?
        method_name = "dynamic_array_pop_byte_length_head"
    elif is_arc4_dynamic_size(array_wtype.element_type):
        method_name = "dynamic_array_pop_dynamic_element"
    else:
        fixed_size = get_arc4_fixed_bit_size(array_wtype.element_type)
        method_name = "dynamic_array_pop_fixed_size"
        args.append(fixed_size // 8)

    popped = mktemp(context, IRType.bytes, source_location, description="popped")
    data = mktemp(context, IRType.bytes, source_location, description="data")
    assign_targets(
        context,
        targets=[popped, data],
        source=invoke_puya_lib_subroutine(
            context,
            module_name="algopy_lib_arc4",
            method_name=method_name,
            args=args,
            source_location=source_location,
        ),
        assignment_location=source_location,
    )

    handle_arc4_assign(context, target=expr.base, value=data, source_location=source_location)

    return popped


def _encode_arc4_bool(
    context: IRFunctionBuildContext, bit: Value, source_location: SourceLocation
) -> Value:
    factory = _OpFactory(context, source_location)
    value = factory.constant(0x00.to_bytes(1, "big"))
    return factory.set_bit(value=value, index=0, bit=bit, temp_desc="encoded_bool")


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
        item = assign_temp(
            context,
            temp_description=f"item{index}",
            source=item_value,
            source_location=source_location,
        )

        items.append(item)
    return ValueTuple(source_location=source_location, values=items)


def _is_byte_length_header(wtype: wtypes.ARC4Type) -> bool:
    return (
        isinstance(wtype, wtypes.ARC4DynamicArray)
        and is_arc4_static_size(wtype.element_type)
        and get_arc4_fixed_bit_size(wtype.element_type) == 8
    )


def _maybe_get_inner_element_size(item_wtype: wtypes.ARC4Type) -> int | None:
    match item_wtype:
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


def _visit_arc4_tuple_encode(
    context: IRFunctionBuildContext,
    elements: Sequence[Value],
    tuple_items: Sequence[wtypes.ARC4Type],
    expr_loc: SourceLocation,
) -> ValueProvider:
    header_size = determine_arc4_tuple_head_size(tuple_items, round_end_result=True)
    factory = _OpFactory(context, expr_loc)
    current_tail_offset = factory.assign(factory.constant(header_size // 8), "current_tail_offset")
    encoded_tuple_buffer = factory.assign(factory.constant(b""), "encoded_tuple_buffer")

    for index, (element, el_wtype) in enumerate(zip(elements, tuple_items, strict=True)):
        if el_wtype == wtypes.arc4_bool_wtype:
            # Pack boolean
            before_header = determine_arc4_tuple_head_size(
                tuple_items[0:index], round_end_result=False
            )
            if before_header % 8 == 0:
                encoded_tuple_buffer = factory.concat(
                    encoded_tuple_buffer, element, "encoded_tuple_buffer"
                )
            else:
                is_true = factory.get_bit(element, 0, "is_true")
                encoded_tuple_buffer = factory.set_bit(
                    value=encoded_tuple_buffer,
                    index=before_header,
                    bit=is_true,
                    temp_desc="encoded_tuple_buffer",
                )
        elif not is_arc4_dynamic_size(el_wtype):
            # Append value
            encoded_tuple_buffer = factory.concat(
                encoded_tuple_buffer, element, "encoded_tuple_buffer"
            )
        else:
            # Append pointer
            offset_as_uint16 = factory.as_u16_bytes(current_tail_offset, "offset_as_uint16")
            encoded_tuple_buffer = factory.concat(
                encoded_tuple_buffer, offset_as_uint16, "encoded_tuple_buffer"
            )
            # Update Pointer
            data_length = factory.len(element, "data_length")
            current_tail_offset = factory.add(
                current_tail_offset, data_length, "current_tail_offset"
            )

    for element, el_wtype in zip(elements, tuple_items, strict=True):
        if is_arc4_dynamic_size(el_wtype):
            encoded_tuple_buffer = factory.concat(
                encoded_tuple_buffer, element, "encoded_tuple_buffer"
            )
    return encoded_tuple_buffer


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
    try:
        index_int = wtype.names.index(field_name)
    except ValueError:
        raise CodeError(f"Invalid arc4.Struct field name {field_name}", source_location) from None
    return _arc4_replace_tuple_item(context, base_expr, index_int, wtype, value, source_location)


def _arc4_replace_tuple_item(
    context: IRFunctionBuildContext,
    base_expr: awst_nodes.Expression,
    index_int: int,
    wtype: wtypes.ARC4Struct | wtypes.ARC4Tuple,
    value: ValueProvider,
    source_location: SourceLocation,
) -> Value:
    factory = _OpFactory(context, source_location)
    base = context.visitor.visit_and_materialise_single(base_expr)
    value = factory.assign(value, "assigned_value")
    element_type = wtype.types[index_int]
    header_up_to_item = determine_arc4_tuple_head_size(
        wtype.types[0:index_int],
        round_end_result=element_type != wtypes.arc4_bool_wtype,
    )
    if element_type == wtypes.arc4_bool_wtype:
        # Use Set bit
        is_true = factory.get_bit(value, 0, "is_true")
        return factory.set_bit(
            value=base,
            index=header_up_to_item,
            bit=is_true,
            temp_desc="updated_data",
        )
    elif is_arc4_static_size(element_type):
        return factory.replace(
            base,
            header_up_to_item // 8,
            value,
            "updated_data",
        )
    else:
        dynamic_indices = [index for index, t in enumerate(wtype.types) if is_arc4_dynamic_size(t)]

        item_offset = factory.extract_uint16(base, header_up_to_item // 8, "item_offset")
        data_up_to_item = factory.extract3(base, 0, item_offset, "data_up_to_item")
        dynamic_indices_after_item = [i for i in dynamic_indices if i > index_int]

        if not dynamic_indices_after_item:
            # This is the last dynamic type in the tuple
            # No need to update headers - just replace the data
            return factory.concat(data_up_to_item, value, "updated_data")
        header_up_to_next_dynamic_item = determine_arc4_tuple_head_size(
            types=wtype.types[0 : dynamic_indices_after_item[0]],
            round_end_result=True,
        )

        # update tail portion with new item
        next_item_offset = factory.extract_uint16(
            base,
            header_up_to_next_dynamic_item // 8,
            "next_item_offset",
        )
        total_data_length = factory.len(base, "total_data_length")
        data_beyond_item = factory.substring3(
            base,
            next_item_offset,
            total_data_length,
            "data_beyond_item",
        )
        updated_data = factory.concat(data_up_to_item, value, "updated_data")
        updated_data = factory.concat(updated_data, data_beyond_item, "updated_data")

        # loop through head and update any offsets after modified item
        item_length = factory.sub(next_item_offset, item_offset, "item_length")
        new_value_length = factory.len(value, "new_value_length")
        for dynamic_index in dynamic_indices_after_item:
            header_up_to_dynamic_item = determine_arc4_tuple_head_size(
                types=wtype.types[0:dynamic_index],
                round_end_result=True,
            )

            tail_offset = factory.extract_uint16(
                updated_data, header_up_to_dynamic_item // 8, "tail_offset"
            )
            # have to add the new length and then subtract the original to avoid underflow
            tail_offset = factory.add(tail_offset, new_value_length, "tail_offset")
            tail_offset = factory.sub(tail_offset, item_length, "tail_offset")
            tail_offset_bytes = factory.as_u16_bytes(tail_offset, "tail_offset_bytes")

            updated_data = factory.replace(
                updated_data, header_up_to_dynamic_item // 8, tail_offset_bytes, "updated_data"
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
        item_start_offset = assign_intrinsic_op(
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
                item_end_offset = assign_intrinsic_op(
                    context,
                    target="item_end_offset",
                    op=AVMOp.extract_uint16,
                    args=[array_head_and_tail, next_dynamic_head_offset],
                    source_location=source_location,
                )
                break
        else:
            item_end_offset = assign_intrinsic_op(
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
    is_true = assign_temp(
        context,
        temp_description="is_true",
        source=Intrinsic(op=AVMOp.getbit, args=[data, index], source_location=source_location),
        source_location=source_location,
    )
    return _encode_arc4_bool(context, is_true, source_location)


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


def _get_arc4_array_tail_data_and_item_count(
    context: IRFunctionBuildContext, expr: awst_nodes.Expression, source_location: SourceLocation
) -> tuple[Value, Value]:
    """
    For ARC4 containers (dynamic array, static array) will return the tail data and item count
    For native tuples will return the tuple items packed into the equivalent static array
    of tail data and item count
    """
    factory = _OpFactory(context, source_location)
    match expr:
        case awst_nodes.Expression(
            wtype=wtypes.ARC4DynamicArray() | wtypes.ARC4StaticArray() as arr_wtype
        ):
            array = context.visitor.visit_and_materialise_single(expr)
            array_length = factory.assign(
                _get_arc4_array_length(arr_wtype, array, source_location),
                "array_length",
            )
            array_head_and_tail = factory.assign(
                _get_arc4_array_head_and_tail(arr_wtype, array, source_location),
                "array_head_and_tail",
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
            data = factory.constant(b"")
            for val in values:
                data = factory.concat(data, val, "data")
            tuple_length = UInt64Constant(
                value=len(values),
                source_location=source_location,
            )
            return data, tuple_length
        case _:
            raise InternalError(f"Unsupported array type: {expr.wtype}")


def _itob_fixed(
    context: IRFunctionBuildContext, value: Value, num_bytes: int, source_location: SourceLocation
) -> ValueProvider:
    if value.atype == AVMType.uint64:
        val_as_bytes = assign_temp(
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
        len_ = assign_temp(
            context,
            temp_description="len_",
            source=Intrinsic(op=AVMOp.len_, args=[value], source_location=source_location),
            source_location=source_location,
        )
        no_overflow = assign_temp(
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

    b_zeros = assign_temp(
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

    value = assign_temp(
        context, value, temp_description="assigned_value", source_location=source_location
    )

    index = context.visitor.visit_and_materialise_single(index_value_expr)

    def updated_result(method_name: str, args: list[Value | int | bytes]) -> Register:
        invoke = invoke_puya_lib_subroutine(
            context,
            module_name="algopy_lib_arc4",
            method_name=method_name,
            args=args,
            source_location=source_location,
        )
        return assign_temp(
            context, invoke, temp_description="updated_value", source_location=source_location
        )

    if _is_byte_length_header(wtype.element_type):
        if isinstance(wtype, wtypes.ARC4DynamicArray):
            return updated_result("dynamic_array_replace_byte_length_head", [base, value, index])
        else:
            return updated_result(
                "static_array_replace_byte_length_head", [base, value, index, wtype.array_size]
            )
    elif is_arc4_dynamic_size(wtype.element_type):
        if isinstance(wtype, wtypes.ARC4DynamicArray):
            return updated_result("dynamic_array_replace_dynamic_element", [base, value, index])
        else:
            return updated_result(
                "static_array_replace_dynamic_element", [base, value, index, wtype.array_size]
            )
    array_length = (
        UInt64Constant(value=wtype.array_size, source_location=source_location)
        if isinstance(wtype, wtypes.ARC4StaticArray)
        else Intrinsic(
            source_location=source_location,
            op=AVMOp.extract_uint16,
            args=[base, UInt64Constant(value=0, source_location=source_location)],
        )
    )
    _assert_index_in_bounds(context, index, array_length, source_location)

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
        write_offset = assign_intrinsic_op(
            context,
            target="write_offset",
            op=AVMOp.mul,
            args=[index, offset_per_item],
            source_location=source_location,
        )
        if dynamic_offset:
            write_offset = assign_intrinsic_op(
                context,
                target=write_offset,
                op=AVMOp.add,
                args=[write_offset, dynamic_offset],
                source_location=source_location,
            )

    if element_size == 1:
        is_true = assign_intrinsic_op(
            context,
            target="is_true",
            op=AVMOp.getbit,
            args=[value, 0],
            source_location=source_location,
        )
        updated_target = assign_intrinsic_op(
            context,
            target="updated_target",
            op=AVMOp.setbit,
            args=[base, write_offset, is_true],
            return_type=base.ir_type,
            source_location=source_location,
        )
    else:
        updated_target = assign_intrinsic_op(
            context,
            target="updated_target",
            op=AVMOp.replace3,
            args=[base, write_offset, value],
            source_location=source_location,
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
    factory = _OpFactory(context, source_location)

    def array_data(expr: awst_nodes.Expression) -> Value:
        match expr.wtype:
            case wtypes.ARC4StaticArray():
                return context.visitor.visit_and_materialise_single(expr)
            case wtypes.ARC4DynamicArray():
                expr_value = context.visitor.visit_and_materialise_single(expr)
                return factory.extract_to_end(expr_value, 2, "expr_value_trimmed")
            case wtypes.WTuple():
                values = context.visitor.visit_and_materialise(expr)
                data = factory.constant(b"")
                for val in values:
                    data = factory.concat(data, val, "data")
                return data
            case _:
                raise InternalError(
                    f"Unexpected operand type for concatenation {expr.wtype}", source_location
                )

    left_data = array_data(left)
    right_data = array_data(right)
    concatenated = factory.concat(left_data, right_data, "concatenated")
    if byte_size == 1:
        len_ = factory.len(concatenated, "len_")
    else:
        byte_len = factory.len(concatenated, "byte_len")
        len_ = assign_intrinsic_op(
            context,
            source_location=source_location,
            op=AVMOp.div_floor,
            args=[byte_len, byte_size],
            target="len_",
        )

    len_16_bit = factory.as_u16_bytes(len_, "len_16_bit")
    return factory.concat(len_16_bit, concatenated, "concat_result")


def _arc4_items_as_arc4_tuple(
    context: IRFunctionBuildContext,
    item_wtype: wtypes.ARC4Type,
    items: Sequence[Value],
    source_location: SourceLocation,
) -> Value:
    factory = _OpFactory(context, source_location)
    result = factory.constant(b"")
    if is_arc4_dynamic_size(item_wtype):
        tail_offset: Value = UInt64Constant(value=len(items) * 2, source_location=source_location)
        for item in items:
            next_item_head = factory.as_u16_bytes(tail_offset, "next_item_head")
            result = factory.concat(result, next_item_head, "result")
            tail_offset = factory.add(
                tail_offset, factory.len(item, "next_item_len"), "tail_offset"
            )
    for item in items:
        result = factory.concat(result, item, "result")

    return result


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

    array_length = assign_temp(
        context,
        source_location=source_location,
        temp_description="array_length",
        source=length,
    )

    index_is_in_bounds = assign_temp(
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
    wtype: wtypes.ARC4Array,
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
            raise InternalError("Unexpected ARC4 array type", source_location)


def _get_arc4_array_head_and_tail(
    wtype: wtypes.ARC4Array,
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
            raise InternalError("Unexpected ARC4 array type", source_location)


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

    factory = _OpFactory(context, source_location)
    # special case to use extract with immediate length of 0 where possible
    # TODO: have an IR pseudo op, extract_to_end that handles this for non constant values?
    if isinstance(array_length, UInt64Constant) and array_length.value <= 127:
        return factory.extract_to_end(array_length, array_length.value * 2, "data")
    start_of_tail = factory.mul(array_length, 2, "start_of_tail")
    total_length = factory.len(array_head_and_tail, "total_length")
    return factory.substring3(array_head_and_tail, start_of_tail, total_length, "data")


@attrs.frozen
class _OpFactory:
    context: IRFunctionBuildContext
    source_location: SourceLocation | None

    def assign(self, value: ValueProvider, temp_desc: str) -> Register:
        register = assign_temp(
            self.context, value, temp_description=temp_desc, source_location=self.source_location
        )
        return register

    def assign_multiple(self, **values: ValueProvider) -> Sequence[Register]:
        return [self.assign(value, desc) for desc, value in values.items()]

    def add(self, a: Value, b: Value | int, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.add,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def sub(self, a: Value, b: Value | int, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.sub,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def mul(self, a: Value, b: Value | int, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.mul,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def len(self, value: Value, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.len_,
            args=[value],
            source_location=self.source_location,
        )
        return result

    def eq(self, a: Value, b: Value, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.eq,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def select(self, false: Value, true: Value, condition: Value, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.select,
            args=[false, true, condition],
            return_type=true.ir_type,
            source_location=self.source_location,
        )
        return result

    def extract_uint16(self, a: Value, b: Value | int, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.extract_uint16,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def itob(self, value: Value | int, temp_desc: str) -> Register:
        itob = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.itob,
            args=[value],
            source_location=self.source_location,
        )
        return itob

    def as_u16_bytes(self, a: Value | int, temp_desc: str) -> Register:
        as_bytes = self.itob(a, "as_bytes")
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.extract,
            immediates=[6, 2],
            args=[as_bytes],
            source_location=self.source_location,
        )
        return result

    def concat(self, a: Value | bytes, b: Value | bytes, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.concat,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def constant(self, value: int | bytes) -> Value:
        if isinstance(value, int):
            return UInt64Constant(value=value, source_location=self.source_location)
        else:
            return BytesConstant(
                value=value, encoding=AVMBytesEncoding.base16, source_location=self.source_location
            )

    def set_bit(self, *, value: Value, index: int, bit: Value | int, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.setbit,
            args=[value, index, bit],
            return_type=value.ir_type,
            source_location=self.source_location,
        )
        return result

    def get_bit(self, value: Value, index: Value | int, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.getbit,
            args=[value, index],
            source_location=self.source_location,
        )
        return result

    def extract_to_end(self, value: Value, start: int, temp_desc: str) -> Register:
        if start > 255:
            raise InternalError(
                "Cannot use extract with a length of 0 if start > 255", self.source_location
            )
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.extract,
            immediates=[start, 0],
            args=[value],
            source_location=self.source_location,
        )
        return result

    def substring3(
        self,
        value: Value | bytes,
        start: Value | int,
        end_ex: Value | int,
        temp_desc: str,
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.substring3,
            args=[value, start, end_ex],
            source_location=self.source_location,
        )
        return result

    def replace(
        self,
        value: Value | bytes,
        index: Value | int,
        replacement: Value | bytes,
        temp_desc: str,
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            source_location=self.source_location,
            op=AVMOp.replace3,
            args=[value, index, replacement],
        )
        return result

    def extract3(
        self,
        value: Value | bytes,
        index: Value | int,
        length: Value | int,
        temp_desc: str,
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.extract3,
            args=[value, index, length],
            source_location=self.source_location,
        )
        return result
