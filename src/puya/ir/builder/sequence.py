from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.errors import InternalError
from puya.ir import (
    encodings,
    models as ir,
    types_ as types,
)
from puya.ir._puya_lib import PuyaLibIR
from puya.ir.builder import mem
from puya.ir.builder._utils import invoke_puya_lib_subroutine, undefined_value
from puya.ir.op_utils import OpFactory, assert_value
from puya.ir.register_context import IRRegisterContext
from puya.parse import SourceLocation

logger = log.get_logger(__name__)

WAggregate = (
    wtypes.ARC4Tuple | wtypes.ARC4Struct | wtypes.WTuple | wtypes.ARC4Array | wtypes.ReferenceArray
)


def read_tuple_index(
    wtype: wtypes.WTuple,
    values: Sequence[ir.Value],
    index: int,
    loc: SourceLocation,
) -> ir.MultiValue:
    tuple_ir_type = types.wtype_to_ir_type(wtype, loc, allow_tuple=True)
    skip_values = sum(e.arity for e in tuple_ir_type.elements[:index])
    target_ir_type = tuple_ir_type.elements[index]
    element_values = values[skip_values : skip_values + target_ir_type.arity]
    if isinstance(target_ir_type, types.TupleIRType):
        return ir.ValueTuple(values=element_values, ir_type=target_ir_type, source_location=loc)
    else:
        (result,) = element_values
        return result


def read_aggregate_index_and_decode(
    context: IRRegisterContext,
    aggregate_wtype: WAggregate,
    values: Sequence[ir.Value],
    indexes: Sequence[int | ir.Value],
    loc: SourceLocation,
    *,
    check_bounds: bool = True,
) -> ir.MultiValue:
    if isinstance(aggregate_wtype, wtypes.WTuple):
        (index,) = indexes
        assert isinstance(index, int), "expected integer"
        return read_tuple_index(aggregate_wtype, values, index, loc)
    (base,) = values
    if isinstance(base.ir_type, types.SlotType):
        base = mem.read_slot(context, base, loc)
    aggregate_encoding = encodings.wtype_to_encoding(aggregate_wtype, loc)
    assert isinstance(aggregate_encoding, encodings.ArrayEncoding | encodings.TupleEncoding)
    element_encoding = _get_aggregate_element_encoding(aggregate_encoding, indexes, loc)
    if element_encoding.is_bit:
        read_result_type: types.IRType = types.bool_
    else:
        read_result_type = types.EncodedType(element_encoding)
    read_index = ir.ExtractValue(
        base=base,
        base_type=types.EncodedType(aggregate_encoding),
        ir_type=read_result_type,
        indexes=indexes,
        source_location=loc,
        check_bounds=check_bounds,
    )
    is_tup = isinstance(aggregate_encoding, encodings.TupleEncoding)
    (tuple_item,) = context.materialise_value_provider(
        read_index, "tuple_item" if is_tup else "array_item"
    )
    element_wtype = _get_nested_element_wtype(aggregate_wtype, indexes, loc)
    element_ir_type = types.wtype_to_ir_type(element_wtype, loc, allow_tuple=True)
    values = context.materialise_value_provider(
        ir.DecodeBytes.maybe(
            value=tuple_item,
            encoding=element_encoding,
            ir_type=element_ir_type,
            source_location=loc,
        ),
        "values",
    )
    if not isinstance(element_ir_type, types.TupleIRType):
        (value,) = values
        return value
    else:
        return ir.ValueTuple(values=values, ir_type=element_ir_type, source_location=loc)


def encode_and_write_aggregate_index(
    context: IRRegisterContext,
    aggregate_wtype: WAggregate,
    base: ir.MultiValue,
    indexes: Sequence[int | ir.Value],
    values: Sequence[ir.Value],
    loc: SourceLocation,
) -> ir.MultiValue:
    if isinstance(aggregate_wtype, wtypes.WTuple):
        (index,) = indexes
        assert isinstance(index, int)
        tuple_ir_type = types.wtype_to_ir_type(aggregate_wtype, loc, allow_tuple=True)
        skip_values = sum(e.arity for e in tuple_ir_type.elements[:index])
        target_arity = tuple_ir_type.elements[index].arity
        new_values = context.materialise_value_provider(base, "new_values")
        new_values[skip_values : skip_values + target_arity] = values
        return ir.ValueTuple(values=new_values, ir_type=tuple_ir_type, source_location=loc)
    (aggregate_or_slot,) = context.materialise_value_provider(base, "base")
    aggregate_encoding = encodings.wtype_to_encoding(aggregate_wtype, loc)
    assert isinstance(aggregate_encoding, encodings.TupleEncoding | encodings.ArrayEncoding)
    element_wtype = _get_nested_element_wtype(aggregate_wtype, indexes, loc)
    element_ir_type = types.wtype_to_ir_type(element_wtype, loc, allow_tuple=True)
    element_encoding = _get_aggregate_element_encoding(aggregate_encoding, indexes, loc)
    (encoded_value,) = context.materialise_value_provider(
        ir.BytesEncode.maybe(
            values=values,
            encoding=element_encoding,
            values_type=element_ir_type,
            source_location=loc,
        ),
        "encoded_value",
    )
    desc = (
        "updated_tuple"
        if isinstance(aggregate_encoding, encodings.TupleEncoding)
        else "updated_array"
    )
    if isinstance(aggregate_or_slot.ir_type, types.SlotType):
        write_index = ir.ReplaceValue(
            base=mem.read_slot(context, aggregate_or_slot, loc),
            base_type=types.EncodedType(aggregate_encoding),
            indexes=indexes,
            value=encoded_value,
            source_location=loc,
        )
        (updated_array,) = context.materialise_value_provider(write_index, desc)
        mem.write_slot(context, aggregate_or_slot, updated_array, loc)
        return aggregate_or_slot
    else:
        write_index = ir.ReplaceValue(
            base=aggregate_or_slot,
            base_type=types.EncodedType(aggregate_encoding),
            indexes=indexes,
            value=encoded_value,
            source_location=loc,
        )
        (updated_array,) = context.materialise_value_provider(write_index, desc)
        return updated_array


