import typing
from collections.abc import Sequence

from puya import log
from puya.awst import (
    wtypes,
)
from puya.ir import models as ir
from puya.ir._puya_lib import PuyaLibIR
from puya.ir.builder import mem
from puya.ir.builder._utils import (
    OpFactory,
    assert_value,
    invoke_puya_lib_subroutine,
    undefined_value,
)
from puya.ir.encodings import (
    ArrayEncoding,
    BoolEncoding,
    DynamicArrayEncoding,
    Encoding,
    FixedArrayEncoding,
    wtype_to_encoding,
)
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import (
    EncodedType,
    IRType,
    PrimitiveIRType,
    SlotType,
    TupleIRType,
    wtype_to_ir_type,
)
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def read_index_and_decode(
    context: IRRegisterContext,
    indexable_wtype: wtypes.ARC4Array | wtypes.ReferenceArray,
    array_or_slot: ir.Value,
    index: ir.Value,
    loc: SourceLocation,
    *,
    check_bounds: bool = True,
) -> ir.MultiValue:
    array_encoding = wtype_to_encoding(indexable_wtype, loc)
    element_ir_type = wtype_to_ir_type(
        indexable_wtype.element_type, source_location=loc, allow_tuple=True
    )
    if isinstance(array_or_slot.ir_type, SlotType):
        array = mem.read_slot(context, array_or_slot, loc)
    else:
        array = array_or_slot
    read_index = ir.ArrayReadIndex(
        array=array,
        array_encoding=array_encoding,
        index=index,
        source_location=loc,
        check_bounds=check_bounds,
    )
    (array_item,) = context.materialise_value_provider(read_index, "array_item")
    element_encoding = array_encoding.element
    if not requires_conversion(element_ir_type, element_encoding, "decode"):
        return array_item
    else:
        factor = OpFactory(context, loc)
        return factor.materialise_multi_value(
            ir.ValueDecode(
                value=array_item,
                encoding=element_encoding,
                decoded_type=element_ir_type,
                source_location=loc,
            )
        )


def read_tuple_index_and_decode(
    context: IRRegisterContext,
    tuple_wtype: wtypes.ARC4Tuple | wtypes.ARC4Struct | wtypes.WTuple,
    values: Sequence[ir.Value],
    index: int,
    loc: SourceLocation,
) -> ir.MultiValue:
    if isinstance(tuple_wtype, wtypes.WTuple):
        tuple_ir_type = wtype_to_ir_type(tuple_wtype, loc, allow_tuple=True)
        skip_values = sum(e.arity for e in tuple_ir_type.elements[:index])
        target_arity = tuple_ir_type.elements[index].arity
        element_values = values[skip_values : skip_values + target_arity]

        if len(element_values) == 1:
            return element_values[0]
        else:
            return ir.ValueTuple(values=element_values, source_location=loc)

    assert isinstance(
        tuple_wtype, wtypes.ARC4Tuple | wtypes.ARC4Struct
    ), "expected ARC4 tuple or struct"
    (base,) = values
    tuple_encoding = wtype_to_encoding(tuple_wtype, loc)
    element_wtype = tuple_wtype.types[index]
    element_ir_type = wtype_to_ir_type(element_wtype, source_location=loc, allow_tuple=True)
    read_index = ir.TupleReadIndex(
        base=base,
        tuple_encoding=tuple_encoding,
        indexes=[index],
        source_location=loc,
    )
    (tuple_item,) = context.materialise_value_provider(read_index, "tuple_item")
    element_encoding = tuple_encoding.elements[index]
    if not requires_conversion(element_ir_type, element_encoding, "decode"):
        return tuple_item
    else:
        values = context.materialise_value_provider(
            ir.ValueDecode(
                value=tuple_item,
                encoding=element_encoding,
                decoded_type=element_ir_type,
                source_location=loc,
            ),
            "values",
        )
        if len(values) == 1:
            return values[0]
        else:
            return ir.ValueTuple(values=values, source_location=loc)


