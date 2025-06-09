import abc
import typing
from collections.abc import Sequence

from puya import log
from puya.avm import AVMType
from puya.errors import InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import (
    undefined_value,
)
from puya.ir.builder.sequence import requires_conversion
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
    UInt64Constant,
    Undefined,
    Value,
    ValueProvider,
    ValueTuple,
)
from puya.ir.op_utils import OpFactory, assert_value
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import (
    EncodedType,
    IRType,
    PrimitiveIRType,
    SizedBytesType,
    TupleIRType,
)
from puya.parse import SourceLocation
from puya.utils import bits_to_bytes

logger = log.get_logger(__name__)


def decode_value(
    context: IRRegisterContext,
    value: Value,
    encoding: Encoding,
    target_type: IRType | TupleIRType,
    loc: SourceLocation,
) -> ValueProvider:
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


def encode_value(
    context: IRRegisterContext,
    values: Sequence[Value],
    value_type: IRType | TupleIRType,
    encoding: Encoding,
    loc: SourceLocation,
) -> ValueProvider:
    if not requires_conversion(value_type, encoding, "encode"):
        logger.debug(
            f"redundant encode operation from {_encoding_or_name(value_type)} to {encoding!s}",
            location=loc,
        )
        (value,) = values
        return value
    codec = _get_arc4_codec(value_type)

    if codec is not None:
        result = codec.encode(context, values, encoding, loc)
        if result is not None:
            return result
    logger.error(f"cannot encode {_encoding_or_name(value_type)} to {encoding!s}", location=loc)
    return Undefined(
        ir_type=PrimitiveIRType.bytes,
        source_location=loc,
    )


_ARC4_FALSE = (0).to_bytes(1, "big")


