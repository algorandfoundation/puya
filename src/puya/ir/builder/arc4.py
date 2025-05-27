import abc
import typing
from collections.abc import Sequence
from itertools import zip_longest

from puya import log
from puya.avm import AVMType
from puya.errors import InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import (
    OpFactory,
    assert_value,
    undefined_value,
)
from puya.ir.encodings import (
    ArrayEncoding,
    BoolEncoding,
    DynamicArrayEncoding,
    Encoding,
    FixedArrayEncoding,
    TupleEncoding,
    UIntEncoding,
    UTF8Encoding,
)
from puya.ir.models import (
    BigUIntConstant,
    Intrinsic,
    MultiValue,
    UInt64Constant,
    Undefined,
    Value,
    ValueEncode,
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
)
from puya.parse import SourceLocation
from puya.utils import round_bits_to_nearest_bytes

logger = log.get_logger(__name__)

# packed bits are packed starting with the left most bit
ARC4_TRUE = (1 << 7).to_bytes(1, "big")
ARC4_FALSE = (0).to_bytes(1, "big")


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
        head = factory.constant(b"")
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
                    bytes_to_set = head if bit_index else ARC4_FALSE
                    value = factory.set_bit(value=bytes_to_set, index=bit_index, bit=value)
                    # if bit_index is not 0, then just update encoded and continue
                    # as there is nothing to concat
                    if bit_index:
                        head = value
                        continue
                else:
                    # value is already encoded, so do nothing
                    if type_has_encoding(native_element, BoolEncoding):
                        pass
                    elif value.atype == AVMType.uint64:
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
                    else:
                        raise InternalError(
                            f"unexpected value for encoding bool,"
                            f" {native_element=}, {element_encoding=}",
                            loc,
                        )
                    bit_packed_index = 0
            else:
                element_arity = get_type_arity(native_element)
                if element_arity == 1:
                    element_value_or_tuple: Value | ValueTuple = values.pop(0)
                else:
                    element_values = values[:element_arity]
                    values = values[element_arity:]
                    element_value_or_tuple = ValueTuple(values=element_values, source_location=loc)
                if type_has_encoding(native_element, element_encoding):
                    assert isinstance(element_value_or_tuple, Value), "expected Value"
                    value = element_value_or_tuple
                else:
                    encoded_element_vp = encode_value(
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
            head = factory.concat(head, value, "encoded", ir_type=encoded_ir_type)
        if values:
            raise InternalError(
                f"unexpected remaining values for array encoding:"
                f" {len(values)=}, {self.native_type=}, {encoding=}",
                loc,
            )
        if isinstance(encoding, ArrayEncoding) and encoding.length_header:
            len_u16 = factory.as_u16_bytes(len(native_elements), "len_u16")
            head = factory.concat(len_u16, head, "encoded")
        encoded = factory.concat(head, tail, "encoded", ir_type=EncodedType(encoding))
        return encoded

    @typing.override
    def decode(
        self,
        context: IRRegisterContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        from puya.ir.builder.tup import EncodedTupleBuilder

        item_types = self.native_type.elements
        match encoding:
            case TupleEncoding(elements=elements) as tuple_encoding if len(elements) == len(
                item_types
            ):
                pass
            case FixedArrayEncoding(element=element, size=size) if size == len(item_types):
                tuple_encoding = TupleEncoding([element] * size)
            case _:
                return None
        builder = EncodedTupleBuilder(
            context, tuple_encoding=tuple_encoding, tuple_ir_type=self.native_type, loc=loc
        )

        factory = OpFactory(context, loc)
        items = list[Value]()
        for index in range(len(tuple_encoding.elements)):
            item = builder.read_at_index(value, index)
            items.extend(factory.materialise_values(item, f"item{index}"))
        return ValueTuple(values=items, source_location=loc)


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
        result = self.encode_value(context, value, encoding, loc)
        if result is None:
            return None
        return factory.as_ir_type(result, EncodedType(encoding))

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
                factory = OpFactory(context, loc)
                # TODO: compare with select implementation
                false = factory.constant(ARC4_FALSE)
                return factory.set_bit(value=false, index=0, bit=value, temp_desc="encoded_bool")
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


def _get_arc4_codec(ir_type: IRType | TupleIRType) -> ARC4Codec | None:
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


def maybe_decode_value(
    context: IRRegisterContext,
    encoded_item: Value,
    encoding: Encoding,
    target_type: IRType | TupleIRType,
    loc: SourceLocation,
) -> MultiValue:
    factory = OpFactory(context, loc)
    encoded_item = factory.materialise_single(encoded_item, "encoded_item")
    if encoded_item.ir_type.avm_type == AVMType.uint64 and type_has_encoding(
        target_type, BoolEncoding(packed=False)
    ):
        # awkward case of bool1 -> bool8
        return factory.materialise_single(
            ValueEncode(
                values=[encoded_item],
                encoding=BoolEncoding(packed=False),
                value_type=PrimitiveIRType.bool,
                source_location=loc,
            )
        )
    if type_has_encoding(target_type, encoding):
        # no decoding required
        return encoded_item
    else:
        # otherwise do a decode
        return factory.materialise_multi_value(
            decode_value(
                context,
                value=encoded_item,
                encoding=encoding,
                target_type=target_type,
                loc=loc,
            )
        )


def decode_value(
    context: IRRegisterContext,
    value: Value,
    encoding: Encoding,
    target_type: IRType | TupleIRType,
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


# TODO: this becomes the lowering implementation for ir.ValueEncode
def encode_value(
    context: IRRegisterContext,
    value_provider: ValueProvider,
    value_type: IRType | TupleIRType,
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


def write_tuple_index(
    context: IRRegisterContext,
    base: Value,
    index_int: int,
    tuple_encoding: TupleEncoding,
    value_ir_type: IRType | TupleIRType,
    value: ValueProvider,
    source_location: SourceLocation,
) -> Value:
    factory = OpFactory(context, source_location)
    tuple_items = tuple_encoding.elements
    value = factory.materialise_single(value, "assigned_value")
    element_encoding = tuple_items[index_int]
    header_up_to_item = _get_arc4_tuple_head_size(
        tuple_items[0:index_int],
        round_end_result=not _bit_packed_bool(element_encoding),
    )

    # TODO: use ValueEncode
    if not type_has_encoding(value_ir_type, element_encoding):
        value_vp = encode_value(
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


def _bit_packed_bool(encoding: Encoding) -> typing.TypeGuard[BoolEncoding]:
    return isinstance(encoding, BoolEncoding) and encoding.packed


def _encoding_or_name(typ: IRType | TupleIRType) -> str:
    if isinstance(typ, EncodedType):
        return typ.encoding.name
    else:
        return typ.name


def _encode_native_uint64_to_arc4(
    context: IRRegisterContext, value: Value, num_bytes: int, source_location: SourceLocation
) -> Value:
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
