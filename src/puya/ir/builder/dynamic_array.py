import typing

import attrs

from puya import log
from puya.awst import wtypes
from puya.errors import CodeError, InternalError
from puya.ir import (
    encodings,
    models as ir,
    types_ as types,
)
from puya.ir.builder.sequence import get_length
from puya.ir.models import ValueProvider
from puya.ir.op_utils import OpFactory
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import EncodedType
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def concat(
    context: IRRegisterContext,
    *,
    wtype: wtypes.WType,
    array: ir.Value,
    iterable: ir.MultiValue,
    iterable_ir_type: types.IRType | types.TupleIRType,
    loc: SourceLocation,
) -> ir.Value:
    if not isinstance(iterable_ir_type, types.EncodedType | types.TupleIRType):
        raise InternalError("expected encoded type or tuple type for concatenation", loc)

    array_encoding = _get_array_encoding(wtype, loc)
    encoded_iterable = _get_encoded_items(context, array_encoding, iterable, iterable_ir_type, loc)
    result = ir.ArrayConcat(
        base=array,
        base_type=types.EncodedType(array_encoding),
        items=encoded_iterable.items,
        num_items=encoded_iterable.num_items,
        item_encoding=encoded_iterable.item_encoding,
        source_location=loc,
    )
    factory = OpFactory(context, loc)
    return factory.materialise_single(result)


def pop(
    context: IRRegisterContext,
    *,
    wtype: wtypes.WType,
    array: ir.Value,
    loc: SourceLocation,
) -> tuple[ir.Value, ir.MultiValue]:
    array_encoding = _get_array_encoding(wtype, loc)
    assert isinstance(wtype, wtypes.ReferenceArray | wtypes.ARC4DynamicArray)
    element_encoding = array_encoding.element
    # we don't allow pop for UTF8 encodings since there are no UTF8 primitives in the AVM
    if type(element_encoding) is encodings.UTF8Encoding:
        raise CodeError("unsupported pop operation", loc)
    pop_element_ir_type = types.wtype_to_ir_type(
        wtype.element_type, source_location=loc, allow_tuple=True
    )
    factory = OpFactory(context, loc)
    array_len = factory.materialise_single(get_length(array_encoding, array, loc))
    last_index = factory.sub(array_len, 1)
    array_type = types.EncodedType(array_encoding)
    if array_encoding.element.is_bit:
        ir_type: types.IRType = types.bool_
    else:
        ir_type = types.EncodedType(array_encoding.element)
    encoded_item = factory.materialise_single(
        ir.ExtractValue(
            base=array,
            base_type=array_type,
            ir_type=ir_type,
            check_bounds=False,
            indexes=(last_index,),
            source_location=loc,
        )
    )
    popped_array = ir.ArrayPop(base=array, base_type=array_type, source_location=loc)
    popped = factory.materialise_multi_value(
        ir.DecodeBytes.maybe(
            value=encoded_item,
            encoding=array_encoding.element,
            ir_type=pop_element_ir_type,
            source_location=loc,
        )
    )
    return factory.materialise_single(popped_array), popped


def _get_array_encoding(wtype: wtypes.WType, loc: SourceLocation) -> encodings.ArrayEncoding:
    if not isinstance(wtype, wtypes.ReferenceArray | wtypes.ARC4DynamicArray):
        raise InternalError(f"unsupported array type: {wtype!s}", loc)
    array_ir_type = types.wtype_to_ir_type(wtype, source_location=loc)
    # only concerned with actual encoding of arrays, not where they are stored
    if isinstance(array_ir_type, types.SlotType):
        array_ir_type = array_ir_type.contents
    assert isinstance(array_ir_type, types.EncodedType), "expected EncodedType"
    array_encoding = array_ir_type.encoding
    assert (
        isinstance(array_encoding, encodings.ArrayEncoding) and array_encoding.size is None
    ), "expected DynamicArray encoding"
    return array_encoding


@attrs.frozen
class _EncodedItems:
    items: ir.Value
    num_items: ir.Value
    item_encoding: encodings.Encoding


def _get_encoded_items(
    context: IRRegisterContext,
    array_encoding: encodings.ArrayEncoding,
    iterable: ir.ValueProvider,
    iterable_ir_type: types.EncodedType | types.TupleIRType,
    loc: SourceLocation,
) -> _EncodedItems:
    """
    Given an iterable and type, returns an encoded iterable suitable for use
    with the ir.ArrayConcat node
    """
    if isinstance(iterable_ir_type, types.EncodedType):
        if encodings.is_byte_length_dynamic_array(array_encoding.element):
            return _get_encoded_byte_length_items_from_encoded_type(
                context, array_encoding, iterable, iterable_ir_type, loc
            )
        else:
            return _get_encoded_items_from_encoded_type(
                context, array_encoding, iterable, iterable_ir_type, loc
            )
    else:
        typing.assert_type(iterable_ir_type, types.TupleIRType)
        if encodings.is_byte_length_dynamic_array(array_encoding.element):
            return _get_encoded_byte_length_items_from_tuple_type(
                context, array_encoding, iterable, iterable_ir_type, loc
            )
        else:
            return _get_encoded_items_from_tuple_type(
                context, array_encoding, iterable, iterable_ir_type, loc
            )


