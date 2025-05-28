from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.ir import models as ir
from puya.ir.builder import arc4
from puya.ir.builder._utils import OpFactory
from puya.ir.encodings import (
    ArrayEncoding,
    FixedArrayEncoding,
    wtype_to_encoding,
)
from puya.ir.models import ValueTuple
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import (
    get_type_arity,
    sum_types_arity,
    wtype_to_ir_type,
)
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def read_index_and_decode(
    context: IRRegisterContext,
    indexable_wtype: wtypes.ARC4Array | wtypes.NativeArray,
    array: ir.Value,
    index: ir.Value,
    loc: SourceLocation,
    *,
    check_bounds: bool = True,
) -> ir.ValueProvider:
    array_encoding = wtype_to_encoding(indexable_wtype, loc)
    element_ir_type = wtype_to_ir_type(
        indexable_wtype.element_type, source_location=loc, allow_tuple=True
    )
    read_index = ir.ArrayReadIndex(
        array=array,
        array_encoding=array_encoding,
        index=index,
        source_location=loc,
        check_bounds=check_bounds,
    )
    (array_item,) = context.materialise_value_provider(read_index, "array_item")
    element_encoding = array_encoding.element
    if not arc4.requires_conversion(element_ir_type, element_encoding, "decode"):
        return array_item
    else:
        return ir.ValueDecode(
            value=array_item,
            encoding=element_encoding,
            decoded_type=element_ir_type,
            source_location=loc,
        )


def read_tuple_index_and_decode(
    context: IRRegisterContext,
    tuple_wtype: wtypes.ARC4Tuple | wtypes.ARC4Struct | wtypes.WTuple,
    base: ir.Value | ir.ValueTuple,
    index: int,
    loc: SourceLocation,
) -> ir.ValueProvider:
    if isinstance(tuple_wtype, wtypes.WTuple):
        tuple_values = [base] if isinstance(base, ir.Value) else base.values
        tuple_ir_type = wtype_to_ir_type(tuple_wtype, loc, allow_tuple=True)
        skip_values = sum_types_arity(tuple_ir_type.elements[:index])
        target_arity = get_type_arity(tuple_ir_type.elements[index])
        values = tuple_values[skip_values : skip_values + target_arity]

        if len(values) == 1:
            return values[0]
        else:
            return ValueTuple(values=values, source_location=loc)

    assert isinstance(
        tuple_wtype, wtypes.ARC4Tuple | wtypes.ARC4Struct
    ), "expected ARC4 tuple or struct"
    assert isinstance(base, ir.Value), "expected single value for ARC4 types"
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
    if not arc4.requires_conversion(element_ir_type, element_encoding, "decode"):
        return tuple_item
    else:
        return ir.ValueDecode(
            value=tuple_item,
            encoding=element_encoding,
            decoded_type=element_ir_type,
            source_location=loc,
        )


def encode_and_write_index(
    context: IRRegisterContext,
    indexable_wtype: wtypes.ARC4Array | wtypes.NativeArray,
    array: ir.Value,
    index: ir.Value,
    values: Sequence[ir.Value],
    loc: SourceLocation,
) -> ir.Value:
    array_encoding = wtype_to_encoding(indexable_wtype, loc)
    element_ir_type = wtype_to_ir_type(
        indexable_wtype.element_type, source_location=loc, allow_tuple=True
    )
    element_encoding = array_encoding.element
    if not arc4.requires_conversion(element_ir_type, element_encoding, "encode"):
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

    write_index = ir.ArrayWriteIndex(
        array=array,
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
    base: ir.Value,
    index: int,
    values: Sequence[ir.Value],
    loc: SourceLocation,
) -> ir.Value:
    tuple_encoding = wtype_to_encoding(tuple_wtype, loc)
    element_wtype = tuple_wtype.types[index]
    element_ir_type = wtype_to_ir_type(element_wtype, source_location=loc, allow_tuple=True)
    element_encoding = tuple_encoding.elements[index]
    if not arc4.requires_conversion(element_ir_type, element_encoding, "encode"):
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
    array: ir.Value,
    loc: SourceLocation | None,
) -> ir.Value:
    # how length is calculated depends on the array type, rather than the element type
    factory = OpFactory(context, loc)
    if isinstance(array_encoding, FixedArrayEncoding):
        return factory.constant(array_encoding.size)
    elif array_encoding.length_header:
        return factory.extract_uint16(array, 0, "array_length")
    assert array_encoding.size is None, "expected dynamic array"
    bytes_len = factory.len(array, "bytes_len")
    return factory.div_floor(bytes_len, array_encoding.element.checked_num_bytes, "array_len")
