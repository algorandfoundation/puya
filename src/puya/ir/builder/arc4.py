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
from puya.ir._puya_lib import PuyaLibIR
from puya.ir.arc4_types import (
    maybe_wtype_to_arc4_wtype,
    wtype_to_arc4_wtype,
)
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import sequence
from puya.ir.builder._utils import (
    OpFactory,
    assert_value,
    assign_intrinsic_op,
    assign_targets,
    invoke_puya_lib_subroutine,
    mktemp,
    undefined_value,
)
from puya.ir.builder.arrays import (
    get_array_encoded_items,
    get_array_length,
)
from puya.ir.builder.assignment import handle_assignment
from puya.ir.builder.mem import read_slot
from puya.ir.context import IRFunctionBuildContext
from puya.ir.encodings import (
    ArrayEncoding,
    BoolEncoding,
    DynamicArrayEncoding,
    Encoding,
    FixedArrayEncoding,
    TupleEncoding,
    UIntEncoding,
    UTF8Encoding,
    wtype_to_encoding,
)
from puya.ir.models import (
    BigUIntConstant,
    Intrinsic,
    UInt64Constant,
    Undefined,
    Value,
    ValueProvider,
    ValueTuple,
)
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import (
    EncodedType,
    IRType,
    PrimitiveIRType,
    SizedBytesType,
    TupleIRType,
    get_type_arity,
    type_has_encoding,
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
    if type_has_encoding(target_type, encoding):
        return value_provider
    factory = OpFactory(context, loc)
    value = factory.materialise_single(value_provider, temp_description)
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
    def __init__(self, native_type: TupleIRType):
        self.native_type = native_type
        self.homogenous = len(set(self.native_type.elements)) == 1

    @typing.override
    def encode(
        self,
        context: IRRegisterContext,
        value_provider: ValueProvider,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        native_elements = self.native_type.elements
        match encoding:
            case TupleEncoding(elements=element_encodings) if len(element_encodings) == len(
                native_elements
            ):
                pass
            case FixedArrayEncoding(element=element_encoding, size=size) if size == len(
                native_elements
            ):
                element_encodings = [element_encoding] * size
            case DynamicArrayEncoding(element=element_encoding):
                element_encodings = [element_encoding] * len(native_elements)
            case _:
                return None
        factory = OpFactory(context, loc)
        bit_packed_index = 0
        current_head_offset = 0
        values = list(factory.materialise_values(value_provider, "to_encode"))
        encoded = factory.constant(b"")
        tail = factory.constant(b"")
        processed_encodings = list[Encoding]()
        header_size = _get_arc4_tuple_head_size(element_encodings, round_end_result=True)
        current_tail_offset = factory.constant(header_size // 8)
        for native_element, element_encoding in zip(
            native_elements, element_encodings, strict=True
        ):
            # special handling to bitpack consecutive bools, this will bit pack both native bools
            # and ARC-4 bools
            if _bit_packed_bool(element_encoding):
                value = values.pop(0)
                # sequential bits in the same tuple are bit-packed
                if processed_encodings and processed_encodings[-1] == element_encoding:
                    # ensure value is a bool
                    if type_has_encoding(native_element, BoolEncoding):
                        value = factory.get_bit(value, 0)
                    elif value.atype != AVMType.uint64:
                        raise InternalError(
                            f"unexpected value for encoding bool,"
                            f" {native_element=}, {element_encoding=}",
                            loc,
                        )
                    bit_packed_index += 1
                    bit_index = bit_packed_index % 8
                    if bit_index:
                        bit_index += (current_head_offset - 1) * 8
                    bytes_to_set = encoded if bit_index else ARC4_FALSE
                    value = factory.set_bit(value=bytes_to_set, index=bit_index, bit=value)
                    # if bit_index is not 0, then just update encoded and continue
                    # as there is nothing to concat
                    if bit_index:
                        encoded = value
                        continue
                else:
                    # value is already encoded, so do nothing
                    if type_has_encoding(native_element, BoolEncoding):
                        pass
                    elif value.atype != AVMType.uint64:
                        raise InternalError(
                            f"unexpected value for encoding bool,"
                            f" {native_element=}, {element_encoding=}",
                            loc,
                        )
                    else:
                        value = factory.set_bit(
                            value=ARC4_FALSE, index=0, bit=value, temp_desc="encoded_bit"
                        )
                        # value = factory.select(
                        #    false=ARC4_FALSE,
                        #    true=ARC4_TRUE,
                        #    condition=value,
                        #    ir_type=PrimitiveIRType.bytes,
                        #    temp_desc="encoded_bit",
                        # )
                    bit_packed_index = 0
            else:
                element_arity = get_type_arity(native_element)
                if element_arity == 1:
                    element_value_or_tuple: Value | ValueTuple = values.pop(0)
                else:
                    element_values = values[:element_arity]
                    values = values[element_arity:]
                    element_value_or_tuple = ValueTuple(values=element_values, source_location=loc)
                encoded_element_vp = encode_value_provider(
                    context, element_value_or_tuple, native_element, element_encoding, loc
                )
                value = factory.materialise_single(encoded_element_vp, "encoded_sub_item")
                if element_encoding.is_dynamic:
                    # append value to tail
                    tail = factory.concat(tail, value, "tail")

                    # update offset
                    data_length = factory.len(value, "data_length")
                    new_current_tail_offset = factory.add(
                        current_tail_offset, data_length, "current_tail_offset"
                    )
                    # value is tail offset
                    value = factory.as_u16_bytes(current_tail_offset, "offset_as_uint16")
                    current_tail_offset = new_current_tail_offset
                    current_head_offset += 2
            if not element_encoding.is_dynamic:
                current_head_offset += element_encoding.checked_num_bytes
            processed_encodings.append(element_encoding)
            encoded_ir_type = EncodedType(TupleEncoding(processed_encodings))
            encoded = factory.concat(encoded, value, "encoded", ir_type=encoded_ir_type)
        if values:
            raise InternalError(
                f"unexpected remaining values for array encoding:"
                f" {len(values)=}, {self.native_type=}, {encoding=}",
                loc,
            )
        encoded = factory.concat(encoded, tail, "encoded")
        if isinstance(encoding, DynamicArrayEncoding) and encoding.length_header:
            len_u16 = factory.as_u16_bytes(len(native_elements), "len_u16")
            encoded = factory.concat(len_u16, encoded, "encoded", ir_type=EncodedType(encoding))
        return encoded

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
            case FixedArrayEncoding(element=element, size=size) if size == len(item_types):
                elements = [element] * size
            case _:
                return None
        return _decode_arc4_tuple_items(
            context, elements, value, target_type=self.native_type, source_location=loc
        )
        # TODO: is this any better?
        """
        factory = OpFactory(context, loc)
        bit_offset = offset = 0
        values = []
        last_sub_typ = None
        for encoded_sub_type, group_id in expand_encoded_type_and_group(element_type):
            # special handling for bit-packed bools in aggregate types
            (sub_type,) = encoded_ir_type_to_ir_types(encoded_sub_type)
            if sub_type == PrimitiveIRType.bool and element_type != PrimitiveIRType.bool:
                if last_sub_typ == (sub_type, group_id):
                    bit_offset += 1
                sub_item = factory.get_bit(item_bytes, offset * 8 + bit_offset, "sub_item")
            else:
                sub_type_size = _get_element_size(encoded_sub_type, loc)
                bit_offset = 0
                sub_item = factory.extract3(item_bytes, offset, sub_type_size, "sub_item")
                if sub_type.avm_type == AVMType.uint64:
                    sub_item = factory.btoi(sub_item, "sub_item")
                offset += sub_type_size
            # also increment offset if we reach the end of a bit-packed byte
            if bit_offset % 8 == 7:
                bit_offset = 0
                offset += 1
            last_sub_typ = sub_type, group_id
            values.append(sub_item)
        if len(values) == 1:
            return values[0]
        else:
            return ValueTuple(values=values, source_location=loc)
        """


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
        (value,) = factory.materialise_values(value_provider, "to_encode")
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
            case UIntEncoding():
                factory = OpFactory(context, loc)
                return factory.to_fixed_size(
                    value,
                    num_bytes=encoding.checked_num_bytes,
                    temp_desc="arc4_encoded",
                    error_message="overflow",
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
    def __init__(self, element: UIntEncoding | UTF8Encoding):
        self.element = element

    @typing.override
    def encode_value(
        self,
        context: IRRegisterContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        factory = OpFactory(context, loc)
        match encoding:
            case DynamicArrayEncoding(
                element=element, length_header=True
            ) if element == self.element:
                length = factory.len(value, "length")
                length_uint16 = factory.as_u16_bytes(length, "length_uint16")
                return factory.concat(length_uint16, value, "encoded_value")
            case DynamicArrayEncoding(
                element=element, length_header=False
            ) if element == self.element:
                return value
            case FixedArrayEncoding(element=element, size=num_bytes) if element == self.element:
                length = factory.len(value, "length")
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
        match encoding:
            case DynamicArrayEncoding(
                element=element, length_header=True
            ) if element == self.element:
                return Intrinsic(
                    op=AVMOp.extract, immediates=[2, 0], args=[value], source_location=loc
                )
            case ArrayEncoding(element=element) if element == self.element:
                return value
        return None


# TODO: work out if we need these codecs
"""
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


class CheckedEncoding(ARC4Codec):
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
        if type_has_encoding(self.native_type, encoding):
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
        if type_has_encoding(self.native_type, encoding):
            return value
        return None


def _get_arc4_codec(ir_type: IRType) -> ARC4Codec | None:
    match ir_type:
        case TupleIRType() as aggregate:
            return NativeTupleCodec(aggregate)
        case PrimitiveIRType.biguint:
            return BigUIntCodec()
        case PrimitiveIRType.bool:
            return BoolCodec()
        case PrimitiveIRType.string:
            return BytesCodec(UTF8Encoding())
        case EncodedType():
            # TODO: this is the equivalent to the old StackArray check
            #       but probably isn't necessary any more
            return CheckedEncoding(ir_type)
        case PrimitiveIRType.bytes | SizedBytesType():
            return BytesCodec(UIntEncoding(n=8))
        case _ if ir_type.maybe_avm_type == AVMType.uint64:
            return UInt64Codec()
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
    if type_has_encoding(target_type, BoolEncoding) and isinstance(encoding, BoolEncoding):
        logger.warning(
            f"TODO: ignoring bool packing for {_encoding_or_name(target_type)}, {encoding=!s}",
            location=loc,
        )
        return value
    codec = _get_arc4_codec(target_type)
    if codec is not None:
        result = codec.decode(context, value, encoding, loc)
        if result is not None:
            return result
    logger.error(
        f"cannot decode from {encoding!s} to {_encoding_or_name(target_type)}",
        location=loc,
    )
    return undefined_value(target_type, loc)


def _encoding_or_name(typ: IRType) -> str:
    if isinstance(typ, EncodedType):
        return typ.encoding.name
    else:
        return typ.name


# TODO: this becomes the lowering implementation for ir.ValueEncode
def encode_value_provider(
    context: IRRegisterContext,
    value_provider: ValueProvider,
    value_type: IRType,
    encoding: Encoding,
    loc: SourceLocation,
) -> ValueProvider:
    if type_has_encoding(value_type, encoding):
        logger.debug(
            f"redundant encode operation from {_encoding_or_name(value_type)} to {encoding!s}",
            location=loc,
        )
        return value_provider
    if type_has_encoding(value_type, BoolEncoding) and isinstance(encoding, BoolEncoding):
        logger.warning(
            f"TODO: ignoring bool packing for {_encoding_or_name(value_type)}, {encoding=!s}",
            location=loc,
        )
        return value_provider
    codec = _get_arc4_codec(value_type)

    if codec is not None:
        result = codec.encode(context, value_provider, encoding, loc)
        if result is not None:
            return result
    logger.error(f"cannot encode {_encoding_or_name(value_type)} to {encoding!s}", location=loc)
    return Undefined(
        ir_type=PrimitiveIRType.bytes,
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
        (encoded_item,) = factory.materialise_values(encoded_item_vp, "arc4_item")
        encoded_items.append(encoded_item)
    return encoded_items


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
        tuple_item_types=tuple_encoding.elements,
        index=index,
        source_location=source_location,
    )
    # TODO: use ValueDecode
    if not type_has_encoding(item_ir_type, item_encoding):
        factory = OpFactory(context, source_location)
        encoded = factory.materialise_single(result, "encoded")
        result = decode_arc4_value(context, encoded, item_encoding, item_ir_type, source_location)
    return result


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
            array = context.visitor.visit_and_materialise_single(base_expr)
            index = context.visitor.visit_and_materialise_single(index_value)
            builder = sequence.get_sequence_builder(context, array_wtype, source_location)
            item = builder.write_at_index(array, index, value)
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
            tuple_encoding = wtype_to_encoding(tuple_wtype, source_location)
            value_ir_type = wtype_to_ir_type(
                tuple_wtype.types[index_value],
                source_location=source_location,
                allow_aggregate=True,
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
    element_encoding = array_encoding.element

    right_element_ir_type, right_element_encoding = _get_iterable_element_type_and_encoding(
        iter_expr.wtype, array_encoding, source_location
    )

    if not element_encoding.is_dynamic and not _bit_packed_bool(element_encoding):
        # TODO: ir.ArrayConcat
        return _concat_dynamic_array_fixed_size(
            context,
            left=array_expr,
            right=iter_expr,
            source_location=source_location,
            byte_size=element_encoding.checked_num_bytes,
        )

    left = context.visitor.visit_and_materialise_single(array_expr)
    if _bit_packed_bool(element_encoding):
        assert isinstance(right_element_encoding, BoolEncoding)
        if right_element_encoding.packed:
            # bits are already packed
            read_step = 1
        else:
            # each bit is in its own byte
            read_step = 8
        (r_data, r_length) = _get_arc4_array_tail_data_and_item_count(
            context, iter_expr, right_element_encoding, right_element_ir_type, source_location
        )
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
            factory.materialise_values_by_name(
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
    invoke = invoke_puya_lib_subroutine(
        context,
        full_name=PuyaLibIR(f"_puya_lib.arc4.{invoke_name}"),
        args=invoke_args,
        source_location=source_location,
    )
    return factory.materialise_single(invoke, "concat_result")


def _bit_packed_bool(encoding: Encoding) -> typing.TypeGuard[BoolEncoding]:
    return isinstance(encoding, BoolEncoding) and encoding.packed


def _extract_dynamic_element_count_head_and_tail(
    context: IRFunctionBuildContext,
    array_encoding: ArrayEncoding,
    iter_expr: awst_nodes.Expression,
    source_location: SourceLocation,
) -> tuple[ValueProvider, ValueProvider]:
    iter_wtype = iter_expr.wtype
    if isinstance(iter_wtype, wtypes.ARC4Array | wtypes.StackArray):
        right = context.visitor.visit_and_materialise_single(iter_expr)
        r_count_vp = get_array_length(context, array_encoding, right, source_location)
        r_head_and_tail_vp = _get_arc4_array_head_and_tail(array_encoding, right, source_location)
    elif isinstance(iter_wtype, wtypes.WTuple):
        r_count_vp = UInt64Constant(value=len(iter_wtype.types), source_location=source_location)
        right_values = context.visitor.visit_and_materialise(iter_expr)
        element_ir_type, element_encoding = _get_iterable_element_type_and_encoding(
            iter_wtype, array_encoding, source_location
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


def _get_iterable_element_type_and_encoding(
    iter_wtype: wtypes.WType,
    array_encoding: ArrayEncoding,
    loc: SourceLocation,
) -> tuple[IRType, Encoding]:
    if isinstance(iter_wtype, wtypes.ARC4Array | wtypes.NativeArray):
        element_wtype = iter_wtype.element_type
        element_ir_type = wtype_to_ir_type(element_wtype, loc, allow_aggregate=True)
        # note: need to use iter wtype to determine encoding,
        # as the aggregate type affects the encoding
        element_encoding = wtype_to_encoding(iter_wtype, loc).element
    elif isinstance(iter_wtype, wtypes.ARC4Tuple | wtypes.WTuple):
        element_wtype, *other_arc4 = set(iter_wtype.types)
        if other_arc4:
            raise CodeError("only homogenous tuples can be iterated", loc)
        element_ir_type = wtype_to_ir_type(element_wtype, loc, allow_aggregate=True)
        element_encoding = wtype_to_encoding(element_wtype, loc)
    else:
        raise CodeError("unsupported type for iteration", loc)

    if array_encoding.element == element_encoding:
        # encodings are compatible
        pass
    elif _bit_packed_bool(array_encoding.element) and isinstance(element_encoding, BoolEncoding):
        # bit packed bools can handle non bit packed bools
        pass
    else:
        raise CodeError("unsupported element type for concatenation", loc)
    return element_ir_type, element_encoding


def _encode_n_items_as_arc4_items(
    context: IRRegisterContext,
    items: Sequence[Value],
    item_ir_type: IRType,
    item_encoding: Encoding,
    loc: SourceLocation,
) -> list[Value]:
    source_types = (
        item_ir_type.elements if isinstance(item_ir_type, TupleIRType) else (item_ir_type,)
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
            encoded_items.append(factory.materialise_single(item_vp, "item"))
        else:
            arc4_items = _encode_arc4_tuple_items(
                context,
                list(items[item_start_idx : item_start_idx + item_arity]),
                source_types,
                item_encoding,
                loc,
            )
            encoded_items.append(
                factory.materialise_single(
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
    array_encoding = wtype_to_encoding(array_wtype, source_location)
    popped, data = invoke_arc4_array_pop(context, array_encoding, base, source_location)
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
    array_encoding: DynamicArrayEncoding,
    base: Value,
    source_location: SourceLocation,
) -> tuple[Value, Value]:
    element_encoding = array_encoding.element
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
        source=invoke_puya_lib_subroutine(
            context,
            full_name=PuyaLibIR(f"_puya_lib.arc4.{method_name}"),
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
    # TODO: compare with select implementation
    value = factory.constant(0x00.to_bytes(1, "big"))
    return factory.set_bit(value=value, index=0, bit=bit, temp_desc="encoded_bool")


def _decode_arc4_tuple_items(
    context: IRRegisterContext,
    tuple_elements: Sequence[Encoding],
    value: Value,
    target_type: TupleIRType,
    source_location: SourceLocation,
) -> ValueProvider:
    factory = OpFactory(context, source_location)
    items = list[Value]()
    for index, (target_item_type, encoded_item_type) in enumerate(
        zip(target_type.elements, tuple_elements, strict=True)
    ):
        item_value = _read_nth_item_of_arc4_heterogeneous_container(
            context,
            array_head_and_tail=value,
            tuple_item_types=tuple_elements,
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
        items.extend(factory.materialise_values(item_vp, item_name))
    return ValueTuple(source_location=source_location, values=items)


def _is_byte_length_header(encoding: Encoding) -> bool:
    if not isinstance(encoding, DynamicArrayEncoding) or not encoding.length_header:
        return False
    if _bit_packed_bool(encoding):
        return False
    return encoding.element.num_bytes == 1


def _encode_arc4_values_as_tuple(
    context: IRRegisterContext,
    elements: Sequence[Value],
    tuple_encoding: TupleEncoding,
    expr_loc: SourceLocation,
) -> ValueProvider:
    tuple_items = tuple_encoding.elements
    header_size = _get_arc4_tuple_head_size(tuple_items, round_end_result=True)
    factory = OpFactory(context, expr_loc)
    current_tail_offset = factory.constant(header_size // 8)
    encoded_tuple_buffer = factory.constant(b"")

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
    tuple_encoding = wtype_to_encoding(wtype, source_location)
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
    value = factory.materialise_single(value, "assigned_value")
    element_encoding = tuple_items[index_int]
    header_up_to_item = _get_arc4_tuple_head_size(
        tuple_items[0:index_int],
        round_end_result=not _bit_packed_bool(element_encoding),
    )

    # TODO: use ValueEncode
    if not type_has_encoding(value_ir_type, element_encoding):
        value_vp = encode_value_provider(
            context,
            value,
            value_ir_type,
            element_encoding,
            source_location,
        )
        value = factory.materialise_single(value_vp, "encoded")
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
    tuple_item_types: Sequence[Encoding],
    index: int,
    source_location: SourceLocation,
) -> ValueProvider:
    item_encoding = tuple_item_types[index]
    head_up_to_item = _get_arc4_tuple_head_size(tuple_item_types[:index], round_end_result=False)
    if _bit_packed_bool(item_encoding):
        return _read_and_decode_nth_bool_from_arc4_container(
            context,
            data=array_head_and_tail,
            index=UInt64Constant(
                value=head_up_to_item,
                source_location=source_location,
            ),
            # TODO: at the moment this can result in double handling
            target_ir_type=EncodedType(BoolEncoding(packed=False)),
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


def _read_and_decode_nth_bool_from_arc4_container(
    context: IRRegisterContext,
    *,
    data: Value,
    index: Value,
    target_ir_type: IRType,
    source_location: SourceLocation,
) -> Value:
    # index is the bit position
    factory = OpFactory(context, source_location)
    item = factory.get_bit(data, index, "is_true")
    if type_has_encoding(target_ir_type, BoolEncoding):
        return _encode_arc4_bool(context, item, source_location)
    elif target_ir_type != PrimitiveIRType.bool:
        raise InternalError("unexpected target_ir_type for bool", source_location)
    else:
        return item


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
        if type_has_encoding(element_ir_type, element_encoding):
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
        array_encoding = wtype_to_encoding(wtype, source_location)
        if isinstance(wtype, wtypes.ReferenceArray):
            array = read_slot(context, stack_value, source_location)
        else:
            array = stack_value
        item_count_vp = get_array_length(context, array_encoding, array, source_location)
        item_count = factory.materialise_single(item_count_vp, "array_length")
        if array_encoding.element != element_encoding and not _bit_packed_bool(
            array_encoding.element
        ):
            raise InternalError(
                f"encodings do not match {array_encoding.element=}, {element_encoding=}",
                source_location,
            )
        head_and_tail_vp = _get_arc4_array_head_and_tail(array_encoding, array, source_location)
        head_and_tail = factory.materialise_single(head_and_tail_vp, "array_head_and_tail")
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
                element_encoding = wtype_to_encoding(types[0], expr.source_location)
                return get_array_encoded_items(
                    context,
                    expr,
                    element_encoding,
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
    context: IRRegisterContext,
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
