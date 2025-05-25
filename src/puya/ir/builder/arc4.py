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
from puya.ir.builder.assignment import handle_assignment
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
from puya.parse import SourceLocation
from puya.utils import bits_to_bytes, round_bits_to_nearest_bytes

logger = log.get_logger(__name__)


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


def decode_arc4_value(
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


def _encoding_or_name(typ: IRType | TupleIRType) -> str:
    if isinstance(typ, EncodedType):
        return typ.encoding.name
    else:
        return typ.name


# TODO: this becomes the lowering implementation for ir.ValueEncode
def encode_value_provider(
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


def arc4_tuple_index(
    context: IRFunctionBuildContext,
    base: Value,
    index: int,
    tuple_encoding: TupleEncoding,
    item_ir_type: IRType | TupleIRType,
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
            builder = sequence.get_builder(context, array_wtype, source_location)
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
                allow_tuple=True,
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


def _bit_packed_bool(encoding: Encoding) -> typing.TypeGuard[BoolEncoding]:
    return isinstance(encoding, BoolEncoding) and encoding.packed


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
        encoded_item_value = _read_nth_item_of_arc4_heterogeneous_container(
            context,
            array_head_and_tail=value,
            tuple_item_types=tuple_elements,
            index=index,
            source_location=source_location,
        )
        if type_has_encoding(target_item_type, encoded_item_type):
            item_value = encoded_item_value
        else:
            item_value = decode_arc4_value(
                context,
                factory.materialise_single(encoded_item_value, f"encoded_item{index}"),
                encoding=encoded_item_type,
                target_type=target_item_type,
                loc=source_location,
            )
        items.extend(factory.materialise_values(item_value, f"item{index}"))
    return ValueTuple(source_location=source_location, values=items)


def _is_byte_length_header(encoding: Encoding) -> bool:
    if not isinstance(encoding, DynamicArrayEncoding) or not encoding.length_header:
        return False
    if _bit_packed_bool(encoding):
        return False
    return encoding.element.num_bytes == 1


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
    value_ir_type: IRType | TupleIRType,
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