def _get_encoded_items_from_encoded_type(
    context: IRRegisterContext,
    array_encoding: encodings.ArrayEncoding,
    iterable: ValueProvider,
    iterable_ir_type: EncodedType,
    loc: SourceLocation,
) -> _EncodedItems:
    factory = OpFactory(context, loc)
    iterable = factory.materialise_single(iterable)
    iterable_encoding = iterable_ir_type.encoding
    match iterable_encoding:
        case encodings.ArrayEncoding():
            length = get_length(iterable_encoding, iterable, factory.source_location)
            if iterable_encoding.length_header:
                iterable = factory.extract_to_end(iterable, 2)
            return _EncodedItems(
                items=iterable,
                num_items=factory.materialise_single(length),
                item_encoding=iterable_encoding.element,
            )
        case encodings.TupleEncoding() if len(set(iterable_encoding.elements)) == 1:
            return _EncodedItems(
                items=iterable,
                num_items=factory.constant(len(iterable_encoding.elements)),
                item_encoding=iterable_encoding.elements[0],
            )
        case _:
            logger.error(
                f"cannot concat {array_encoding} and {iterable_encoding}",
                location=loc,
            )
            return _EncodedItems(
                items=iterable,
                num_items=ir.Undefined(ir_type=types.uint64, source_location=loc),
                item_encoding=iterable_encoding,
            )


def _get_encoded_byte_length_items_from_encoded_type(
    context: IRRegisterContext,
    array_encoding: encodings.ArrayEncoding,
    iterable: ValueProvider,
    iterable_ir_type: EncodedType,
    loc: SourceLocation,
) -> _EncodedItems:
    encoded_iterable = _get_encoded_items_from_encoded_type(
        context, array_encoding, iterable, iterable_ir_type, loc
    )
    factory = OpFactory(context, loc)
    # existing encoded items, byte length items should just be the tail portion
    start_of_tail = factory.mul(encoded_iterable.num_items, 2, "start_of_tail")
    r_tail = factory.extract_to_end(encoded_iterable.items, start_of_tail, "data")
    return _EncodedItems(
        num_items=encoded_iterable.num_items,
        items=r_tail,
        item_encoding=array_encoding.element,
    )


def _get_encoded_items_from_tuple_type(
    context: IRRegisterContext,
    array_encoding: encodings.ArrayEncoding,
    iterable: ir.ValueProvider,
    iterable_ir_type: types.TupleIRType,
    loc: SourceLocation,
) -> _EncodedItems:
    if len(set(iterable_ir_type.elements)) != 1:
        raise InternalError("expected homogenous tuple for concatenation", loc)
    factory = OpFactory(context, loc)
    # the iterable could be either
    # a tuple of compatible native elements
    # a tuple of compatible encoded elements
    # all of which can be encoded as a dynamic array of the element
    element_encoding = array_encoding.element
    encoded_iterable = ir.BytesEncode.maybe(
        values=factory.materialise_values(iterable),
        values_type=iterable_ir_type,
        encoding=encodings.ArrayEncoding.dynamic(element=element_encoding, length_header=False),
        source_location=loc,
    )
    return _EncodedItems(
        num_items=factory.constant(len(iterable_ir_type.elements)),
        items=factory.materialise_single(encoded_iterable),
        item_encoding=element_encoding,
    )


def _get_encoded_byte_length_items_from_tuple_type(
    context: IRRegisterContext,
    array_encoding: encodings.ArrayEncoding,
    iterable: ir.ValueProvider,
    iterable_ir_type: types.TupleIRType,
    loc: SourceLocation,
) -> _EncodedItems:
    factory = OpFactory(context, loc)
    tuple_size = len(iterable_ir_type.elements)
    # only need to construct the tail, so iterate and concat
    r_tail = factory.constant(b"")
    values = factory.materialise_values(iterable)
    (element_ir_type,) = set(iterable_ir_type.elements)
    element_encoding = array_encoding.element
    for _ in range(tuple_size):
        encoded_element_vp = ir.BytesEncode.maybe(
            values=values[: element_ir_type.arity],
            encoding=element_encoding,
            values_type=element_ir_type,
            source_location=loc,
        )
        encoded_element = factory.materialise_single(encoded_element_vp)
        r_tail = factory.concat(r_tail, encoded_element)
        values = values[element_ir_type.arity :]
    assert not values, "too many values to encode"
    return _EncodedItems(
        num_items=factory.constant(tuple_size),
        items=r_tail,
        item_encoding=element_encoding,
    )
