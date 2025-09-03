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
from puya.ir.builder.aggregates.tup import read_at_index
from puya.ir.op_utils import OpFactory, assert_value
from puya.ir.register_context import IRRegisterContext
from puya.parse import SourceLocation
from puya.utils import bits_to_bytes, chunk_array

logger = log.get_logger(__name__)


def decode_bytes(
    context: IRRegisterContext,
    value: ir.Value,
    encoding: encodings.Encoding,
    target_type: types.IRType | types.TupleIRType,
    loc: SourceLocation,
    *,
    error_message_override: str | None = None,
) -> ir.ValueProvider:
    result = _try_decode_bytes(context, value, encoding, target_type, loc)
    if result is not None:
        return result
    logger.error(
        error_message_override
        or f"cannot decode from {encoding!s} to {_encoding_or_name(target_type)}",
        location=loc,
    )
    return undefined_value(target_type, loc)


def _try_decode_bytes(
    context: IRRegisterContext,
    value: ir.Value,
    encoding: encodings.Encoding,
    target_type: types.IRType | types.TupleIRType,
    loc: SourceLocation,
) -> ir.ValueProvider | None:
    if isinstance(target_type, types.EncodedType) and target_type.encoding == encoding:
        return value
    codec = _get_arc4_codec(target_type)
    if codec is None:
        return None
    return codec.decode(context, value, encoding, loc)


def encode_to_bytes(
    context: IRRegisterContext,
    values: Sequence[ir.Value],
    values_type: types.IRType | types.TupleIRType,
    encoding: encodings.Encoding,
    loc: SourceLocation,
    *,
    error_message_override: str | None = None,
) -> ir.ValueProvider:
    result = _try_encode_to_bytes(context, values, values_type, encoding, loc)
    if result is not None:
        return result
    logger.error(
        error_message_override
        or f"cannot encode {_encoding_or_name(values_type)} to {encoding!s}",
        location=loc,
    )
    return ir.Undefined(
        ir_type=types.bytes_,
        source_location=loc,
    )