def get_length(
    array_encoding: encodings.ArrayEncoding,
    array_or_slot: ir.Value,
    loc: SourceLocation | None,
) -> ir.ArrayLength:
    return ir.ArrayLength(
        base=array_or_slot,
        base_type=array_or_slot.ir_type,
        array_encoding=array_encoding,
        source_location=loc,
    )


def convert_array(
    context: IRRegisterContext,
    source: ir.Value,
    *,
    source_wtype: wtypes.ARC4Array | wtypes.ReferenceArray,
    target_wtype: wtypes.ARC4Array | wtypes.ReferenceArray,
    loc: SourceLocation,
) -> ir.ValueProvider:
    factory = OpFactory(context, loc)

    target_ir_type = types.wtype_to_ir_type(target_wtype, loc)
    target_encoding = encodings.wtype_to_encoding(target_wtype, loc)
    source_encoding = encodings.wtype_to_encoding(source_wtype, loc)

    if isinstance(source.ir_type, types.SlotType):
        source = mem.read_slot(context, source, loc)
    source_length = factory.materialise_single(get_length(source_encoding, source, loc))

    match source_encoding.element, target_encoding.element:
        case (
            encodings.BoolEncoding(),
            encodings.Bool8Encoding(),
        ):
            logger.error(
                "converting from a bitpacked bool array"
                " to an non-bitpacked bool array is currently unsupported",
                location=loc,
            )
            return undefined_value(target_ir_type, loc)
        case (
            encodings.Bool8Encoding(),
            encodings.BoolEncoding(),
        ):
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
            source_encoding = encodings.ArrayEncoding.dynamic(
                encodings.BoolEncoding(), length_header=True
            )

    if target_encoding.element != source_encoding.element:
        logger.error(
            "array elements must have equivalent encoding to be convertible", location=loc
        )
        return undefined_value(target_ir_type, loc)

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
            return undefined_value(target_ir_type, loc)

    if isinstance(target_ir_type, types.SlotType):
        target_value_type = target_ir_type.contents
    else:
        target_value_type = target_ir_type
    if source_encoding.length_header and not target_encoding.length_header:
        new_value: ir.Value = factory.extract_to_end(source, 2, "converted_array")
    elif target_encoding.length_header and not source_encoding.length_header:
        len_value = factory.as_u16_bytes(source_length)
        new_value = factory.concat(
            len_value, source, temp_desc="converted_array", ir_type=target_value_type
        )
    else:
        new_value = source

    if isinstance(target_ir_type, types.SlotType):
        new_slot = mem.new_slot(context, target_ir_type, loc)
        mem.write_slot(context, new_slot, new_value, loc)
        return new_slot
    return new_value


def _get_nested_element_wtype(
    aggregate: WAggregate, indexes: Sequence[int | ir.Value], loc: SourceLocation
) -> wtypes.WType:
    element: wtypes.WType = aggregate
    reverse_indexes = list(reversed(indexes))
    while reverse_indexes:
        index = reverse_indexes.pop()
        if isinstance(
            element, wtypes.WTuple | wtypes.ARC4Tuple | wtypes.ARC4Struct
        ) and isinstance(index, int):
            element = element.types[index]
        elif isinstance(element, wtypes.ARC4Array | wtypes.ReferenceArray):
            element = element.element_type
        else:
            # invalid index sequence
            raise InternalError(f"invalid index sequence: {aggregate=!s}, {indexes=!s}", loc)
    return element


def _get_aggregate_element_encoding(
    aggregate_encoding: encodings.TupleEncoding | encodings.ArrayEncoding,
    indexes: Sequence[int | ir.Value],
    loc: SourceLocation | None,
) -> encodings.Encoding:
    element_encoding: encodings.Encoding = aggregate_encoding
    reverse_indexes = list(reversed(indexes))
    while reverse_indexes:
        index = reverse_indexes.pop()
        if isinstance(element_encoding, encodings.TupleEncoding) and isinstance(index, int):
            element_encoding = element_encoding.elements[index]
        elif isinstance(element_encoding, encodings.ArrayEncoding):
            element_encoding = element_encoding.element
        else:
            raise InternalError(
                f"invalid index sequence: {aggregate_encoding=!s}, {indexes=!s}", loc
            )
    return element_encoding
