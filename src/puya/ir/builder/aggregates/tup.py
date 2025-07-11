from puya import log
from puya.avm import AVMType
from puya.ir import models as ir
from puya.ir.encodings import TupleEncoding
from puya.ir.op_utils import OpFactory
from puya.ir.register_context import IRRegisterContext
from puya.parse import SourceLocation
from puya.utils import bits_to_bytes

logger = log.get_logger(__name__)


def read_at_index(
    context: IRRegisterContext,
    tuple_encoding: TupleEncoding,
    tup: ir.Value,
    index: int,
    loc: SourceLocation | None,
) -> ir.Value:
    factory = OpFactory(context, loc)

    # TODO: split by element_encoding
    element_encoding = tuple_encoding.elements[index]
    head_offset_bits = tuple_encoding.get_head_bit_offset(index)

    if element_encoding.is_bit:
        return factory.get_bit(tup, head_offset_bits)
    elif element_encoding.is_fixed:
        head_offset = bits_to_bytes(head_offset_bits)
        return factory.extract3(tup, head_offset, element_encoding.checked_num_bytes)
    else:
        assert element_encoding.is_dynamic, "expected dynamic encoding"

        head_offset = bits_to_bytes(head_offset_bits)
        item_start_offset = factory.extract_uint16(tup, head_offset)
        dynamic_head_offsets = _get_subsequent_dynamic_head_offsets(tuple_encoding, index)
        if not dynamic_head_offsets:
            item_end_offset = factory.len(tup)
        else:
            item_end_offset = factory.extract_uint16(tup, dynamic_head_offsets[0])
        return factory.substring3(tup, item_start_offset, item_end_offset)


def write_at_index(
    context: IRRegisterContext,
    tuple_encoding: TupleEncoding,
    tup: ir.Value,
    index: int,
    value: ir.Value,
    loc: SourceLocation | None,
) -> ir.Value:
    factory = OpFactory(context, loc)

    # TODO: split by element_encoding, as with read_at_index
    element_encoding = tuple_encoding.elements[index]
    head_offset_bits = tuple_encoding.get_head_bit_offset(index)

    if element_encoding.is_bit:
        assert value.ir_type.avm_type == AVMType.uint64, "expected bool value"
        return factory.set_bit(
            value=tup, index=head_offset_bits, bit=value, temp_desc="updated_data"
        )
    elif element_encoding.is_fixed:
        head_offset = bits_to_bytes(head_offset_bits)
        return factory.replace(tup, head_offset, value, "updated_data")
    else:
        assert element_encoding.is_dynamic, "expected dynamic encoding"

        head_offset = bits_to_bytes(head_offset_bits)
        item_offset = factory.extract_uint16(tup, head_offset, "item_offset")

        dynamic_head_offsets = _get_subsequent_dynamic_head_offsets(tuple_encoding, index)
        data_up_to_item = factory.extract3(tup, 0, item_offset, "data_up_to_item")
        result = factory.concat(data_up_to_item, value, "updated_data")
        if dynamic_head_offsets:
            # If there are subsequent dynamic elements in this tuple, we need to append their
            # existing tail data, and also update their offsets in the header
            next_item_offset = factory.extract_uint16(
                tup, dynamic_head_offsets[0], "next_item_offset"
            )
            data_beyond_item = factory.extract_to_end(tup, next_item_offset, "data_beyond_item")
            result = factory.concat(result, data_beyond_item, "updated_data")

            # loop through head and update any offsets after modified item
            old_value_length = factory.sub(next_item_offset, item_offset, "old_value_length")
            new_value_length = factory.len(value, "new_value_length")
            for dynamic_head_offset in dynamic_head_offsets:
                tail_offset = factory.extract_uint16(tup, dynamic_head_offset, "tail_offset")
                # have to add the new length and then subtract the original to avoid underflow
                tail_offset = factory.add(tail_offset, new_value_length, "tail_offset")
                tail_offset = factory.sub(tail_offset, old_value_length, "tail_offset")
                tail_offset_u16 = factory.as_u16_bytes(tail_offset, "tail_offset_bytes")

                result = factory.replace(
                    result, dynamic_head_offset, tail_offset_u16, "updated_data"
                )
        return result


def _get_subsequent_dynamic_head_offsets(tuple_encoding: TupleEncoding, index: int) -> list[int]:
    tuple_elements = tuple_encoding.elements
    next_index = index + 1
    return [
        bits_to_bytes(tuple_encoding.get_head_bit_offset(idx))
        for idx, elem in enumerate(tuple_elements[next_index:], start=next_index)
        if elem.is_dynamic
    ]
