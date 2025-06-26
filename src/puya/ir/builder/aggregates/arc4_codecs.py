import abc
import itertools
import typing
from collections.abc import Sequence

import attrs

from puya import log
from puya.avm import AVMType
from puya.errors import InternalError
from puya.ir import (
    encodings,
    models as ir,
    types_ as types,
)
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import undefined_value
from puya.ir.builder.sequence import requires_no_conversion
from puya.ir.op_utils import OpFactory, assert_value
from puya.ir.register_context import IRRegisterContext
from puya.parse import SourceLocation
from puya.utils import bits_to_bytes

logger = log.get_logger(__name__)


def decode_bytes(
    context: IRRegisterContext,
    value: ir.Value,
    encoding: encodings.Encoding,
    target_type: types.IRType | types.TupleIRType,
    loc: SourceLocation,
) -> ir.ValueProvider:
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


def encode_to_bytes(
    context: IRRegisterContext,
    values: Sequence[ir.Value],
    values_type: types.IRType | types.TupleIRType,
    encoding: encodings.Encoding,
    loc: SourceLocation,
) -> ir.ValueProvider:
    codec = _get_arc4_codec(values_type)
    if codec is not None:
        result = codec.encode(context, values, encoding, loc)
        if result is not None:
            return result
    logger.error(f"cannot encode {_encoding_or_name(values_type)} to {encoding!s}", location=loc)
    return ir.Undefined(
        ir_type=types.PrimitiveIRType.bytes,
        source_location=loc,
    )