def _try_encode_to_bytes(
    context: IRRegisterContext,
    values: Sequence[ir.Value],
    values_type: types.IRType | types.TupleIRType,
    encoding: encodings.Encoding,
    loc: SourceLocation,
) -> ir.ValueProvider | None:
    if isinstance(values_type, types.EncodedType) and values_type.encoding == encoding:
        if isinstance(values_type, types.TupleIRType):
            return ir.ValueTuple(values=values, ir_type=values_type, source_location=loc)
        else:
            (value,) = values
            return value
    codec = _get_arc4_codec(values_type)
    if codec is None:
        return None
    return codec.encode(context, values, encoding, loc)


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
        element_ir_types = self.native_type.elements
        num_tuple_elements = len(element_ir_types)
        match encoding:
            case encodings.TupleEncoding(elements=element_encodings) as tuple_encoding if (
                len(element_encodings) == num_tuple_elements
            ):
                pass
            case encodings.ArrayEncoding(element=element_encoding, size=size) if (
                size in (None, num_tuple_elements)
            ):
                tuple_encoding = encodings.TupleEncoding([element_encoding] * num_tuple_elements)
            case _:
                return None

        values = list(values)
        data = list[tuple[encodings.Encoding, types.IRType | types.TupleIRType, list[ir.Value]]]()
        for element_ir_type, element_encoding in zip(
            element_ir_types, tuple_encoding.elements, strict=True
        ):
            element_arity = element_ir_type.arity
            element_values = values[:element_arity]
            assert len(element_values) == element_arity
            values = values[element_arity:]
            data.append((element_encoding, element_ir_type, element_values))
        if values:
            raise InternalError(
                f"unexpected remaining values for tuple encoding:"
                f" {len(values)=}, {self.native_type=}, {encoding=}",
                loc,
            )

        factory = OpFactory(context, loc)
        header_size_bits = tuple_encoding.get_head_bit_offset(None)
        header_size = bits_to_bytes(header_size_bits)
        if isinstance(encoding, encodings.ArrayEncoding) and encoding.length_header:
            head: ir.Value = factory.as_u16_bytes(num_tuple_elements, "len_u16")
        else:
            head = factory.constant(b"")

        current_tail_offset = factory.constant(header_size)
        tail_parts = []

        # special handling to bitpack consecutive bools, this will bit pack both native bools
        # and ARC-4 bools
        for element_encoding, group in itertools.groupby(data, key=lambda p: p[0]):
            # sequential bits in the same tuple are bit-packed
            if element_encoding.is_bit:
                values_to_bitpack = [v for (_, _, element_values) in group for v in element_values]
                for byte_group in chunk_array(values_to_bitpack, size=8):
                    # if element is an encoded bool then read the bit.
                    # outside an array bool elements should not be packed
                    first, *rest = byte_group
                    if first.atype == AVMType.bytes:
                        building = first
                    else:
                        building = factory.make_arc4_bool(first)
                    for index, bit_value in enumerate(rest, start=1):
                        if bit_value.atype == AVMType.bytes:
                            bit_value = factory.get_bit(bit_value, 0)
                        building = factory.set_bit(value=building, index=index, bit=bit_value)
                    head = factory.concat(head, building, "head")
            else:
                for _, element_ir_type, element_values in group:
                    encoded_element_vp = _try_encode_to_bytes(
                        context, element_values, element_ir_type, element_encoding, loc
                    )
                    if encoded_element_vp is None:
                        return None
                    encoded_element = factory.materialise_single(
                        encoded_element_vp, "encoded_sub_item"
                    )
                    if element_encoding.is_fixed:
                        # head value is element
                        head = factory.concat(head, encoded_element, "head")
                    else:
                        # head value is tail offset
                        head = factory.concat(
                            head,
                            factory.as_u16_bytes(current_tail_offset, "offset_as_uint16"),
                            "head",
                        )
                        # append value to tail
                        tail_parts.append(encoded_element)
                        # update offset
                        current_tail_offset = factory.add(
                            current_tail_offset,
                            factory.len(encoded_element, "data_length"),
                            "current_tail_offset",
                        )

        encoded = head
        for tail_part in tail_parts:
            encoded = factory.concat(encoded, tail_part)
        return factory.as_ir_type(encoded, types.EncodedType(encoding))

    @typing.override
    def decode(
        self,
        context: IRRegisterContext,
        value: ir.Value,
        encoding: encodings.Encoding,
        loc: SourceLocation,
    ) -> ir.ValueProvider | None:
        element_ir_types = self.native_type.elements
        num_tuple_elements = len(element_ir_types)
        match encoding:
            case encodings.TupleEncoding(elements=elements) as tuple_encoding if (
                len(elements) == num_tuple_elements
            ):
                pass
            # asymmetrical encode/decode support here
            # reasons:
            #   1) fixed size and length_header=True is not supported currently
            #   2) size=None is not supported as dynamically sized tuples are not supported
            case encodings.ArrayEncoding(element=element, size=size, length_header=False) if (
                size == num_tuple_elements
            ):
                tuple_encoding = encodings.TupleEncoding([element] * num_tuple_elements)
            case _:
                return None

        factory = OpFactory(context, loc)
        result = list[ir.Value]()
        for index, (element_encoding, element_ir_type) in enumerate(
            zip(tuple_encoding.elements, element_ir_types, strict=True)
        ):
            encoded_element = read_at_index(context, tuple_encoding, value, index, loc)
            item = _try_decode_bytes(
                context,
                value=encoded_element,
                encoding=element_encoding,
                target_type=element_ir_type,
                loc=loc,
            )
            if item is None:
                return None
            items = factory.materialise_values(item, f"item{index}")
            result.extend(items)
        return ir.ValueTuple(values=result, ir_type=self.native_type, source_location=loc)


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
            case encodings.UIntEncoding(n=bits) if bits <= 64:
                return ir.Intrinsic(op=AVMOp.btoi, args=[value], source_location=loc)
            case encodings.UIntEncoding(n=bits) if bits > 64:
                factory = OpFactory(context, loc)
                bit_len = factory.bitlen(value)
                is_correct_bit_len = factory.lte(bit_len, 64)
                factory.assert_value(is_correct_bit_len, error_message="overflow")

                endian_index = factory.sub(factory.len(value), 8)
                return factory.extract_uint64(value, endian_index)

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
                return factory.get_bit(value, 0, ir_type=types.bool_)
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
        elif isinstance(encoding, encodings.Bool8Encoding):
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
        if encoding.is_bit:
            factory = OpFactory(context, loc)
            assert value.atype == AVMType.uint64, "expected uint64"
            return factory.make_arc4_bool(value)
        elif isinstance(encoding, encodings.Bool8Encoding):
            return value
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


def _get_arc4_codec(ir_type: types.IRType | types.TupleIRType) -> _ARC4Codec | None:
    match ir_type:
        case types.TupleIRType() as aggregate:
            return _NativeTupleCodec(aggregate)
        case types.biguint:
            return _BigUIntCodec()
        case types.bool_:
            return _BoolCodec()
        case types.EncodedType(encoding=encodings.Bool8Encoding()):
            return _Bool8Codec()
        case types.string:
            return _BytesCodec(encodings.UTF8Encoding())
        case types.account:
            return _AccountCodec()
        case types.bytes_ | types.SizedBytesType():
            return _BytesCodec(encodings.UIntEncoding(n=8))
        case types.IRType(maybe_avm_type=AVMType.uint64):
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
