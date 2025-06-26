from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.errors import InternalError
from puya.ir import models as ir
from puya.ir._puya_lib import PuyaLibIR
from puya.ir.builder import mem
from puya.ir.builder._utils import invoke_puya_lib_subroutine, undefined_value
from puya.ir.encodings import (
    ArrayEncoding,
    Bool8Encoding,
    BoolEncoding,
    Encoding,
    TupleEncoding,
    wtype_to_encoding,
)
from puya.ir.op_utils import OpFactory, assert_value
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

WAggregate = (
    wtypes.ARC4Tuple | wtypes.ARC4Struct | wtypes.WTuple | wtypes.ARC4Array | wtypes.ReferenceArray
)


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
        tuple_ir_type = wtype_to_ir_type(aggregate_wtype, loc, allow_tuple=True)
        skip_values = sum(e.arity for e in tuple_ir_type.elements[:index])
        target_arity = tuple_ir_type.elements[index].arity
        element_values = values[skip_values : skip_values + target_arity]

        if len(element_values) == 1:
            return element_values[0]
        else:
            return ir.ValueTuple(values=element_values, source_location=loc)

    (base,) = values
    if isinstance(base.ir_type, SlotType):
        base = mem.read_slot(context, base, loc)
    aggregate_encoding = wtype_to_encoding(aggregate_wtype, loc)
    assert isinstance(aggregate_encoding, ArrayEncoding | TupleEncoding)
    element_encoding = _get_aggregate_element_encoding(aggregate_encoding, indexes, loc)
    if element_encoding.is_bit:
        read_result_type: IRType = PrimitiveIRType.bool
    else:
        read_result_type = EncodedType(element_encoding)
    read_index = ir.ExtractValue(
        base=base,
        base_type=EncodedType(aggregate_encoding),
        ir_type=read_result_type,
        indexes=indexes,
        source_location=loc,
        check_bounds=check_bounds,
    )
    is_tup = isinstance(aggregate_encoding, TupleEncoding)
    (tuple_item,) = context.materialise_value_provider(
        read_index, "tuple_item" if is_tup else "array_item"
    )
    element_ir_type = _get_nested_element_ir_type(aggregate_wtype, indexes, loc)
    if requires_no_conversion(element_ir_type, element_encoding):
        return tuple_item
    else:
        values = context.materialise_value_provider(
            ir.DecodeBytes(
                value=tuple_item,
                encoding=element_encoding,
                ir_type=element_ir_type,
                source_location=loc,
            ),
            "values",
        )
        if len(values) == 1:
            return values[0]
        else:
            return ir.ValueTuple(values=values, source_location=loc)


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
        tuple_ir_type = wtype_to_ir_type(aggregate_wtype, loc, allow_tuple=True)
        skip_values = sum(e.arity for e in tuple_ir_type.elements[:index])
        target_arity = tuple_ir_type.elements[index].arity
        new_values = context.materialise_value_provider(base, "new_values")
        new_values[skip_values : skip_values + target_arity] = values
        if len(new_values) == 1:
            return new_values[0]
        else:
            return ir.ValueTuple(values=new_values, source_location=loc)
    (base,) = context.materialise_value_provider(base, "base")
    aggregate_or_slot = base
    aggregate_encoding = wtype_to_encoding(aggregate_wtype, loc)
    assert isinstance(aggregate_encoding, TupleEncoding | ArrayEncoding)
    element_ir_type = _get_nested_element_ir_type(aggregate_wtype, indexes, loc)
    element_encoding = _get_aggregate_element_encoding(aggregate_encoding, indexes, loc)
    if requires_no_conversion(element_ir_type, element_encoding):
        (encoded_value,) = values
    else:
        (encoded_value,) = context.materialise_value_provider(
            ir.BytesEncode(
                values=values,
                encoding=element_encoding,
                values_type=element_ir_type,
                source_location=loc,
            ),
            "encoded_value",
        )
    desc = "updated_tuple" if isinstance(aggregate_encoding, TupleEncoding) else "updated_array"
    if isinstance(aggregate_or_slot.ir_type, SlotType):
        base = mem.read_slot(context, aggregate_or_slot, loc)
        write_index = ir.ReplaceValue(
            base=base,
            base_type=EncodedType(aggregate_encoding),
            indexes=indexes,
            value=encoded_value,
            source_location=loc,
        )
        (result,) = context.materialise_value_provider(write_index, desc)
        mem.write_slot(context, aggregate_or_slot, result, loc)
        return aggregate_or_slot
    else:
        write_index = ir.ReplaceValue(
            base=base,
            base_type=EncodedType(aggregate_encoding),
            indexes=indexes,
            value=encoded_value,
            source_location=loc,
        )
        (result,) = context.materialise_value_provider(write_index, desc)
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
    if array_encoding.size is not None:
        return factory.constant(array_encoding.size)
    elif array_encoding.length_header:
        return factory.extract_uint16(array, 0, "array_length")
    assert array_encoding.size is None, "expected dynamic array"
    bytes_len = factory.len(array, "bytes_len")
    return factory.div_floor(bytes_len, array_encoding.element.checked_num_bytes, "array_len")