def encode_and_write_index(
    context: IRRegisterContext,
    indexable_wtype: wtypes.ARC4Array | wtypes.ReferenceArray,
    array_or_slot: ir.Value,
    index: ir.Value,
    values: Sequence[ir.Value],
    loc: SourceLocation,
) -> ir.Value:
    array_encoding = wtype_to_encoding(indexable_wtype, loc)
    element_ir_type = wtype_to_ir_type(
        indexable_wtype.element_type, source_location=loc, allow_tuple=True
    )
    element_encoding = array_encoding.element
    if not requires_conversion(element_ir_type, element_encoding, "encode"):
        (encoded_value,) = values
    else:
        (encoded_value,) = context.materialise_value_provider(
            ir.ValueEncode(
                values=values,
                encoding=element_encoding,
                value_type=element_ir_type,
                source_location=loc,
            ),
            "encoded_value",
        )

    if isinstance(array_or_slot.ir_type, SlotType):
        array = mem.read_slot(context, array_or_slot, loc)
        write_index = ir.ArrayWriteIndex(
            array=array,
            array_encoding=array_encoding,
            index=index,
            value=encoded_value,
            source_location=loc,
        )
        (result,) = context.materialise_value_provider(write_index, "updated_array")
        mem.write_slot(context, array_or_slot, result, loc)
        return array_or_slot
    else:
        write_index = ir.ArrayWriteIndex(
            array=array_or_slot,
            array_encoding=array_encoding,
            index=index,
            value=encoded_value,
            source_location=loc,
        )
        (result,) = context.materialise_value_provider(write_index, "updated_array")
        return result


def encode_and_write_tuple_index(
    context: IRRegisterContext,
    tuple_wtype: wtypes.WTuple | wtypes.ARC4Tuple | wtypes.ARC4Struct,
    base: ir.MultiValue,
    index: int,
    values: Sequence[ir.Value],
    loc: SourceLocation,
) -> ir.MultiValue:
    if isinstance(tuple_wtype, wtypes.WTuple):
        tuple_ir_type = wtype_to_ir_type(tuple_wtype, loc, allow_tuple=True)
        skip_values = sum(e.arity for e in tuple_ir_type.elements[:index])
        target_arity = tuple_ir_type.elements[index].arity
        new_values = context.materialise_value_provider(base, "new_values")
        new_values[skip_values : skip_values + target_arity] = values
        if len(new_values) == 1:
            return new_values[0]
        else:
            return ir.ValueTuple(values=new_values, source_location=loc)
    (base,) = context.materialise_value_provider(base, "base")
    tuple_encoding = wtype_to_encoding(tuple_wtype, loc)
    element_wtype = tuple_wtype.types[index]
    element_ir_type = wtype_to_ir_type(element_wtype, source_location=loc, allow_tuple=True)
    element_encoding = tuple_encoding.elements[index]
    if not requires_conversion(element_ir_type, element_encoding, "encode"):
        (encoded_value,) = values
    else:
        (encoded_value,) = context.materialise_value_provider(
            ir.ValueEncode(
                values=values,
                encoding=element_encoding,
                value_type=element_ir_type,
                source_location=loc,
            ),
            "encoded_value",
        )

    write_index = ir.TupleWriteIndex(
        base=base,
        tuple_encoding=tuple_encoding,
        indexes=[index],
        value=encoded_value,
        source_location=loc,
    )
    (result,) = context.materialise_value_provider(write_index, "updated_tuple")
    return result


def get_length(
    context: IRRegisterContext,
    array_encoding: ArrayEncoding,
    array_or_slot: ir.Value,
    loc: SourceLocation | None,
) -> ir.Value:
    if isinstance(array_or_slot.ir_type, SlotType):
        array = mem.read_slot(context, array_or_slot, loc)
    else:
        array = array_or_slot
    # how length is calculated depends on the array type, rather than the element type
    factory = OpFactory(context, loc)
    if isinstance(array_encoding, FixedArrayEncoding):
        return factory.constant(array_encoding.size)
    elif array_encoding.length_header:
        return factory.extract_uint16(array, 0, "array_length")
    assert array_encoding.size is None, "expected dynamic array"
    bytes_len = factory.len(array, "bytes_len")
    return factory.div_floor(bytes_len, array_encoding.element.checked_num_bytes, "array_len")


