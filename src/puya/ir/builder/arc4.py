import abc
import typing
from collections.abc import Sequence
from itertools import zip_longest

from puya import log
from puya.avm import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import (
    OpFactory,
    assert_value,
    assign_intrinsic_op,
    assign_targets,
    assign_temp,
    convert_constants,
    mktemp,
    undefined_value,
)
from puya.ir.builder.arrays import (
    ArrayIterator,
    get_array_encoded_items,
    get_array_length,
)
from puya.ir.builder.assignment import handle_assignment
from puya.ir.builder.mem import read_slot
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import (
    BigUIntConstant,
    Intrinsic,
    InvokeSubroutine,
    Register,
    UInt64Constant,
    Undefined,
    Value,
    ValueProvider,
    ValueTuple,
)
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import (
    AggregateIRType,
    ArrayEncoding,
    BoolEncoding,
    DynamicArrayEncoding,
    EncodedType,
    Encoding,
    FixedArrayEncoding,
    IRType,
    PrimitiveIRType,
    TupleEncoding,
    UIntEncoding,
    get_type_arity,
    type_has_encoding,
    wtype_to_encoding,
    wtype_to_ir_type,
    wtype_to_ir_type_and_encoding,
)
from puya.parse import SourceLocation, sequential_source_locations_merge
from puya.utils import bits_to_bytes, round_bits_to_nearest_bytes

logger = log.get_logger(__name__)


def maybe_decode_arc4_value_provider(
    context: IRRegisterContext,
    value_provider: ValueProvider,
    encoding: Encoding,
    target_type: IRType,
    loc: SourceLocation,
    *,
    temp_description: str = "tmp",
) -> ValueProvider:
    """If the target type is not already the required ARC-4 type, then decode it.

    This situation arises for example when indexing or iterating an array of "native" element
    types, which are in fact ARC-4 encoded. For example, an array of what is typed as uint64
    elements is actually byte encoded, thus in arc4.uint64 format and requires translation.

    So this function should only ever be called if target type is already arc4 type,
    or if the arc4 type can decode to the target type, any other situation results in a code error.
    """
    if isinstance(target_type, EncodedType) and target_type.encoding == encoding:
        return value_provider
    factory = OpFactory(context, loc)
    value = factory.assign(value_provider, temp_description)
    return decode_arc4_value(context, value, encoding, target_type, loc)