def requires_no_conversion(
    typ: IRType | TupleIRType,
    encoding: Encoding,
) -> bool:
    match typ:
        case PrimitiveIRType.bool | EncodedType(encoding=BoolEncoding()) if encoding.is_bit:
            return True
        case EncodedType(encoding=typ_encoding) if typ_encoding == encoding:
            return True
        case _:
            return False


def convert_array(
    context: IRRegisterContext,
    source: ir.Value,
    *,
    source_wtype: wtypes.ARC4Array | wtypes.ReferenceArray,
    target_wtype: wtypes.ARC4Array | wtypes.ReferenceArray,
    loc: SourceLocation,
) -> ir.ValueProvider:
    factory = OpFactory(context, loc)

    target_ir_type = wtype_to_ir_type(target_wtype, loc)
    target_encoding = wtype_to_encoding(target_wtype, loc)
    source_encoding = wtype_to_encoding(source_wtype, loc)

    if isinstance(source.ir_type, SlotType):
        source = mem.read_slot(context, source, loc)
    source_length = get_length(context, source_encoding, source, loc)

    match source_encoding.element, target_encoding.element:
        case (
            BoolEncoding(),
            Bool8Encoding(),
        ):
            logger.error(
                "converting from a bitpacked bool array"
                " to an non-bitpacked bool array is currently unsupported",
                location=loc,
            )
            return undefined_value(target_ir_type, loc)
        case (
            Bool8Encoding(),
            BoolEncoding(),
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
            source_encoding = ArrayEncoding.dynamic(BoolEncoding(), length_header=True)

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


def _get_nested_element_ir_type(
    aggregate: WAggregate, indexes: Sequence[int | ir.Value], loc: SourceLocation
) -> IRType | TupleIRType:
    last_i = len(indexes) - 1
    element = None
    for i, index in enumerate(indexes):
        if isinstance(
            aggregate, wtypes.WTuple | wtypes.ARC4Tuple | wtypes.ARC4Struct
        ) and isinstance(index, int):
            element = aggregate.types[index]
        elif isinstance(aggregate, wtypes.ARC4Array | wtypes.ReferenceArray):
            element = aggregate.element_type
        else:
            # invalid index sequence
            raise InternalError(f"invalid index sequence: {aggregate=!s}, {index=!s}", loc)
        # indexes must point to aggregates except for the final encoding
        if i == last_i:
            # last index can be any encoding
            pass
        elif isinstance(element, WAggregate):
            aggregate = element
        else:
            # invalid index sequence
            raise InternalError(f"invalid index sequence: {aggregate=!s}, {index=!s}", loc)
    if element is None:
        raise InternalError(f"invalid index sequence: {aggregate=!s}, {indexes=!s}", loc)
    return wtype_to_ir_type(element, loc, allow_tuple=True)


def _get_aggregate_element_encoding(
    aggregate_encoding: TupleEncoding | ArrayEncoding,
    indexes: Sequence[int | ir.Value],
    loc: SourceLocation | None,
) -> Encoding:
    last_i = len(indexes) - 1
    element_encoding = None
    for i, index in enumerate(indexes):
        if isinstance(aggregate_encoding, TupleEncoding) and isinstance(index, int):
            element_encoding = aggregate_encoding.elements[index]
        elif isinstance(aggregate_encoding, ArrayEncoding):
            element_encoding = aggregate_encoding.element
        else:
            raise InternalError(
                f"invalid index sequence: {aggregate_encoding=!s}, {index=!s}", loc
            )
        if i == last_i:
            # last index is the only one that doesn't need to be an aggregate
            pass
        elif isinstance(element_encoding, TupleEncoding | ArrayEncoding):
            aggregate_encoding = element_encoding
        else:
            # invalid index sequence
            raise InternalError(
                f"invalid index sequence: {aggregate_encoding=!s}, {index=!s}", loc
            )
    if element_encoding is None:
        raise InternalError(f"invalid index sequence: {aggregate_encoding=!s}, {indexes=!s}", loc)
    return element_encoding