class _ARC4Codec(abc.ABC):
    @abc.abstractmethod
    def encode(
        self,
        context: IRRegisterContext,
        values: Sequence[Value],
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


class _NativeTupleCodec(_ARC4Codec):
    def __init__(self, native_type: TupleIRType):
        self.native_type = native_type
        self.homogenous = len(set(self.native_type.elements)) == 1

    @typing.override
    def encode(
        self,
        context: IRRegisterContext,
        values: Sequence[Value],
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        values = list(values)
        element_ir_types = self.native_type.elements
        match encoding:
            case TupleEncoding(elements=element_encodings) as tuple_encoding if len(
                element_encodings
            ) == len(element_ir_types):
                pass
            case FixedArrayEncoding(element=element_encoding, size=size) if size == len(
                element_ir_types
            ):
                tuple_encoding = TupleEncoding([element_encoding] * size)
            case DynamicArrayEncoding(element=element_encoding):
                tuple_encoding = TupleEncoding([element_encoding] * len(element_ir_types))
            case _:
                return None
        factory = OpFactory(context, loc)
        bit_packed_index = 0
        current_head_offset = 0
        head = factory.constant(b"")
        tail = factory.constant(b"")
        processed_encodings = list[Encoding]()
        header_size_bits = tuple_encoding.get_head_bit_offset(None)
        header_size = bits_to_bytes(header_size_bits)
        current_tail_offset = factory.constant(header_size)
        for element_ir_type, element_encoding in zip(
            element_ir_types, tuple_encoding.elements, strict=True
        ):
            # special handling to bitpack consecutive bools, this will bit pack both native bools
            # and ARC-4 bools
            if element_encoding.is_bit:
                value = values.pop(0)
                # sequential bits in the same tuple are bit-packed
                if processed_encodings and processed_encodings[-1] == element_encoding:
                    # if element is an encoded bool then read the bit
                    # outside an array bool elements should not be packed
                    if value.atype == AVMType.bytes:
                        value = factory.get_bit(value, 0)
                    bit_packed_index += 1
                    bit_index = bit_packed_index % 8
                    if bit_index:
                        bit_index += (current_head_offset - 1) * 8
                    bytes_to_set = head if bit_index else _ARC4_FALSE
                    value = factory.set_bit(value=bytes_to_set, index=bit_index, bit=value)
                    # if bit_index is not 0, then just update encoded and continue
                    # as there is nothing to concat
                    if bit_index:
                        head = value
                        continue
                else:
                    if value.atype == AVMType.uint64:
                        value = factory.set_bit(
                            value=_ARC4_FALSE, index=0, bit=value, temp_desc="encoded_bit"
                        )
                    bit_packed_index = 0
            else:
                element_arity = element_ir_type.arity
                if element_arity == 1:
                    element_values = [values.pop(0)]
                else:
                    element_values = values[:element_arity]
                    values = values[element_arity:]
                if requires_conversion(element_ir_type, element_encoding, "encode"):
                    encoded_element_vp = encode_value(
                        context, element_values, element_ir_type, element_encoding, loc
                    )
                    value = factory.materialise_single(encoded_element_vp, "encoded_sub_item")
                else:
                    (value,) = element_values
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
            len_u16 = factory.as_u16_bytes(len(element_ir_types), "len_u16")
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
        from puya.ir.builder.aggregates.tup import read_at_index

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

        factory = OpFactory(context, loc)
        items = list[Value]()
        for index, (item_encoding, item_ir_type) in enumerate(
            zip(tuple_encoding.elements, self.native_type.elements, strict=True)
        ):
            encoded_item = read_at_index(
                context,
                tuple_encoding,
                value,
                index,
                loc,
            )
            assert isinstance(encoded_item, Value), "expected single item"
            if requires_conversion(item_ir_type, item_encoding, "decode"):
                item = decode_value(
                    context,
                    value=encoded_item,
                    encoding=item_encoding,
                    target_type=item_ir_type,
                    loc=loc,
                )
            else:
                item = encoded_item
            items.extend(factory.materialise_values(item, f"item{index}"))
        return ValueTuple(values=items, source_location=loc)


class _ScalarCodec(_ARC4Codec, abc.ABC):
    @typing.override
    @typing.final
    def encode(
        self,
        context: IRRegisterContext,
        values: Sequence[Value],
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        factory = OpFactory(context, loc)
        (value,) = values
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


class _BigUIntCodec(_ScalarCodec):
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


class _UInt64Codec(_ScalarCodec):
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


class _BoolCodec(_ScalarCodec):
    def __init__(self, ir_type: IRType) -> None:
        self.ir_type = ir_type

    @typing.override
    def encode_value(
        self,
        context: IRRegisterContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        match encoding:
            case BoolEncoding() if self.ir_type == PrimitiveIRType.bool:
                factory = OpFactory(context, loc)
                # TODO: compare with select implementation
                false = factory.constant(_ARC4_FALSE)
                return factory.set_bit(value=false, index=0, bit=value, temp_desc="encoded_bool")
            case UIntEncoding(n=bits) if self.ir_type == PrimitiveIRType.bool:
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
            case BoolEncoding(packed=True) if self.ir_type == EncodedType(
                BoolEncoding(packed=False)
            ):
                encoder = _BoolCodec(PrimitiveIRType.bool)
                return encoder.encode_value(context, value, BoolEncoding(packed=False), loc)
            case BoolEncoding() if self.ir_type == PrimitiveIRType.bool:
                return Intrinsic(
                    op=AVMOp.getbit,
                    args=[value, UInt64Constant(value=0, source_location=None)],
                    types=(PrimitiveIRType.bool,),
                    source_location=loc,
                )
            case UIntEncoding() if self.ir_type == PrimitiveIRType.bool:
                return Intrinsic(
                    op=AVMOp.neq_bytes,
                    args=[value, BigUIntConstant(value=0, source_location=None)],
                    types=(PrimitiveIRType.bool,),
                    source_location=loc,
                )
        return None


class _BytesCodec(_ScalarCodec):
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


class _AccountCodec(_ScalarCodec):
    @typing.override
    def encode_value(
        self,
        context: IRRegisterContext,
        value: Value,
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        match encoding:
            case FixedArrayEncoding(element=UIntEncoding(n=8), size=32):
                return value
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
        match encoding:
            case FixedArrayEncoding(element=UIntEncoding(n=8), size=32):
                return value
            case _:
                return None


class _CheckedEncoding(_ARC4Codec):
    def __init__(self, native_type: IRType):
        self.native_type: typing.Final = native_type

    @typing.override
    def encode(
        self,
        context: IRRegisterContext,
        values: Sequence[Value],
        encoding: Encoding,
        loc: SourceLocation,
    ) -> ValueProvider | None:
        if not requires_conversion(self.native_type, encoding, "encode"):
            (value,) = values
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
        if not requires_conversion(self.native_type, encoding, "decode"):
            return value
        return None


def _get_arc4_codec(ir_type: IRType | TupleIRType) -> _ARC4Codec | None:
    match ir_type:
        case TupleIRType() as aggregate:
            return _NativeTupleCodec(aggregate)
        case PrimitiveIRType.biguint:
            return _BigUIntCodec()
        case PrimitiveIRType.bool | EncodedType(BoolEncoding(packed=False)):
            return _BoolCodec(ir_type)
        case PrimitiveIRType.string:
            return _BytesCodec(UTF8Encoding())
        case PrimitiveIRType.account:
            return _AccountCodec()
        case EncodedType():
            # this supports conversion of high-level types to another high-level type
            # that has the same encoding e.g.
            # ARC4DynamicArray[arc4.UInt64] -> ARC4DynamicArray[UInt64]
            return _CheckedEncoding(ir_type)
        case PrimitiveIRType.bytes | SizedBytesType():
            return _BytesCodec(UIntEncoding(n=8))
        case _ if ir_type.maybe_avm_type == AVMType.uint64:
            return _UInt64Codec()
        case _:
            return None


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