def requires_conversion(
    typ: IRType | TupleIRType, encoding: Encoding, action: typing.Literal["encode", "decode"]
) -> bool:
    if typ == PrimitiveIRType.bool and isinstance(encoding, BoolEncoding):
        return True
    elif isinstance(typ, EncodedType):
        typ_is_bool8 = isinstance(typ.encoding, BoolEncoding) and not typ.encoding.packed
        encoding_is_bool1 = encoding.is_bit
        if typ_is_bool8 and encoding_is_bool1 and action == "encode":
            return False
        # are encodings different?
        return typ.encoding != encoding
    # otherwise requires conversion
    else:
        return True


def convert_array(
    context: IRRegisterContext,
    source: ir.Value,
    *,
    source_wtype: wtypes.ARC4Array | wtypes.ReferenceArray,
    target_wtype: wtypes.ARC4Array | wtypes.ReferenceArray,
    loc: SourceLocation,
) -> ir.ValueProvider:
    factory = OpFactory(context, loc)

    target_encoding = wtype_to_encoding(target_wtype, loc)
    source_encoding = wtype_to_encoding(source_wtype, loc)

    if isinstance(source.ir_type, SlotType):
        source = mem.read_slot(context, source, loc)
    source_length = get_length(context, source_encoding, source, loc)

    match target_encoding.element, source_encoding.element:
        case (
            BoolEncoding(packed=packed_target),
            BoolEncoding(packed=packed_source),
        ) if packed_target != packed_source:
            if packed_source:
                logger.error(
                    "converting from a bitpacked bool array"
                    " to an non-bitpacked bool array is currently unsupported",
                    location=loc,
                )
                return undefined_value(target_wtype, loc)
            else:
                assert not source_encoding.length_header, "expected ReferenceArray"
                empty_header = factory.constant(b"\0" * 2)
                bitpacked_source_provider = invoke_puya_lib_subroutine(
                    context,
                    full_name=PuyaLibIR.dynamic_array_concat_bits,
                    args=[empty_header, source, source_length, 8],
                    source_location=loc,
                )
                (source,) = context.materialise_value_provider(
                    bitpacked_source_provider, description="bit_packed_source"
                )
                source_encoding = DynamicArrayEncoding(
                    BoolEncoding(packed=True), length_header=True
                )

    if target_encoding.element != source_encoding.element:
        logger.error(
            "array elements must have equivalent encoding to be convertible", location=loc
        )
        return undefined_value(target_wtype, loc)

    if source_encoding.size != target_encoding.size:
        if target_encoding.size is None:
            pass  # going from fixed to dynamic, there's no rules here
        elif source_encoding.size is None:
            # we want to get the length of the source and assert it equals the size
            assert_value(
                context,
                factory.eq(source_length, target_encoding.size),
                error_message="invalid input length",
                source_location=loc,
            )
        else:
            # fixed to fixed, but the lengths aren't equal
            logger.error("static size conversion cannot add or remove elements", location=loc)
            return undefined_value(target_wtype, loc)

    target_ir_type = wtype_to_ir_type(target_wtype, loc)
    if isinstance(target_ir_type, SlotType):
        target_value_type = target_ir_type.contents
    else:
        target_value_type = target_ir_type
    if source_encoding.length_header and not target_encoding.length_header:
        new_value: ir.Value = factory.extract_to_end(
            source, 2, "converted_array", ir_type=target_value_type
        )
    elif target_encoding.length_header and not source_encoding.length_header:
        len_value = factory.as_u16_bytes(source_length)
        new_value = factory.concat(
            len_value, source, temp_desc="converted_array", ir_type=target_value_type
        )
    else:
        new_value = source

    if isinstance(target_ir_type, SlotType):
        new_slot = mem.new_slot(context, target_ir_type, loc)
        mem.write_slot(context, new_slot, new_value, loc)
        return new_slot
    return new_value