class ARC4Codec(abc.ABC):
    @abc.abstractmethod
    def encode(
        self,
        context: IRRegisterContext,
        value_provider: ValueProvider,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None: ...

    @abc.abstractmethod
    def decode(
        self,
        context: IRRegisterContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None: ...


class NativeTupleCodec(ARC4Codec):
    def __init__(self, native_type: AggregateIRType):
        self.native_type = native_type

    @typing.override
    def encode(
        self,
        context: IRRegisterContext,
        value_provider: ValueProvider,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        factory = OpFactory(context, loc)
        values = factory.materialise(value_provider, description="elements_to_encode")
        item_types = self.native_type.elements
        match encoding:
            case TupleEncoding(elements=elements) if len(elements) == len(item_types):
                arc4_items = _encode_arc4_tuple_items(context, values, item_types, encoding, loc)
                return _encode_arc4_values_as_tuple(context, arc4_items, encoding, loc)
            case _:
                return None

    @typing.override
    def decode(
        self,
        context: IRRegisterContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        item_types = self.native_type.elements
        match encoding:
            case TupleEncoding(elements=elements) if len(elements) == len(item_types):
                pass
            case _:
                return None
        return _decode_arc4_tuple_items(
            context, encoding, value, target_type=self.native_type, source_location=loc
        )


class ScalarCodec(ARC4Codec, abc.ABC):
    @typing.override
    @typing.final
    def encode(
        self,
        context: IRRegisterContext,
        value_provider: ValueProvider,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        factory = OpFactory(context, loc)
        (value,) = factory.materialise(value_provider, "to_encode")
        return self.encode_value(context, value, encoding, loc)

    @abc.abstractmethod
    def encode_value(
        self,
        context: IRRegisterContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None: ...


class BigUIntCodec(ScalarCodec):
    @typing.override
    def encode_value(
        self,
        context: IRRegisterContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        match encoding:
            case UIntEncoding(n=bits):
                factory = OpFactory(context, loc)
                num_bytes = bits // 8
                return factory.to_fixed_size(
                    value, num_bytes=num_bytes, temp_desc="arc4_encoded", error_message="overflow"
                )
        return None

    @typing.override
    def decode(
        self,
        context: IRRegisterContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        match encoding:
            case UIntEncoding():
                return value
        return None


class UInt64Codec(ScalarCodec):
    @typing.override
    def encode_value(
        self,
        context: IRRegisterContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        match encoding:
            case UIntEncoding(n=bits):
                num_bytes = bits // 8
                return _encode_native_uint64_to_arc4(context, value, num_bytes, loc)
        return None

    @typing.override
    def decode(
        self,
        context: IRRegisterContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        match encoding:
            # note that if bits were > 64, a runtime error would always occur, as btoi
            # will fail if input is more than 8 bytes.
            # if the need arose, we could handle the >64 case by asserting the value is in range
            # and then using extract_uint64
            case UIntEncoding(n=bits) if bits <= 64:
                return Intrinsic(op=AVMOp.btoi, args=[value], source_location=loc)
        return None


class BoolCodec(ScalarCodec):
    @typing.override
    def encode_value(
        self,
        context: IRRegisterContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        match encoding:
            case BoolEncoding():
                return _encode_arc4_bool(context, value, loc)
            case UIntEncoding(n=bits):
                num_bytes = bits // 8
                return _encode_native_uint64_to_arc4(context, value, num_bytes, loc)
        return None

    @typing.override
    def decode(
        self,
        context: IRRegisterContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        match encoding:
            case BoolEncoding():
                return Intrinsic(
                    op=AVMOp.getbit,
                    args=[value, UInt64Constant(value=0, source_location=None)],
                    types=(PrimitiveIRType.bool,),
                    source_location=loc,
                )
            case UIntEncoding():
                return Intrinsic(
                    op=AVMOp.neq_bytes,
                    args=[value, BigUIntConstant(value=0, source_location=None)],
                    types=(PrimitiveIRType.bool,),
                    source_location=loc,
                )
        return None


class BytesCodec(ScalarCodec):
    @typing.override
    def encode_value(
        self,
        context: IRRegisterContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        # TODO: check for string when mapping?
        # if _is_known_alias(target_type, expected=wtypes.arc4_string_alias):
        #   return None
        factory = OpFactory(context, loc)
        length = factory.len(value, "length")
        match encoding:
            case DynamicArrayEncoding(element=UIntEncoding(n=8), length_header=True):
                length_uint16 = factory.as_u16_bytes(length, "length_uint16")
                return factory.concat(length_uint16, value, "encoded_value")
            case DynamicArrayEncoding(element=UIntEncoding(n=8), length_header=False):
                return value
            case FixedArrayEncoding(element=UIntEncoding(n=8), size=num_bytes):
                lengths_equal = factory.eq(length, num_bytes, "lengths_equal")
                assert_value(
                    context, lengths_equal, error_message="invalid size", source_location=loc
                )
                return value
        return None

    @typing.override
    def decode(
        self,
        context: IRRegisterContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        # TODO: check for string when mapping?
        # if _is_known_alias(source_type, expected=wtypes.arc4_string_alias):
        #    return None
        match encoding:
            case DynamicArrayEncoding(element=UIntEncoding(n=8), length_header=True):
                return Intrinsic(
                    op=AVMOp.extract, immediates=[2, 0], args=[value], source_location=loc
                )
            case DynamicArrayEncoding(element=UIntEncoding(n=8), length_header=False):
                return value
            case wtypes.ARC4StaticArray(element_type=wtypes.ARC4UIntN(n=8)):
                return value
        return None


# TODO: work out if we need these codecs
"""
class StringCodec(ScalarCodec):
    @typing.override
    def encode_value(
        self,
        context: IRFunctionBuildContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        typing.assert_type(wtypes.arc4_string_alias, wtypes.ARC4DynamicArray)
        if _is_known_alias(target_type, expected=wtypes.arc4_string_alias):
            factory = OpFactory(context, loc)
            length = factory.len(value, "length")
            length_uint16 = factory.as_u16_bytes(length, "length_uint16")
            return factory.concat(length_uint16, value, "encoded_value")
        return None

    @typing.override
    def decode(
        self,
        context: IRFunctionBuildContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        typing.assert_type(wtypes.arc4_string_alias, wtypes.ARC4DynamicArray)
        if _is_known_alias(source_type, expected=wtypes.arc4_string_alias):
            return Intrinsic(
                op=AVMOp.extract, immediates=[2, 0], args=[value], source_location=loc
            )
        return None


class AccountCodec(ARC4Codec):
    @typing.override
    def encode(
        self,
        context: IRFunctionBuildContext,
        value_provider: ValueProvider,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        if _is_known_alias(target_type, expected=wtypes.arc4_address_alias):
            return value_provider
        return None

    @typing.override
    def decode(
        self,
        context: IRFunctionBuildContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        if _is_known_alias(source_type, expected=wtypes.arc4_address_alias):
            return value
        return None
"""


class StackArrayCodec(ARC4Codec):
    def __init__(self, native_type: IRType):
        self.native_type: typing.Final = native_type

    @typing.override
    def encode(
        self,
        context: IRRegisterContext,
        value_provider: ValueProvider,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        if isinstance(self.native_type, EncodedType) and self.native_type.encoding == encoding:
            return value_provider
        return None

    @typing.override
    def decode(
        self,
        context: IRRegisterContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        if isinstance(self.native_type, EncodedType) and self.native_type.encoding == encoding:
            return value
        return None


def _is_known_alias(wtype: wtypes.ARC4Type, *, expected: wtypes.ARC4Type) -> bool:
    # why? because arc4_name is not considered for structural equality, for reasons...
    # and we can't use `is` because of JSON inputs...
    return wtype == expected and wtype.arc4_alias == expected.arc4_alias


def _get_arc4_codec(ir_type: IRType) -> ARC4Codec | None:
    match ir_type:
        case AggregateIRType() as aggregate:
            return NativeTupleCodec(aggregate)
        case PrimitiveIRType.biguint:
            return BigUIntCodec()
        case PrimitiveIRType.bool:
            return BoolCodec()
        case wtypes.StackArray():
            return StackArrayCodec(ir_type)
        # TODO: what about these types
        # case wtypes.string_wtype:
        #    return StringCodec()
        case _ if ir_type.maybe_avm_type == AVMType.uint64:
            return UInt64Codec()
        case _ if ir_type.maybe_avm_type == AVMType.bytes:
            return BytesCodec()
        case _:
            return None


def decode_arc4_value(
    context: IRRegisterContext,
    value: Value,
    encoding: Encoding,
    target_type: IRType,
    loc: SourceLocation,
) -> ValueProvider:
    # TODO: migrate to ValueDecode

    codec = _get_arc4_codec(target_type)
    if codec is not None:
        result = codec.decode(context, value, encoding, loc)
        if result is not None:
            return result
    logger.error(
        f"unsupported ARC-4 decode operation from type {target_type=}, {encoding=}",
        location=loc,
    )
    return undefined_value(target_type, loc)


def encode_arc4_struct(
    context: IRRegisterContext,
    elements: Sequence[Value],
    encoding: TupleEncoding,
    element_ir_types: Sequence[IRType],
    loc: SourceLocation,
) -> ValueProvider:
    encoded_elements = _encode_arc4_tuple_items(context, elements, element_ir_types, encoding, loc)
    return _encode_arc4_values_as_tuple(context, encoded_elements, encoding, loc)


# TODO: this becomes the lowering implementation for ir.ValueEncode
def encode_value_provider(
    context: IRRegisterContext,
    value_provider: ValueProvider,
    value_type: IRType,
    encoding: Encoding,
    loc: SourceLocation,
) -> ValueProvider:
    codec = _get_arc4_codec(value_type)
    if codec is not None:
        result = codec.encode(context, value_provider, encoding, loc)
        if result is not None:
            return result
    if type_has_encoding(value_type, encoding):
        raise InternalError("redundant encode", loc)
    logger.error(
        f"unsupported ARC-4 encode operation for {value_type=!s}, {encoding=!s}", location=loc
    )
    return Undefined(
        ir_type=value_type,
        source_location=loc,
    )


def _encode_arc4_tuple_items(
    context: IRRegisterContext,
    elements: Sequence[Value],
    item_types: Sequence[IRType],
    encoding: TupleEncoding,
    loc: SourceLocation,
) -> list[Value]:
    factory = OpFactory(context, loc)
    encoded_items = list[Value]()
    for item_type, item_encoding in zip(item_types, encoding.elements, strict=True):
        item_arity = get_type_arity(item_type)
        item_elements = elements[:item_arity]
        elements = elements[item_arity:]
        if type_has_encoding(item_type, item_encoding):
            encoded_items.extend(item_elements)
            continue

        # TODO: use ValueEncode
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
        encoded_item_vp = encode_value_provider(
            context,
            item_value_provider,
            item_type,
            item_encoding,
            item_value_provider.source_location or loc,
        )
        (encoded_item,) = factory.materialise(encoded_item_vp, "arc4_item")
        encoded_items.append(encoded_item)
    return encoded_items


def encode_arc4_exprs_as_array(
    context: IRFunctionBuildContext,
    wtype: wtypes.ARC4Array,
    values: Sequence[awst_nodes.Expression],
    loc: SourceLocation,
) -> ValueProvider:
    elements = [
        element for value in values for element in context.visitor.visit_and_materialise(value)
    ]
    element_ir_type, element_encoding = wtype_to_ir_type_and_encoding(wtype.element_type, loc)
    # TODO: use ValueEncode
    if not type_has_encoding(element_ir_type, element_encoding):
        elements = _encode_n_items_as_arc4_items(
            context,
            elements,
            item_ir_type=element_ir_type,
            item_encoding=element_encoding,
            loc=loc,
        )
    array_encoding = wtype_to_encoding(wtype)
    return _encode_arc4_values_as_array(context, array_encoding, elements, loc)


def _encode_arc4_values_as_array(
    context: IRFunctionBuildContext,
    array_encoding: ArrayEncoding,
    elements: Sequence[Value],
    loc: SourceLocation,
) -> ValueProvider:
    element_encoding = array_encoding.element
    factory = OpFactory(context, loc)
    if isinstance(array_encoding, DynamicArrayEncoding):
        len_prefix = len(elements).to_bytes(2, "big")
    elif isinstance(array_encoding, FixedArrayEncoding):
        if len(elements) != array_encoding.size:
            logger.error(
                f"expected {array_encoding.size} elements, got {len(elements)}", location=loc
            )
            return undefined_value(EncodedType(array_encoding), loc)
        len_prefix = b""
    else:
        raise InternalError("unhandled ARC-4 Array type", loc)
    if not _bit_packed_bool(element_encoding):
        array_head_and_tail = _arc4_items_as_arc4_tuple(context, element_encoding, elements, loc)
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
    array_encoding: ArrayEncoding,
    item_type: IRType,
    array: Value,
    index: Value,
    source_location: SourceLocation,
    assert_bounds: bool = True,
) -> ValueProvider:
    # TODO: migrate to ArrayReadIndex
    factory = OpFactory(context, source_location)
    array_length_vp = get_array_length(context, array_encoding, array, source_location)
    array_head_and_tail_vp = _get_arc4_array_head_and_tail(array_encoding, array, source_location)
    array_head_and_tail = factory.assign(array_head_and_tail_vp, "array_head_and_tail")
    element_encoding = array_encoding.element

    if element_encoding.is_dynamic:
        inner_element_size = element_encoding.num_bytes
        if inner_element_size is not None:
            if assert_bounds:
                _assert_index_in_bounds(context, index, array_length_vp, source_location)
            item = _read_dynamic_item_using_length_from_arc4_container(
                context,
                array_head_and_tail=array_head_and_tail,
                inner_element_size=inner_element_size,
                index=index,
                source_location=source_location,
            )
        else:
            # no _assert_index_in_bounds here as end offset calculation implicitly checks
            item = _read_dynamic_item_using_end_offset_from_arc4_container(
                context,
                array_length_vp=array_length_vp,
                array_head_and_tail=array_head_and_tail,
                index=index,
                source_location=source_location,
            )
    elif _bit_packed_bool(element_encoding):
        if assert_bounds:
            # this catches the edge case of bit arrays that are not a multiple of 8
            # e.g. reading index 6 & 7 of an array that has a length of 6
            _assert_index_in_bounds(context, index, array_length_vp, source_location)
        item = _read_nth_bool_from_arc4_container(
            context,
            data=array_head_and_tail,
            index=index,
            source_location=source_location,
        )
    else:
        item_num_bytes = element_encoding.checked_num_bytes
        # no _assert_index_in_bounds here as static items will error on read if past end of array
        item = _read_static_item_from_arc4_container(
            data=array_head_and_tail,
            offset=factory.mul(index, item_num_bytes, "item_offset"),
            encoding=element_encoding,
            source_location=source_location,
        )
    # TODO: use ValueDecode
    if not type_has_encoding(item_type, element_encoding):
        item = factory.assign(item, "encoded")
        return decode_arc4_value(context, item, element_encoding, item_type, source_location)
    return item


def arc4_tuple_index(
    context: IRFunctionBuildContext,
    base: Value,
    index: int,
    tuple_encoding: TupleEncoding,
    item_ir_type: IRType,
    source_location: SourceLocation,
) -> ValueProvider:
    item_encoding = tuple_encoding.elements[index]

    result = _read_nth_item_of_arc4_heterogeneous_container(
        context,
        array_head_and_tail=base,
        tuple_encoding=tuple_encoding,
        index=index,
        source_location=source_location,
    )
    # TODO: use ValueDecode
    if not type_has_encoding(item_ir_type, item_encoding):
        factory = OpFactory(context, source_location)
        encoded = factory.assign(result, "encoded")
        result = decode_arc4_value(context, encoded, item_encoding, item_ir_type, source_location)
    return result


def build_for_in_array(
    context: IRFunctionBuildContext,
    array_encoding: ArrayEncoding,
    array_expr: awst_nodes.Expression,
    source_location: SourceLocation,
) -> ArrayIterator:
    array_wtype = array_expr.wtype
    assert isinstance(array_wtype, wtypes.ARC4Array), "expected ARC-4 array type"
    if not array_wtype.element_type.immutable:
        raise InternalError(
            "Attempted iteration of an ARC-4 array of mutable objects", source_location
        )
    array = context.visitor.visit_and_materialise_single(array_expr)
    length_vp = get_array_length(context, array_encoding, array, source_location)
    array_length = assign_temp(
        context,
        length_vp,
        temp_description="array_length",
        source_location=source_location,
    )
    item_type = wtype_to_ir_type(
        array_wtype.element_type, source_location=source_location, allow_aggregate=True
    )

    def _read_and_decode(index: Value) -> ValueProvider:
        assert isinstance(array_wtype, wtypes.ARC4Array), "expected ARC-4 array type"
        # TODO: split this into a read and a decode
        value = arc4_array_index(
            context,
            array_encoding=array_encoding,
            item_type=item_type,
            array=array,
            index=index,
            source_location=source_location,
            assert_bounds=False,
        )
        return value

    return ArrayIterator(array_length=array_length, get_value_at_index=_read_and_decode)


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
            array_encoding = wtype_to_encoding(array_wtype)
            assert isinstance(array_encoding, ArrayEncoding), "expected array encoding"
            element_ir_type = wtype_to_ir_type(
                array_wtype.element_type, source_location=source_location, allow_aggregate=True
            )

            item = arc4_replace_array_item(
                context,
                base_expr=base_expr,
                index_value_expr=index_value,
                array_encoding=array_encoding,
                element_ir_type=element_ir_type,
                value_vp=value,
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
            tuple_ir_type, tuple_encoding = wtype_to_ir_type_and_encoding(
                tuple_wtype, source_location
            )
            value_ir_type, _ = wtype_to_ir_type_and_encoding(
                tuple_wtype.types[index_value], source_location
            )
            item = _arc4_replace_tuple_item(
                context,
                base_expr=base_expr,
                index_int=index_value,
                tuple_encoding=tuple_encoding,
                value_ir_type=value_ir_type,
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
        case (
            awst_nodes.TupleItemExpression(wtype=wtypes.WType(immutable=False))
            | awst_nodes.FieldExpression(wtype=wtypes.WType(immutable=False))
        ):
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
    array_encoding: ArrayEncoding,
    array_expr: awst_nodes.Expression,
    iter_expr: awst_nodes.Expression,
    source_location: SourceLocation,
) -> Value:
    """
    Takes an expression which is effectively ARC-4 DynamicArray encoded,
     and concats it with an iterable like expression.
    If the iterable type contains non ARC-4 values, they will be encoded to the element type
    of the array
    """
    factory = OpFactory(context, source_location)

    # check right is a valid type to concat
    right_element_wtype = _get_iterable_element_wtype(iter_expr, source_location)
    right_element_ir_type, right_element_encoding = wtype_to_ir_type_and_encoding(
        right_element_wtype, source_location
    )
    element_encoding = array_encoding.element

    if element_encoding != right_element_encoding:
        raise CodeError("unsupported element type for concatenation", iter_expr.source_location)

    if not element_encoding.is_dynamic and not _bit_packed_bool(element_encoding):
        return _concat_dynamic_array_fixed_size(
            context,
            left=array_expr,
            right=iter_expr,
            source_location=source_location,
            byte_size=element_encoding.checked_num_bytes,
        )

    left = context.visitor.visit_and_materialise_single(array_expr)
    if _bit_packed_bool(element_encoding):
        (r_data, r_length) = _get_arc4_array_tail_data_and_item_count(
            context, iter_expr, element_encoding, right_element_ir_type, source_location
        )
        if isinstance(iter_expr.wtype, wtypes.WTuple | wtypes.ReferenceArray):
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
    elif _is_byte_length_header(element_encoding):
        (r_data, r_length) = _get_arc4_array_tail_data_and_item_count(
            context, iter_expr, element_encoding, right_element_ir_type, source_location
        )
        invoke_name = "dynamic_array_concat_byte_length_head"
        invoke_args = [left, r_data, r_length]
    elif element_encoding.is_dynamic:
        r_count_vp, r_head_and_tail_vp = _extract_dynamic_element_count_head_and_tail(
            context,
            array_encoding,
            iter_expr,
            source_location,
        )
        invoke_name = "dynamic_array_concat_dynamic_element"
        invoke_args = list(
            factory.assign_multiple(
                l_count=get_array_length(context, array_encoding, left, source_location),
                l_head_and_tail=_get_arc4_array_head_and_tail(
                    array_encoding, left, source_location
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


def _bit_packed_bool(encoding: Encoding) -> bool:
    return isinstance(encoding, BoolEncoding) and encoding.packable


def _extract_dynamic_element_count_head_and_tail(
    context: IRFunctionBuildContext,
    array_encoding: ArrayEncoding,
    iter_expr: awst_nodes.Expression,
    source_location: SourceLocation,
) -> tuple[ValueProvider, ValueProvider]:
    element_encoding = array_encoding.element
    iter_wtype = iter_expr.wtype
    if isinstance(iter_wtype, wtypes.ARC4Array | wtypes.StackArray):
        right = context.visitor.visit_and_materialise_single(iter_expr)
        r_count_vp = get_array_length(context, array_encoding, right, source_location)
        r_head_and_tail_vp = _get_arc4_array_head_and_tail(array_encoding, right, source_location)
    elif isinstance(iter_wtype, wtypes.WTuple):
        r_count_vp = UInt64Constant(value=len(iter_wtype.types), source_location=source_location)
        right_values = context.visitor.visit_and_materialise(iter_expr)
        element_wtype = _get_iterable_element_wtype(iter_expr, source_location)
        element_ir_type, element_encoding = wtype_to_ir_type_and_encoding(
            element_wtype, source_location
        )
        # TODO: use ValueEncode
        if not type_has_encoding(element_ir_type, element_encoding):
            right_values = _encode_n_items_as_arc4_items(
                context,
                right_values,
                element_ir_type,
                element_encoding,
                iter_expr.source_location,
            )
        r_head_and_tail_vp = _arc4_items_as_arc4_tuple(
            context, element_encoding, right_values, source_location
        )
    elif isinstance(iter_wtype, wtypes.ARC4Tuple):
        r_count_vp = UInt64Constant(value=len(iter_wtype.types), source_location=source_location)
        r_head_and_tail_vp = context.visitor.visit_and_materialise_single(iter_expr)
    elif isinstance(iter_wtype, wtypes.ReferenceArray):
        raise InternalError(
            "shouldn't have reference array of dynamically-sized element type", source_location
        )
    else:
        raise InternalError("Expected array", source_location)
    return r_count_vp, r_head_and_tail_vp


def _get_iterable_element_wtype(
    expr: awst_nodes.Expression,
    loc: SourceLocation,
) -> wtypes.WType:
    iter_wtype = expr.wtype
    if isinstance(iter_wtype, wtypes.ARC4Array):
        return iter_wtype.element_type
    elif isinstance(iter_wtype, wtypes.ARC4Tuple | wtypes.WTuple):
        element_type, *other_arc4 = set(iter_wtype.types)
        if other_arc4:
            raise CodeError("only homogenous tuples can be iterated", loc)
        return element_type
    elif isinstance(iter_wtype, wtypes.NativeArray):
        return iter_wtype.element_type
    else:
        raise CodeError("unsupported type for iteration", loc)


def _encode_n_items_as_arc4_items(
    context: IRFunctionBuildContext,
    items: Sequence[Value],
    item_ir_type: IRType,
    item_encoding: Encoding,
    loc: SourceLocation,
) -> list[Value]:
    source_types = (
        item_ir_type.elements if isinstance(item_ir_type, AggregateIRType) else (item_ir_type,)
    )
    item_arity = get_type_arity(item_ir_type)
    encoded_items = list[Value]()
    factory = OpFactory(context, loc)
    for item_start_idx in range(0, len(items), item_arity):
        if not isinstance(item_encoding, TupleEncoding):
            assert item_arity == 1, "expected scalar value"
            item_vp = encode_value_provider(
                context, items[item_start_idx], item_ir_type, item_encoding, loc
            )
            encoded_items.append(factory.assign(item_vp, "item"))
        else:
            arc4_items = _encode_arc4_tuple_items(
                context,
                list(items[item_start_idx : item_start_idx + item_arity]),
                source_types,
                item_encoding,
                loc,
            )
            encoded_items.append(
                factory.assign(
                    _encode_arc4_values_as_tuple(context, arc4_items, item_encoding, loc),
                    "encoded_tuple",
                )
            )

    return encoded_items


def pop_arc4_array(
    context: IRFunctionBuildContext,
    expr: awst_nodes.ArrayPop,
    array_wtype: wtypes.ARC4DynamicArray,
) -> ValueProvider:
    source_location = expr.source_location

    base = context.visitor.visit_and_materialise_single(expr.base)
    element_encoding = wtype_to_encoding(array_wtype.element_type)
    popped, data = invoke_arc4_array_pop(context, element_encoding, base, source_location)
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
    element_encoding: Encoding,
    base: Value,
    source_location: SourceLocation,
) -> tuple[Value, Value]:
    args: list[Value | int | bytes] = [base]
    if _bit_packed_bool(element_encoding):
        method_name = "dynamic_array_pop_bit"
    elif _is_byte_length_header(element_encoding):  # TODO: multi_byte_length prefix?
        method_name = "dynamic_array_pop_byte_length_head"
    elif element_encoding.is_dynamic:
        method_name = "dynamic_array_pop_dynamic_element"
    else:
        method_name = "dynamic_array_pop_fixed_size"
        args.append(element_encoding.checked_num_bytes)

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


# packed bits are packed starting with the left most bit
ARC4_TRUE = (1 << 7).to_bytes(1, "big")
ARC4_FALSE = (0).to_bytes(1, "big")


def _encode_arc4_bool(
    context: IRRegisterContext, bit: Value, source_location: SourceLocation
) -> Value:
    factory = OpFactory(context, source_location)
    value = factory.constant(0x00.to_bytes(1, "big"))
    return factory.set_bit(value=value, index=0, bit=bit, temp_desc="encoded_bool")


def _decode_arc4_tuple_items(
    context: IRRegisterContext,
    encoding: TupleEncoding,
    value: Value,
    target_type: AggregateIRType,
    source_location: SourceLocation,
) -> ValueProvider:
    factory = OpFactory(context, source_location)
    items = list[Value]()
    for index, (target_item_type, encoded_item_type) in enumerate(
        zip(target_type.elements, encoding.elements, strict=True)
    ):
        item_value = _read_nth_item_of_arc4_heterogeneous_container(
            context,
            array_head_and_tail=value,
            tuple_encoding=encoding,
            index=index,
            source_location=source_location,
        )
        item_name = f"item{index}"
        item_vp = maybe_decode_arc4_value_provider(
            context,
            item_value,
            encoding=encoded_item_type,
            target_type=target_item_type,
            temp_description=item_name,
            loc=source_location,
        )
        items.extend(factory.materialise(item_vp, item_name))
    return ValueTuple(source_location=source_location, values=items)


def _is_byte_length_header(encoding: Encoding) -> bool:
    if not isinstance(encoding, DynamicArrayEncoding) or not encoding.length_header:
        return False
    if _bit_packed_bool(encoding):
        return False
    return encoding.element.num_bytes == 1


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


def _encode_arc4_values_as_tuple(
    context: IRRegisterContext,
    elements: Sequence[Value],
    tuple_encoding: TupleEncoding,
    expr_loc: SourceLocation,
) -> ValueProvider:
    tuple_items = tuple_encoding.elements
    header_size = _get_arc4_tuple_head_size(tuple_items, round_end_result=True)
    factory = OpFactory(context, expr_loc)
    current_tail_offset = factory.assign(factory.constant(header_size // 8), "current_tail_offset")
    encoded_tuple_buffer = factory.assign(factory.constant(b""), "encoded_tuple_buffer")

    for index, (element, element_encoding) in enumerate(zip(elements, tuple_items, strict=True)):
        if _bit_packed_bool(element_encoding):
            # Pack boolean
            before_header = _get_arc4_tuple_head_size(tuple_items[0:index], round_end_result=False)
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
        elif element_encoding.is_dynamic:
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
        else:
            # Append value
            encoded_tuple_buffer = factory.concat(
                encoded_tuple_buffer, element, "encoded_tuple_buffer"
            )

    for element, element_encoding in zip(elements, tuple_items, strict=True):
        if element_encoding.is_dynamic:
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

    item_wtype = wtype.types[index_int]
    tuple_encoding = wtype_to_encoding(wtype)
    value_ir_type, _ = wtype_to_ir_type_and_encoding(item_wtype, source_location)
    return _arc4_replace_tuple_item(
        context, base_expr, index_int, tuple_encoding, value_ir_type, value, source_location
    )


def _arc4_replace_tuple_item(
    context: IRFunctionBuildContext,
    base_expr: awst_nodes.Expression,
    index_int: int,
    tuple_encoding: TupleEncoding,
    value_ir_type: IRType,
    value: ValueProvider,
    source_location: SourceLocation,
) -> Value:
    factory = OpFactory(context, source_location)
    tuple_items = tuple_encoding.elements
    base = context.visitor.visit_and_materialise_single(base_expr)
    value = factory.assign(value, "assigned_value")
    element_encoding = tuple_items[index_int]
    header_up_to_item = _get_arc4_tuple_head_size(
        tuple_items[0:index_int],
        round_end_result=not _bit_packed_bool(element_encoding),
    )

    # TODO: use ValueEncode
    if type_has_encoding(value_ir_type, element_encoding):
        value_vp = encode_value_provider(
            context,
            value,
            value_ir_type,
            element_encoding,
            source_location,
        )
        value = factory.assign(value_vp, "encoded")
    if _bit_packed_bool(element_encoding):
        # Use Set bit
        is_true = factory.get_bit(value, 0, "is_true")
        return factory.set_bit(
            value=base,
            index=header_up_to_item,
            bit=is_true,
            temp_desc="updated_data",
        )
    elif not element_encoding.is_dynamic:
        return factory.replace(
            base,
            header_up_to_item // 8,
            value,
            "updated_data",
        )
    else:
        assert element_encoding.is_dynamic, "expected dynamic encoding"
        dynamic_indices = [index for index, t in enumerate(tuple_items) if t.is_dynamic]

        item_offset = factory.extract_uint16(base, header_up_to_item // 8, "item_offset")
        data_up_to_item = factory.extract3(base, 0, item_offset, "data_up_to_item")
        dynamic_indices_after_item = [i for i in dynamic_indices if i > index_int]

        if not dynamic_indices_after_item:
            # This is the last dynamic type in the tuple
            # No need to update headers - just replace the data
            return factory.concat(data_up_to_item, value, "updated_data")
        header_up_to_next_dynamic_item = _get_arc4_tuple_head_size(
            tuple_items[: dynamic_indices_after_item[0]],
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
            header_up_to_dynamic_item = _get_arc4_tuple_head_size(
                tuple_items[:dynamic_index],
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
    context: IRRegisterContext,
    *,
    array_head_and_tail: Value,
    tuple_encoding: TupleEncoding,
    index: int,
    source_location: SourceLocation,
) -> ValueProvider:
    tuple_item_types = tuple_encoding.elements
    item_encoding = tuple_item_types[index]
    head_up_to_item = _get_arc4_tuple_head_size(tuple_item_types[:index], round_end_result=False)
    if _bit_packed_bool(item_encoding):
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
    if item_encoding.is_dynamic:
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
            if tuple_item_type.is_dynamic:
                head_up_to_next_dynamic_item = _get_arc4_tuple_head_size(
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
            encoding=item_encoding,
            source_location=source_location,
        )


def _read_nth_bool_from_arc4_container(
    context: IRRegisterContext,
    *,
    data: Value,
    index: Value,
    source_location: SourceLocation,
) -> ValueProvider:
    # index is the bit position
    factory = OpFactory(context, source_location)
    is_true = factory.get_bit(data, index, "is_true")
    return _encode_arc4_bool(context, is_true, source_location)


def _read_static_item_from_arc4_container(
    *,
    data: Value,
    offset: Value,
    encoding: Encoding,
    source_location: SourceLocation,
) -> ValueProvider:
    item_length = UInt64Constant(value=encoding.checked_num_bytes, source_location=source_location)
    return Intrinsic(
        op=AVMOp.extract3,
        args=[data, offset, item_length],
        source_location=source_location,
        error_message="Index access is out of bounds",
    )


def _get_arc4_array_tail_data_and_item_count(
    context: IRFunctionBuildContext,
    expr: awst_nodes.Expression,
    element_encoding: Encoding,
    element_ir_type: IRType,
    source_location: SourceLocation,
) -> tuple[Value, Value]:
    """
    For supported iterable types, will return the ARC-4 tail data and item count,
    doing any necessary ARC-4 encoding.
    """

    factory = OpFactory(context, source_location)

    wtype = expr.wtype
    if isinstance(wtype, wtypes.WTuple):
        native_values = context.visitor.visit_and_materialise(expr)
        if element_ir_type == EncodedType(element_encoding):
            encoded_values = native_values
        else:
            encoded_values = _encode_n_items_as_arc4_items(
                context,
                native_values,
                item_ir_type=element_ir_type,
                item_encoding=element_encoding,
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
    elif isinstance(wtype, wtypes.ARC4Array | wtypes.StackArray | wtypes.ReferenceArray):
        array_encoding = wtype_to_encoding(wtype)
        item_count_vp = get_array_length(context, array_encoding, stack_value, source_location)
        item_count = factory.assign(item_count_vp, "array_length")
        if array_encoding.element != element_encoding:
            raise InternalError("encodings do not match", source_location)
        head_and_tail_vp = _get_arc4_array_head_and_tail(
            array_encoding, stack_value, source_location
        )
        head_and_tail = factory.assign(head_and_tail_vp, "array_head_and_tail")
    else:
        raise InternalError(f"Unsupported array type: {wtype}")

    tail_data = _get_arc4_array_tail(
        context,
        element_encoding=element_encoding,
        array_head_and_tail=head_and_tail,
        array_length=item_count,
        source_location=source_location,
    )
    return tail_data, item_count


def _encode_native_uint64_to_arc4(
    context: IRRegisterContext, value: Value, num_bytes: int, source_location: SourceLocation
) -> ValueProvider:
    assert value.atype == AVMType.uint64, "function expects a native uint64 type to encode"
    factory = OpFactory(context, source_location)
    val_as_bytes = factory.itob(value, "val_as_bytes")
    # encoding to n==64: no checks or padding required
    if num_bytes == 8:
        return val_as_bytes
    # encoding to n>64, just need to pad
    if num_bytes > 8:
        return factory.pad_bytes(val_as_bytes, num_bytes=num_bytes, temp_desc="arc4_encoded")
    # encoding to n<64, need to check for overflow and then trim
    bit_len = factory.bitlen(val_as_bytes, "bitlen")
    no_overflow = factory.lte(bit_len, num_bytes * 8, "no_overflow")
    assert_value(context, no_overflow, source_location=source_location, error_message="overflow")
    return factory.extract3(val_as_bytes, 8 - num_bytes, num_bytes, f"uint{num_bytes*8}")


def arc4_replace_array_item(
    context: IRFunctionBuildContext,
    *,
    base_expr: awst_nodes.Expression,
    index_value_expr: awst_nodes.Expression,
    array_encoding: ArrayEncoding,
    element_ir_type: IRType,
    value_vp: ValueProvider,
    source_location: SourceLocation,
) -> Value:
    factory = OpFactory(context, source_location)
    base = context.visitor.visit_and_materialise_single(base_expr)
    element_encoding = array_encoding.element

    # TODO: use ValueEncode
    if not type_has_encoding(element_ir_type, element_encoding):
        encoded_vp = encode_value_provider(
            context, value_vp, element_ir_type, element_encoding, source_location
        )
        value: Value = factory.assign(encoded_vp, "encoded")
    else:
        (value,) = context.visitor.materialise_value_provider(value_vp, "assigned_value")

    index = context.visitor.visit_and_materialise_single(index_value_expr)

    def updated_result(method_name: str, args: list[Value | int | bytes]) -> Register:
        invoke = _invoke_puya_lib_subroutine(
            context,
            full_name=f"_puya_lib.arc4.{method_name}",
            args=args,
            source_location=source_location,
        )
        return factory.assign(invoke, "updated_value")

    if _is_byte_length_header(element_encoding):
        if isinstance(array_encoding, FixedArrayEncoding):
            return updated_result(
                "static_array_replace_byte_length_head", [base, value, index, array_encoding.size]
            )
        else:
            return updated_result("dynamic_array_replace_byte_length_head", [base, value, index])
    elif element_encoding.is_dynamic:
        if isinstance(array_encoding, FixedArrayEncoding):
            return updated_result(
                "static_array_replace_dynamic_element", [base, value, index, array_encoding.size]
            )
        elif isinstance(array_encoding, DynamicArrayEncoding) and array_encoding.length_header:
            return updated_result("dynamic_array_replace_dynamic_element", [base, value, index])
    array_length_vp = get_array_length(context, array_encoding, base, source_location)
    array_length = factory.assign(array_length_vp, "array_length")
    _assert_index_in_bounds(context, index, array_length, source_location)
    assert element_encoding.num_bytes is not None, "expected static element"

    if _bit_packed_bool(element_encoding):
        element_num_bits = 1
    else:
        element_num_bits = element_encoding.num_bytes * 8
    dynamic_offset = 0 if isinstance(array_encoding, FixedArrayEncoding) else 2
    if element_num_bits == 1:
        dynamic_offset *= 8  # convert offset to bits
        offset_per_item = element_num_bits
    else:
        offset_per_item = element_num_bits // 8

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

    if element_num_bits == 1:
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
            case wtypes.ARC4StaticArray() | wtypes.ARC4Tuple():
                return context.visitor.visit_and_materialise_single(expr)
            case wtypes.ARC4DynamicArray() | wtypes.StackArray():
                expr_value = context.visitor.visit_and_materialise_single(expr)
                return factory.extract_to_end(expr_value, 2, "expr_value_trimmed")
            case wtypes.WTuple(types=types):
                element_encoding = wtype_to_encoding(types[0])
                return get_array_encoded_items(
                    context,
                    expr,
                    DynamicArrayEncoding(length_header=False, element=element_encoding),
                )
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
    encoding: Encoding,
    items: Sequence[Value],
    source_location: SourceLocation,
) -> Value:
    factory = OpFactory(context, source_location)
    result = factory.constant(b"")
    if encoding.is_dynamic:
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
        error_message="Index access is out of bounds",
        source_location=source_location,
    )


def _get_arc4_array_head_and_tail(
    encoding: ArrayEncoding,
    array: Value,
    source_location: SourceLocation,
) -> ValueProvider:
    match encoding:
        case FixedArrayEncoding() | DynamicArrayEncoding(length_header=False):
            return array
        case DynamicArrayEncoding(length_header=True):
            return Intrinsic(
                op=AVMOp.extract,
                args=[array],
                immediates=[2, 0],
                source_location=source_location,
            )
        case _:
            raise InternalError("Unexpected ARC-4 array type", source_location)


def _get_arc4_array_tail(
    context: IRFunctionBuildContext,
    *,
    element_encoding: Encoding,
    array_length: Value,
    array_head_and_tail: Value,
    source_location: SourceLocation,
) -> Value:
    if not element_encoding.is_dynamic:
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


def _get_arc4_tuple_head_size(encodings: Sequence[Encoding], *, round_end_result: bool) -> int:
    bit_size = 0
    for encoding, next_encoding in zip_longest(encodings, encodings[1:]):
        if encoding.is_dynamic:
            size = 16
        elif _bit_packed_bool(encoding):
            size = 1
        else:
            size = encoding.checked_num_bytes * 8
        bit_size += size
        if (
            _bit_packed_bool(encoding)
            and next_encoding != encoding
            and (round_end_result or next_encoding)
        ):
            bit_size = round_bits_to_nearest_bytes(bit_size)
    return bit_size
