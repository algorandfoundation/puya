from collections.abc import Sequence

from puya import log
from puya.avm import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.ir.arc4 import (
    get_arc4_static_bit_size,
    get_arc4_tuple_head_size,
    is_arc4_dynamic_size,
    is_arc4_static_size,
)
from puya.ir.arc4_types import (
    is_equivalent_effective_array_encoding,
    maybe_wtype_to_arc4_wtype,
)
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import (
    OpFactory,
    assert_value,
    assign_intrinsic_op,
    assign_targets,
    assign_temp,
    convert_constants,
    mktemp,
)
from puya.ir.builder.arrays import (
    ArrayIterator,
    get_array_encoded_items,
    get_array_length as get_native_array_length,
)
from puya.ir.builder.assignment import handle_assignment
from puya.ir.builder.mem import read_slot
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import (
    Intrinsic,
    InvokeSubroutine,
    Register,
    UInt64Constant,
    Value,
    ValueProvider,
    ValueTuple,
)
from puya.ir.types_ import (
    ArrayType,
    PrimitiveIRType,
    get_wtype_arity,
    wtype_to_encoded_ir_type,
)
from puya.parse import SourceLocation, sequential_source_locations_merge
from puya.utils import bits_to_bytes

logger = log.get_logger(__name__)


def decode_arc4_value(
    context: IRFunctionBuildContext,
    value: Value,
    arc4_wtype: wtypes.WType,
    target_wtype: wtypes.WType,
    loc: SourceLocation,
) -> ValueProvider:
    if arc4_wtype == target_wtype:
        return value
    match arc4_wtype, target_wtype:
        case wtypes.ARC4UIntN(), wtypes.biguint_wtype:
            return value
        case wtypes.ARC4UIntN(), (wtypes.uint64_wtype | wtypes.bool_wtype):
            return Intrinsic(
                op=AVMOp.btoi,
                args=[value],
                source_location=loc,
            )
        case wtypes.arc4_bool_wtype, wtypes.bool_wtype:
            return Intrinsic(
                op=AVMOp.getbit,
                args=[value, UInt64Constant(value=0, source_location=None)],
                source_location=loc,
                types=(PrimitiveIRType.bool,),
            )
        case wtypes.ARC4DynamicArray(element_type=wtypes.ARC4UIntN(n=8)), (
            wtypes.bytes_wtype
            | wtypes.string_wtype
        ):
            return Intrinsic(
                op=AVMOp.extract,
                immediates=[2, 0],
                args=[value],
                source_location=loc,
            )
        case (
            wtypes.ARC4Tuple()
            | wtypes.ARC4Struct() as arc4_tuple,
            wtypes.WTuple() as native_tuple,
        ) if (len(arc4_tuple.types) == len(native_tuple.types)):
            return _visit_arc4_tuple_decode(
                context, arc4_tuple, value, target_wtype=native_tuple, source_location=loc
            )
        case wtypes.ARC4DynamicArray(), wtypes.StackArray() if (
            is_equivalent_effective_array_encoding(target_wtype, arc4_wtype, loc)
        ):
            return value
    raise InternalError(
        f"unsupported ARC4Decode operation from {arc4_wtype} to {target_wtype}", loc
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


def encode_value_provider(
    context: IRFunctionBuildContext,
    value_provider: ValueProvider,
    value_wtype: wtypes.WType,
    arc4_wtype: wtypes.ARC4Type,
    loc: SourceLocation,
) -> ValueProvider:
    match arc4_wtype, value_wtype:
        case (
            wtypes.arc4_bool_wtype,
            wtypes.bool_wtype,
        ):
            (value,) = context.visitor.materialise_value_provider(
                value_provider, description="to_encode"
            )
            return _encode_arc4_bool(context, value, loc)
        case (
            wtypes.ARC4UIntN(n=bits),
            (wtypes.bool_wtype | wtypes.uint64_wtype | wtypes.biguint_wtype),
        ):
            (value,) = context.visitor.materialise_value_provider(
                value_provider, description="to_encode"
            )
            num_bytes = bits // 8
            return _itob_fixed(context, value, num_bytes, loc)
        case (
            wtypes.ARC4Tuple(types=arc4_item_types),
            wtypes.WTuple(types=item_types),
        ):
            elements = context.visitor.materialise_value_provider(
                value_provider, description="elements_to_encode"
            )
            arc4_items = _encode_arc4_tuple_items(
                context, elements, item_types, arc4_item_types, loc
            )
            return _visit_arc4_tuple_encode(context, arc4_items, arc4_item_types, loc)
        case (
            wtypes.ARC4Struct(types=arc4_item_types),
            wtypes.WTuple(types=item_types),
        ):
            elements = context.visitor.materialise_value_provider(
                value_provider, description="elements_to_encode"
            )
            arc4_items = _encode_arc4_tuple_items(
                context, elements, item_types, arc4_item_types, loc
            )
            return _visit_arc4_tuple_encode(context, arc4_items, arc4_item_types, loc)
        case (
            wtypes.ARC4DynamicArray(element_type=wtypes.ARC4UIntN(n=8)),
            (wtypes.bytes_wtype | wtypes.string_wtype),
        ):
            (value,) = context.visitor.materialise_value_provider(
                value_provider, description="to_encode"
            )
            factory = OpFactory(context, loc)
            length = factory.len(value, "length")
            length_uint16 = factory.as_u16_bytes(length, "length_uint16")
            return factory.concat(length_uint16, value, "encoded_value")
        case (wtypes.arc4_address_alias, wtypes.account_wtype):
            return value_provider
        case (
            wtypes.ARC4Array(),
            wtypes.StackArray(),
        ) if is_equivalent_effective_array_encoding(value_wtype, arc4_wtype, loc):
            # already ARC4 encoded
            return value_provider
        case _:
            raise InternalError(
                f"unsupported ARC4 translation from {value_wtype} to {arc4_wtype}", loc
            )


def _encode_arc4_tuple_items(
    context: IRFunctionBuildContext,
    elements: list[Value],
    item_wtypes: Sequence[wtypes.WType],
    arc4_item_wtypes: Sequence[wtypes.ARC4Type],
    loc: SourceLocation,
) -> Sequence[Value]:
    arc4_items = []
    for item_wtype, arc4_item_wtype in zip(item_wtypes, arc4_item_wtypes, strict=True):
        item_arity = get_wtype_arity(item_wtype)
        item_elements = elements[:item_arity]
        elements = elements[item_arity:]
        if item_wtype == arc4_item_wtype:
            arc4_items.extend(item_elements)
            continue

        item_value_provider = (
            item_elements[0]
            if item_arity == 1
            else ValueTuple(
                values=item_elements,
                source_location=sequential_source_locations_merge(
                    [e.source_location for e in item_elements]
                ),
            )
        )
        arc4_item_vp = encode_value_provider(
            context,
            item_value_provider,
            item_wtype,
            arc4_item_wtype,
            item_value_provider.source_location or loc,
        )
        (arc4_item,) = context.visitor.materialise_value_provider(arc4_item_vp, "arc4_item")
        arc4_items.append(arc4_item)
    return arc4_items


def encode_arc4_exprs_as_array(
    context: IRFunctionBuildContext,
    wtype: wtypes.ARC4Array,
    values: Sequence[awst_nodes.Expression],
    loc: SourceLocation,
) -> ValueProvider:
    elements = [context.visitor.visit_and_materialise_single(value) for value in values]
    return _encode_arc4_values_as_array(context, wtype, elements, loc)


def _encode_arc4_values_as_array(
    context: IRFunctionBuildContext,
    wtype: wtypes.ARC4Array,
    elements: Sequence[Value],
    loc: SourceLocation,
) -> ValueProvider:
    factory = OpFactory(context, loc)
    if isinstance(wtype, wtypes.ARC4DynamicArray):
        len_prefix = len(elements).to_bytes(2, "big")
    else:
        len_prefix = b""
    element_type = wtype.element_type
    if element_type != wtypes.arc4_bool_wtype:
        array_head_and_tail = _arc4_items_as_arc4_tuple(context, element_type, elements, loc)
    else:
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
    factory = OpFactory(context, source_location)
    array_length_vp = get_arc4_array_length(array_wtype, array, source_location)
    array_head_and_tail_vp = _get_arc4_array_head_and_tail(
        context, array_wtype, array, source_location
    )
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
        item_bit_size = get_arc4_static_bit_size(item_wtype)
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
    length_vp = get_arc4_array_length(array_wtype, array, source_location)
    array_length = assign_temp(
        context,
        length_vp,
        temp_description="array_length",
        source_location=source_location,
    )
    return ArrayIterator(
        array_length=array_length,
        get_value_at_index=lambda index: arc4_array_index(
            context,
            array_wtype=array_wtype,
            array=array,
            index=index,
            source_location=source_location,
            assert_bounds=False,
        ),
    )


def handle_arc4_assign(
    context: IRFunctionBuildContext,
    target: awst_nodes.Expression,
    value: ValueProvider,
    source_location: SourceLocation,
    *,
    is_nested_update: bool,
) -> Value:
    result: Value
    match target:
        case awst_nodes.IndexExpression(
            base=awst_nodes.Expression(
                wtype=wtypes.ARC4DynamicArray() | wtypes.ARC4StaticArray() as array_wtype
            ) as base_expr,
            index=index_value,
        ):
            item = arc4_replace_array_item(
                context,
                base_expr=base_expr,
                index_value_expr=index_value,
                wtype=array_wtype,
                value=value,
                source_location=source_location,
            )
            return handle_arc4_assign(
                context,
                target=base_expr,
                value=item,
                source_location=source_location,
                is_nested_update=True,
            )
        case awst_nodes.FieldExpression(
            base=awst_nodes.Expression(wtype=wtypes.ARC4Struct() as struct_wtype) as base_expr,
            name=field_name,
        ):
            item = _arc4_replace_struct_item(
                context,
                base_expr=base_expr,
                field_name=field_name,
                wtype=struct_wtype,
                value=value,
                source_location=source_location,
            )
            return handle_arc4_assign(
                context,
                target=base_expr,
                value=item,
                source_location=source_location,
                is_nested_update=True,
            )
        case awst_nodes.TupleItemExpression(
            base=awst_nodes.Expression(wtype=wtypes.ARC4Tuple() as tuple_wtype) as base_expr,
            index=index_value,
        ):
            item = _arc4_replace_tuple_item(
                context,
                base_expr=base_expr,
                index_int=index_value,
                wtype=tuple_wtype,
                value=value,
                source_location=source_location,
            )
            return handle_arc4_assign(
                context,
                target=base_expr,
                value=item,
                source_location=source_location,
                is_nested_update=True,
            )
        # this function is sometimes invoked outside an assignment expr/stmt, which
        # is how a non l-value expression can be possible
        # TODO: refactor this so that this special case is handled where it originates
        case awst_nodes.TupleItemExpression(wtype=wtypes.WType(immutable=False)):
            (result,) = handle_assignment(
                context,
                target,
                value=value,
                assignment_location=source_location,
                is_nested_update=True,
            )
            return result
        case _:
            (result,) = handle_assignment(
                context,
                target,
                value=value,
                assignment_location=source_location,
                is_nested_update=is_nested_update,
            )
            return result


def dynamic_array_concat_and_convert(
    context: IRFunctionBuildContext,
    array_wtype: wtypes.ARC4DynamicArray,
    array_expr: awst_nodes.Expression,
    iter_expr: awst_nodes.Expression,
    source_location: SourceLocation,
) -> Value:
    """
    Takes an expression which is effectively ARC-4 DynamicArray encoded,
     and concats it with an iterable like expression.
    If the iterable type contains non ARC4 values, they will be encoded to the element type
    of the array
    """
    factory = OpFactory(context, source_location)

    # check right is a valid type to concat
    right_wtype = iter_expr.wtype
    element_type, right_native_type = _get_arc4_element_type(iter_expr)

    if array_wtype.element_type != element_type:
        raise CodeError("unsupported element type for concatenation", iter_expr.source_location)

    if is_arc4_static_size(element_type) and element_type != wtypes.arc4_bool_wtype:
        element_size = get_arc4_static_bit_size(element_type)
        return _concat_dynamic_array_fixed_size(
            context,
            left=array_expr,
            right=iter_expr,
            source_location=source_location,
            byte_size=element_size // 8,
        )

    left = context.visitor.visit_and_materialise_single(array_expr)
    if element_type == wtypes.arc4_bool_wtype:
        (r_data, r_length) = _get_arc4_array_tail_data_and_item_count(
            context, iter_expr, element_type, right_native_type, source_location
        )
        if isinstance(right_wtype, wtypes.WTuple):
            # each bit is in its own byte
            read_step = 8
        else:
            # bits are already packed
            read_step = 1
        invoke_name = "dynamic_array_concat_bits"
        invoke_args = [
            left,
            r_data,
            r_length,
            UInt64Constant(value=read_step, source_location=source_location),
        ]
    elif _is_byte_length_header(element_type):
        (r_data, r_length) = _get_arc4_array_tail_data_and_item_count(
            context, iter_expr, element_type, right_native_type, source_location
        )
        invoke_name = "dynamic_array_concat_byte_length_head"
        invoke_args = [left, r_data, r_length]
    elif is_arc4_dynamic_size(element_type):
        r_count_vp, r_head_and_tail_vp = _extract_dynamic_element_count_head_and_tail(
            context, element_type, iter_expr, right_native_type, right_wtype, source_location
        )
        invoke_name = "dynamic_array_concat_dynamic_element"
        invoke_args = list(
            factory.assign_multiple(
                l_count=get_arc4_array_length(array_wtype, left, source_location),
                l_head_and_tail=_get_arc4_array_head_and_tail(
                    context, array_wtype, left, source_location
                ),
                r_count=r_count_vp,
                r_head_and_tail=r_head_and_tail_vp,
            )
        )
    else:
        raise InternalError("unexpected element type", source_location)
    invoke = _invoke_puya_lib_subroutine(
        context,
        full_name=f"_puya_lib.arc4.{invoke_name}",
        args=invoke_args,
        source_location=source_location,
    )
    return factory.assign(invoke, "concat_result")


def _extract_dynamic_element_count_head_and_tail(
    context: IRFunctionBuildContext,
    element_type: wtypes.ARC4Type,
    iter_expr: awst_nodes.Expression,
    right_native_type: wtypes.WType | None,
    right_wtype: wtypes.WType,
    source_location: SourceLocation,
) -> tuple[ValueProvider, ValueProvider]:
    if isinstance(right_wtype, wtypes.ARC4Array | wtypes.StackArray):
        right = context.visitor.visit_and_materialise_single(iter_expr)
        if right_native_type is not None:
            logger.debug(
                f"assuming {right_native_type} is already encoded as {element_type}",
                location=source_location,
            )
        r_count_vp = _get_any_array_length(context, right_wtype, right, source_location)
        r_head_and_tail_vp = _get_arc4_array_head_and_tail(
            context, right_wtype, right, source_location
        )
    elif isinstance(right_wtype, wtypes.WTuple):
        r_count_vp = UInt64Constant(value=len(right_wtype.types), source_location=source_location)
        right_values = context.visitor.visit_and_materialise(iter_expr)
        if right_native_type is not None:
            right_values = _encode_n_items_as_arc4_items(
                context,
                right_values,
                right_native_type,
                element_type,
                iter_expr.source_location,
            )
        r_head_and_tail_vp = _arc4_items_as_arc4_tuple(
            context, element_type, right_values, source_location
        )
    elif isinstance(right_wtype, wtypes.ARC4Tuple):
        assert right_native_type is None
        r_count_vp = UInt64Constant(value=len(right_wtype.types), source_location=source_location)
        r_head_and_tail_vp = context.visitor.visit_and_materialise_single(iter_expr)
    elif isinstance(right_wtype, wtypes.ReferenceArray):
        raise InternalError(
            "shouldn't have reference array of dynamically-sized element type", source_location
        )
    else:
        raise InternalError("Expected array", source_location)
    return r_count_vp, r_head_and_tail_vp


def _get_arc4_element_type(
    expr: awst_nodes.Expression,
) -> tuple[wtypes.ARC4Type, wtypes.WType | None]:
    right_wtype = expr.wtype
    loc = expr.source_location
    right_unencoded_type = None
    if isinstance(right_wtype, wtypes.ARC4Array):
        right_element_type = right_wtype.element_type
    elif isinstance(right_wtype, wtypes.ARC4Tuple):
        right_element_type, *other_arc4 = set(right_wtype.types)
        if other_arc4:
            raise CodeError("only homogenous tuples can be concatenated", loc)
    else:
        if isinstance(right_wtype, wtypes.StackArray | wtypes.ReferenceArray):
            right_native_type = right_wtype.element_type
        elif isinstance(right_wtype, wtypes.WTuple):
            right_native_type, *other = set(right_wtype.types)
            if other:
                raise CodeError("only homogenous tuples can be concatenated", loc)
        else:
            raise CodeError("unsupported sequence type", loc)

        # gets the ARC-4 equivalent element type of the elements on the right
        right_arc4_type = maybe_wtype_to_arc4_wtype(right_native_type)
        if right_arc4_type is None:
            raise CodeError("unsupported element type for concatenation", loc)
        right_element_type = right_arc4_type
        if right_arc4_type != right_native_type:
            right_unencoded_type = right_native_type
    return right_element_type, right_unencoded_type


def _encode_n_items_as_arc4_items(
    context: IRFunctionBuildContext,
    items: Sequence[Value],
    source_wtype: wtypes.WType,
    target_wtype: wtypes.ARC4Type,
    loc: SourceLocation,
) -> Sequence[Value]:
    source_types = (
        source_wtype.types if isinstance(source_wtype, wtypes.WTuple) else (source_wtype,)
    )
    target_types = (
        target_wtype.types
        if isinstance(target_wtype, wtypes.ARC4Tuple | wtypes.ARC4Struct)
        else (target_wtype,)
    )
    item_arity = get_wtype_arity(source_wtype)
    encoded_items = list[Value]()
    factory = OpFactory(context, loc)
    for item_start_idx in range(0, len(items), item_arity):
        arc4_items = _encode_arc4_tuple_items(
            context,
            list(items[item_start_idx : item_start_idx + item_arity]),
            source_types,
            target_types,
            loc,
        )
        if isinstance(target_wtype, wtypes.ARC4Tuple | wtypes.ARC4Struct):
            encoded_items.append(
                factory.assign(
                    _visit_arc4_tuple_encode(context, arc4_items, target_types, loc),
                    "encoded_tuple",
                )
            )
        else:
            encoded_items.extend(arc4_items)

    return encoded_items


def pop_arc4_array(
    context: IRFunctionBuildContext,
    expr: awst_nodes.ArrayPop,
    array_wtype: wtypes.ARC4DynamicArray,
) -> ValueProvider:
    source_location = expr.source_location

    base = context.visitor.visit_and_materialise_single(expr.base)
    popped, data = invoke_arc4_array_pop(context, array_wtype.element_type, base, source_location)
    handle_arc4_assign(
        context,
        target=expr.base,
        value=data,
        is_nested_update=True,
        source_location=source_location,
    )

    return popped


def invoke_arc4_array_pop(
    context: IRFunctionBuildContext,
    element_wtype: wtypes.ARC4Type,
    base: Value,
    source_location: SourceLocation,
) -> tuple[Value, Value]:
    args: list[Value | int | bytes] = [base]
    if element_wtype == wtypes.arc4_bool_wtype:
        method_name = "dynamic_array_pop_bit"
    elif _is_byte_length_header(element_wtype):  # TODO: multi_byte_length prefix?
        method_name = "dynamic_array_pop_byte_length_head"
    elif is_arc4_dynamic_size(element_wtype):
        method_name = "dynamic_array_pop_dynamic_element"
    else:
        fixed_size = get_arc4_static_bit_size(element_wtype)
        method_name = "dynamic_array_pop_fixed_size"
        args.append(fixed_size // 8)

    popped = mktemp(context, PrimitiveIRType.bytes, source_location, description="popped")
    data = mktemp(context, PrimitiveIRType.bytes, source_location, description="data")
    assign_targets(
        context,
        targets=[popped, data],
        source=_invoke_puya_lib_subroutine(
            context,
            full_name=f"_puya_lib.arc4.{method_name}",
            args=args,
            source_location=source_location,
        ),
        assignment_location=source_location,
    )
    return popped, data


ARC4_TRUE = 0b10000000.to_bytes(1, "big")
ARC4_FALSE = 0b00000000.to_bytes(1, "big")


def _encode_arc4_bool(
    context: IRFunctionBuildContext, bit: Value, source_location: SourceLocation
) -> Value:
    factory = OpFactory(context, source_location)
    value = factory.constant(0x00.to_bytes(1, "big"))
    return factory.set_bit(value=value, index=0, bit=bit, temp_desc="encoded_bool")


def _visit_arc4_tuple_decode(
    context: IRFunctionBuildContext,
    wtype: wtypes.ARC4Tuple | wtypes.ARC4Struct,
    value: Value,
    target_wtype: wtypes.WTuple,
    source_location: SourceLocation,
) -> ValueProvider:
    items = list[Value]()
    for index, (target_item_wtype, item_wtype) in enumerate(
        zip(target_wtype.types, wtype.types, strict=True)
    ):
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
        if target_item_wtype != item_wtype:
            decoded_item = decode_arc4_value(
                context, item, item_wtype, target_item_wtype, source_location
            )
            items.extend(context.visitor.materialise_value_provider(decoded_item, item.name))
        else:
            items.append(item)
    return ValueTuple(source_location=source_location, values=items)


def _is_byte_length_header(wtype: wtypes.ARC4Type) -> bool:
    return (
        isinstance(wtype, wtypes.ARC4DynamicArray)
        and is_arc4_static_size(wtype.element_type)
        and get_arc4_static_bit_size(wtype.element_type) == 8
    )


def _maybe_get_inner_element_size(item_wtype: wtypes.ARC4Type) -> int | None:
    match item_wtype:
        case wtypes.ARC4Array(element_type=inner_static_element_type) if is_arc4_static_size(
            inner_static_element_type
        ):
            pass
        case _:
            return None
    return get_arc4_static_bit_size(inner_static_element_type) // 8


def _read_dynamic_item_using_length_from_arc4_container(
    context: IRFunctionBuildContext,
    *,
    array_head_and_tail: Value,
    inner_element_size: int,
    index: Value,
    source_location: SourceLocation,
) -> ValueProvider:
    factory = OpFactory(context, source_location)
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
    factory = OpFactory(context, source_location)
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
            error_message="Index access is out of bounds",
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

    item_end_offset = factory.select(
        false=end_of_array,
        true=next_item_offset,
        condition=has_next,
        temp_desc="end_offset",
        ir_type=PrimitiveIRType.uint64,
    )
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
    header_size = get_arc4_tuple_head_size(tuple_items, round_end_result=True)
    factory = OpFactory(context, expr_loc)
    current_tail_offset = factory.assign(factory.constant(header_size // 8), "current_tail_offset")
    encoded_tuple_buffer = factory.assign(factory.constant(b""), "encoded_tuple_buffer")

    for index, (element, el_wtype) in enumerate(zip(elements, tuple_items, strict=True)):
        if el_wtype == wtypes.arc4_bool_wtype:
            # Pack boolean
            before_header = get_arc4_tuple_head_size(tuple_items[0:index], round_end_result=False)
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
        elif is_arc4_static_size(el_wtype):
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
    factory = OpFactory(context, source_location)
    base = context.visitor.visit_and_materialise_single(base_expr)
    value = factory.assign(value, "assigned_value")
    element_type = wtype.types[index_int]
    header_up_to_item = get_arc4_tuple_head_size(
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
        header_up_to_next_dynamic_item = get_arc4_tuple_head_size(
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
            header_up_to_dynamic_item = get_arc4_tuple_head_size(
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
    head_up_to_item = get_arc4_tuple_head_size(tuple_item_types[:index], round_end_result=False)
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
                head_up_to_next_dynamic_item = get_arc4_tuple_head_size(
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
    item_bit_size = get_arc4_static_bit_size(item_wtype)
    item_length = UInt64Constant(value=item_bit_size // 8, source_location=source_location)
    return Intrinsic(
        op=AVMOp.extract3,
        args=[data, offset, item_length],
        source_location=source_location,
        error_message="Index access is out of bounds",
    )


def _get_any_array_length(
    context: IRFunctionBuildContext,
    arr_wtype: wtypes.ARC4Array | wtypes.StackArray | wtypes.ReferenceArray,
    array: Value,
    source_location: SourceLocation,
) -> ValueProvider:
    if isinstance(arr_wtype, wtypes.ARC4Array):
        return get_arc4_array_length(arr_wtype, array, source_location)
    else:
        return get_native_array_length(context, arr_wtype, array, source_location)


def _get_arc4_array_tail_data_and_item_count(
    context: IRFunctionBuildContext,
    expr: awst_nodes.Expression,
    arc4_element_type: wtypes.ARC4Type,
    native_element_type: wtypes.WType | None,
    source_location: SourceLocation,
) -> tuple[Value, Value]:
    """
    For supported iterable types, will return the ARC4 tail data and item count,
    doing any necessary ARC4 encoding.
    """

    factory = OpFactory(context, source_location)

    wtype = expr.wtype
    if isinstance(wtype, wtypes.WTuple):
        native_values = context.visitor.visit_and_materialise(expr)
        if native_element_type is None:
            encoded_values = native_values
        else:
            encoded_values = _encode_n_items_as_arc4_items(
                context,
                native_values,
                source_wtype=native_element_type,
                target_wtype=arc4_element_type,
                loc=source_location,
            )
        data = factory.constant(b"")
        for val in encoded_values:
            data = factory.concat(data, val, "data")
        item_count: Value = UInt64Constant(value=len(wtype.types), source_location=source_location)
        return data, item_count

    stack_value = context.visitor.visit_and_materialise_single(expr)
    if isinstance(wtype, wtypes.ARC4Tuple):
        head_and_tail = stack_value
        item_count = UInt64Constant(value=len(wtype.types), source_location=source_location)
    elif isinstance(wtype, wtypes.ARC4Array | wtypes.StackArray):
        item_count_vp = _get_any_array_length(context, wtype, stack_value, source_location)
        item_count = factory.assign(item_count_vp, "array_length")
        if native_element_type is not None:
            logger.debug(
                f"assuming {native_element_type} is already encoded as {arc4_element_type}",
                location=source_location,
            )
        head_and_tail_vp = _get_arc4_array_head_and_tail(
            context, wtype, stack_value, source_location
        )
        head_and_tail = factory.assign(head_and_tail_vp, "array_head_and_tail")
    elif isinstance(wtype, wtypes.ReferenceArray):
        raise InternalError("reference array of dynamic sized elements", source_location)
    else:
        raise InternalError(f"Unsupported array type: {wtype}")

    tail_data = _get_arc4_array_tail(
        context,
        element_wtype=arc4_element_type,
        array_head_and_tail=head_and_tail,
        array_length=item_count,
        source_location=source_location,
    )
    return tail_data, item_count


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
                error_message="overflow",
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


def arc4_replace_array_item(
    context: IRFunctionBuildContext,
    *,
    base_expr: awst_nodes.Expression,
    index_value_expr: awst_nodes.Expression,
    wtype: wtypes.ARC4Array,
    value: ValueProvider,
    source_location: SourceLocation,
) -> Value:
    assert type(wtype) in (wtypes.ARC4StaticArray, wtypes.ARC4DynamicArray)
    base = context.visitor.visit_and_materialise_single(base_expr)

    value = assign_temp(
        context, value, temp_description="assigned_value", source_location=source_location
    )

    index = context.visitor.visit_and_materialise_single(index_value_expr)

    def updated_result(method_name: str, args: list[Value | int | bytes]) -> Register:
        invoke = _invoke_puya_lib_subroutine(
            context,
            full_name=f"_puya_lib.arc4.{method_name}",
            args=args,
            source_location=source_location,
        )
        return assign_temp(
            context, invoke, temp_description="updated_value", source_location=source_location
        )

    if _is_byte_length_header(wtype.element_type):
        if isinstance(wtype, wtypes.ARC4StaticArray):
            return updated_result(
                "static_array_replace_byte_length_head", [base, value, index, wtype.array_size]
            )
        else:
            return updated_result("dynamic_array_replace_byte_length_head", [base, value, index])
    elif is_arc4_dynamic_size(wtype.element_type):
        if isinstance(wtype, wtypes.ARC4StaticArray):
            return updated_result(
                "static_array_replace_dynamic_element", [base, value, index, wtype.array_size]
            )
        else:
            return updated_result("dynamic_array_replace_dynamic_element", [base, value, index])
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

    element_size = get_arc4_static_bit_size(wtype.element_type)
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
        factory = OpFactory(context, source_location)
        updated_target = factory.set_bit(
            value=base,
            index=write_offset,
            bit=is_true,
            temp_desc="updated_target",
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
    factory = OpFactory(context, source_location)

    def array_data(expr: awst_nodes.Expression) -> Value:
        match expr.wtype:
            case wtypes.ReferenceArray():
                slot = context.visitor.visit_and_materialise_single(expr)
                return read_slot(context, slot, slot.source_location)
            case wtypes.ARC4StaticArray():
                return context.visitor.visit_and_materialise_single(expr)
            case wtypes.ARC4DynamicArray() | wtypes.StackArray():
                expr_value = context.visitor.visit_and_materialise_single(expr)
                return factory.extract_to_end(expr_value, 2, "expr_value_trimmed")
            case wtypes.WTuple(types=types) | wtypes.ARC4Tuple(types=types):
                element_type = wtype_to_encoded_ir_type(
                    types[0], require_static_size=True, loc=expr.source_location
                )
                return get_array_encoded_items(context, expr, ArrayType(element=element_type))
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
    factory = OpFactory(context, source_location)
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


def get_arc4_array_length(
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
    context: IRFunctionBuildContext,
    wtype: wtypes.ARC4Array | wtypes.StackArray | wtypes.ReferenceArray,
    array: Value,
    source_location: SourceLocation,
) -> ValueProvider:
    match wtype:
        case wtypes.ARC4StaticArray():
            return array
        case wtypes.ReferenceArray():
            return read_slot(context, array, source_location)
        case wtypes.ARC4DynamicArray() | wtypes.StackArray():
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
    if is_arc4_static_size(element_wtype):
        # static sized elements are encoded directly in the head and have no tail
        return array_head_and_tail

    factory = OpFactory(context, source_location)
    start_of_tail = factory.mul(array_length, 2, "start_of_tail")
    return factory.extract_to_end(array_head_and_tail, start_of_tail, "data")


def _invoke_puya_lib_subroutine(
    context: IRFunctionBuildContext,
    *,
    full_name: str,
    args: Sequence[Value | int | bytes],
    source_location: SourceLocation,
) -> InvokeSubroutine:
    sub = context.embedded_funcs_lookup[full_name]
    return InvokeSubroutine(
        target=sub,
        args=[convert_constants(arg, source_location) for arg in args],
        source_location=source_location,
    )