class _ARC4Codec(abc.ABC):
    @abc.abstractmethod
    def encode(
        self,
        context: IRRegisterContext,
        values: Sequence[ir.Value],
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None: ...

    @abc.abstractmethod
    def decode(
        self,
        context: IRRegisterContext,
        value: ir.Value,
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None: ...


@attrs.frozen
class _NativeTupleCodec(_ARC4Codec):
    native_type: types.TupleIRType

    @typing.override
    def encode(
        self,
        context: IRRegisterContext,
        values: Sequence[ir.Value],
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        values = list(values)
        element_ir_types = self.native_type.elements
        match encoding:
            case encodings.TupleEncoding(elements=element_encodings) as tuple_encoding if (
                len(element_encodings) == len(element_ir_types)
            ):
                pass
            case encodings.ArrayEncoding(element=element_encoding, size=int(size)) if (
                size == len(element_ir_types)
            ):
                tuple_encoding = encodings.TupleEncoding([element_encoding] * size)
            case encodings.ArrayEncoding(element=element_encoding, size=None):
                tuple_encoding = encodings.TupleEncoding(
                    [element_encoding] * len(element_ir_types)
                )
            case _:
                return None
        factory = OpFactory(context, loc)
        current_head_offset = 0
        head = factory.constant(b"")
        tail = factory.constant(b"")
        processed_encodings = list[encodings.Encoding]()
        header_size_bits = tuple_encoding.get_head_bit_offset(None)
        header_size = bits_to_bytes(header_size_bits)
        current_tail_offset = factory.constant(header_size)
        ir_type_and_encoding = list(zip(element_ir_types, tuple_encoding.elements, strict=True))
        # special handling to bitpack consecutive bools, this will bit pack both native bools
        # and ARC-4 bools
        for element_encoding, igroup in itertools.groupby(
            ir_type_and_encoding, key=lambda p: p[1]
        ):
            group = list(igroup)
            # sequential bits in the same tuple are bit-packed
            if element_encoding.is_bit and len(group) > 1:
                bits_offset = current_head_offset * 8
                num_bytes = bits_to_bytes(len(group))
                current_head_offset += num_bytes
                for bit_index, _ in enumerate(group):
                    processed_encodings.append(element_encoding)
                    encoded_ir_type = types.EncodedType(
                        encodings.TupleEncoding(processed_encodings)
                    )
                    value = values.pop(0)
                    if bit_index % 8 == 0:
                        if value.atype == AVMType.uint64:
                            value = factory.make_arc4_bool(value)
                        head = factory.concat(head, value, "encoded", ir_type=encoded_ir_type)
                    else:
                        # if element is an encoded bool then read the bit.
                        # outside an array bool elements should not be packed
                        if value.atype == AVMType.bytes:
                            value = factory.get_bit(value, 0)
                        head = factory.set_bit(
                            value=head, index=bits_offset + bit_index, bit=value
                        )
            else:
                for element_ir_type, _ in group:
                    element_arity = element_ir_type.arity
                    element_values = values[:element_arity]
                    values = values[element_arity:]
                    if element_encoding.is_bit:
                        (value,) = element_values
                        if value.atype == AVMType.uint64:
                            value = factory.make_arc4_bool(value)
                    elif requires_no_conversion(element_ir_type, element_encoding):
                        (value,) = element_values
                    else:
                        encoded_element_vp = encode_to_bytes(
                            context, element_values, element_ir_type, element_encoding, loc
                        )
                        value = factory.materialise_single(encoded_element_vp, "encoded_sub_item")
                    if element_encoding.is_fixed:
                        current_head_offset += element_encoding.checked_num_bytes
                    else:
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
                    processed_encodings.append(element_encoding)
                    encoded_ir_type = types.EncodedType(
                        encodings.TupleEncoding(processed_encodings)
                    )
                    head = factory.concat(head, value, "encoded", ir_type=encoded_ir_type)
        if values:
            raise InternalError(
                f"unexpected remaining values for array encoding:"
                f" {len(values)=}, {self.native_type=}, {encoding=}",
                loc,
            )
        if isinstance(encoding, encodings.ArrayEncoding) and encoding.length_header:
            len_u16 = factory.as_u16_bytes(len(element_ir_types), "len_u16")
            head = factory.concat(len_u16, head, "encoded")
        encoded = factory.concat(head, tail, "encoded", ir_type=types.EncodedType(encoding))
        return encoded

    @typing.override
    def decode(
        self,
        context: IRRegisterContext,
        value: ir.Value,
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        from puya.ir.builder.aggregates.tup import read_at_index

        item_types = self.native_type.elements
        match encoding:
            case encodings.TupleEncoding(elements=elements) as tuple_encoding if (
                len(elements) == len(item_types)
            ):
                pass
            case encodings.ArrayEncoding(element=element, size=int(size), length_header=False) if (
                size == len(item_types)
            ):
                tuple_encoding = encodings.TupleEncoding([element] * size)
            case _:
                return None

        factory = OpFactory(context, loc)
        result = list[ir.Value]()
        for index, (item_encoding, item_ir_type) in enumerate(
            zip(tuple_encoding.elements, item_types, strict=True)
        ):
            encoded_item = read_at_index(context, tuple_encoding, value, index, loc)
            if requires_no_conversion(item_ir_type, item_encoding):
                result.append(encoded_item)
            else:
                item = decode_bytes(
                    context,
                    value=encoded_item,
                    encoding=item_encoding,
                    target_type=item_ir_type,
                    loc=loc,
                )
                items = factory.materialise_values(item, f"item{index}")
                result.extend(items)
        return ir.ValueTuple(values=result, source_location=loc)


class _ScalarCodec(_ARC4Codec, abc.ABC):
    @typing.override
    @typing.final
    def encode(
        self,
        context: IRRegisterContext,
        values: Sequence[ir.Value],
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        factory = OpFactory(context, loc)
        (value,) = values
        result = self.encode_value(context, value, encoding, loc)
        if result is None:
            return None
        return factory.as_ir_type(result, types.EncodedType(encoding))

    @abc.abstractmethod
    def encode_value(
        self,
        context: IRRegisterContext,
        value: ir.Value,
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None: ...


class _BigUIntCodec(_ScalarCodec):
    @typing.override
    def encode_value(
        self,
        context: IRRegisterContext,
        value: ir.Value,
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        match encoding:
            case encodings.UIntEncoding():
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
        value: ir.Value,
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        match encoding:
            case encodings.UIntEncoding():
                return value
        return None


class _UInt64Codec(_ScalarCodec):
    @typing.override
    def encode_value(
        self,
        context: IRRegisterContext,
        value: ir.Value,
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        match encoding:
            case encodings.UIntEncoding(n=bits):
                num_bytes = bits // 8
                return _encode_native_uint64_to_arc4(context, value, num_bytes, loc)
        return None

    @typing.override
    def decode(
        self,
        context: IRRegisterContext,
        value: ir.Value,
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        match encoding:
            # note that if bits were > 64, a runtime error would always occur, as btoi
            # will fail if input is more than 8 bytes.
            # if the need arose, we could handle the >64 case by asserting the value is in range
            # and then using extract_uint64
            case encodings.UIntEncoding(n=bits) if bits <= 64:
                return ir.Intrinsic(op=AVMOp.btoi, args=[value], source_location=loc)
        return None


class _BoolCodec(_ScalarCodec):
    @typing.override
    def encode_value(
        self,
        context: IRRegisterContext,
        value: ir.Value,
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        match encoding:
            case encodings.BoolEncoding():
                return value
            case encodings.Bool8Encoding():
                factory = OpFactory(context, loc)
                return factory.make_arc4_bool(value)
            case encodings.UIntEncoding(n=bits):
                num_bytes = bits // 8
                return _encode_native_uint64_to_arc4(context, value, num_bytes, loc)
        return None

    @typing.override
    def decode(
        self,
        context: IRRegisterContext,
        value: ir.Value,
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        factory = OpFactory(context, loc)
        match encoding:
            case encodings.BoolEncoding():
                return value
            case encodings.Bool8Encoding():
                return factory.get_bit(value, 0, ir_type=types.PrimitiveIRType.bool)
            case encodings.UIntEncoding():
                return factory.neq_bytes(value, b"")
        return None


class _Bool8Codec(_ScalarCodec):
    @typing.override
    def encode_value(
        self,
        context: IRRegisterContext,
        value: ir.Value,
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        if encoding.is_bit:
            factory = OpFactory(context, loc)
            assert value.atype == AVMType.bytes, "expected bytes"
            return factory.get_bit(value, 0)
        return None

    @typing.override
    def decode(
        self,
        context: IRRegisterContext,
        value: ir.Value,
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        if encoding.is_bit:
            factory = OpFactory(context, loc)
            assert value.atype == AVMType.uint64, "expected uint64"
            return factory.make_arc4_bool(value)
        return None


@attrs.frozen
class _BytesCodec(_ScalarCodec):
    element: encodings.UIntEncoding | encodings.UTF8Encoding

    @typing.override
    def encode_value(
        self,
        context: IRRegisterContext,
        value: ir.Value,
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        factory = OpFactory(context, loc)
        if isinstance(encoding, encodings.ArrayEncoding) and encoding.element == self.element:
            if encoding.length_header:
                assert encoding.size is None, "unexpected array encoding"
                length = factory.len(value, "length")
                length_uint16 = factory.as_u16_bytes(length, "length_uint16")
                return factory.concat(length_uint16, value, "encoded_value")
            else:
                if encoding.size is not None:
                    length = factory.len(value, "length")
                    lengths_equal = factory.eq(length, encoding.size, "lengths_equal")
                    assert_value(
                        context, lengths_equal, error_message="invalid size", source_location=loc
                    )
                return value
        return None

    @typing.override
    def decode(
        self,
        context: IRRegisterContext,
        value: ir.Value,
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        if isinstance(encoding, encodings.ArrayEncoding) and encoding.element == self.element:
            if encoding.length_header:
                return ir.Intrinsic(
                    op=AVMOp.extract, immediates=[2, 0], args=[value], source_location=loc
                )
            else:
                return value
        return None


class _AccountCodec(_ScalarCodec):
    @typing.override
    def encode_value(
        self,
        context: IRRegisterContext,
        value: ir.Value,
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        match encoding:
            case encodings.ArrayEncoding(
                element=encodings.UIntEncoding(n=8), size=32, length_header=False
            ):
                return value
            case _:
                return None

    @typing.override
    def decode(
        self,
        context: IRRegisterContext,
        value: ir.Value,
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        match encoding:
            case encodings.ArrayEncoding(
                element=encodings.UIntEncoding(n=8), size=32, length_header=False
            ):
                return value
            case _:
                return None


@attrs.frozen
class _CheckedEncoding(_ARC4Codec):
    native_type: types.EncodedType

    @typing.override
    def encode(
        self,
        context: IRRegisterContext,
        values: Sequence[ir.Value],
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        if self.native_type.encoding == encoding:
            (value,) = values
            return value
        return None

    @typing.override
    def decode(
        self,
        context: IRRegisterContext,
        value: ir.Value,
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        if self.native_type.encoding == encoding:
            return value
        return None


def _get_arc4_codec(ir_type: types.IRType | types.TupleIRType) -> _ARC4Codec | None:
    match ir_type:
        case types.TupleIRType() as aggregate:
            return _NativeTupleCodec(aggregate)
        case types.PrimitiveIRType.biguint:
            return _BigUIntCodec()
        case types.PrimitiveIRType.bool | types.EncodedType(encoding=encodings.BoolEncoding()):
            return _BoolCodec()
        case types.EncodedType(encoding=encodings.Bool8Encoding()):
            return _Bool8Codec()
        case types.PrimitiveIRType.string:
            return _BytesCodec(encodings.UTF8Encoding())
        case types.PrimitiveIRType.account:
            return _AccountCodec()
        case types.EncodedType():
            # this supports conversion of high-level types to another high-level type
            # that has the same encoding e.g.
            # ARC4DynamicArray[arc4.UInt64] -> ARC4DynamicArray[UInt64]
            return _CheckedEncoding(ir_type)
        case types.PrimitiveIRType.bytes | types.SizedBytesType():
            return _BytesCodec(encodings.UIntEncoding(n=8))
        case _ if ir_type.maybe_avm_type == AVMType.uint64:
            return _UInt64Codec()
        case _:
            return None


def _encoding_or_name(typ: types.IRType | types.TupleIRType) -> str:
    if isinstance(typ, types.EncodedType):
        return typ.encoding.name
    else:
        return typ.name


def _encode_native_uint64_to_arc4(
    context: IRRegisterContext, value: ir.Value, num_bytes: int, source_location: SourceLocation
) -> ir.Value:
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
