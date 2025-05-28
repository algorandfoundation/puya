from puya import log
from puya.ir import models as ir
from puya.ir.builder._utils import OpFactory
from puya.ir.encodings import (
    TupleEncoding,
)
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
    tuple_elements = tuple_encoding.elements
    element_encoding = tuple_elements[index]
    head_offset_bits = tuple_encoding.get_head_bit_offset(index)
    if element_encoding.is_bit:
        return factory.get_bit(tup, head_offset_bits)
    elif not element_encoding.is_dynamic:
        head_offset = bits_to_bytes(head_offset_bits)
        return factory.extract3(tup, head_offset, element_encoding.checked_num_bytes)
    else:
        head_offset = bits_to_bytes(head_offset_bits)
        item_start_offset = factory.extract_uint16(tup, head_offset)

        next_index = index + 1
        for tuple_item_index, tuple_item_type in enumerate(
            tuple_elements[next_index:], start=next_index
        ):
            if tuple_item_type.is_dynamic:
                next_dynamic_head_offset_bits = tuple_encoding.get_head_bit_offset(
                    tuple_item_index
                )
                next_dynamic_head_offset = bits_to_bytes(next_dynamic_head_offset_bits)
                item_end_offset = factory.extract_uint16(tup, next_dynamic_head_offset)
                break
        else:
            item_end_offset = factory.len(tup)
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
    element_encoding = tuple_encoding.elements[index]

    if element_encoding.is_bit:
        # Use Set bit
        is_true = factory.get_bit(value, 0, "is_true")
        return factory.set_bit(
            value=tup,
            index=tuple_encoding.get_head_bit_offset(index),
            bit=is_true,
            temp_desc="updated_data",
        )
    header_up_to_item_bytes = bits_to_bytes(tuple_encoding.get_head_bit_offset(index))
    if not element_encoding.is_dynamic:
        return factory.replace(
            tup,
            header_up_to_item_bytes,
            value,
            "updated_data",
        )
    assert element_encoding.is_dynamic, "expected dynamic encoding"
    dynamic_indices = [index for index, t in enumerate(tuple_encoding.elements) if t.is_dynamic]

    item_offset = factory.extract_uint16(tup, header_up_to_item_bytes, "item_offset")
    data_up_to_item = factory.extract3(tup, 0, item_offset, "data_up_to_item")
    dynamic_indices_after_item = [i for i in dynamic_indices if i > index]

    if not dynamic_indices_after_item:
        # This is the last dynamic type in the tuple
        # No need to update headers - just replace the data
        return factory.concat(data_up_to_item, value, "updated_data")
    header_up_to_next_dynamic_item = bits_to_bytes(
        tuple_encoding.get_head_bit_offset(dynamic_indices_after_item[0])
    )

    # update tail portion with new item
    next_item_offset = factory.extract_uint16(
        tup,
        header_up_to_next_dynamic_item,
        "next_item_offset",
    )
    total_data_length = factory.len(tup, "total_data_length")
    data_beyond_item = factory.substring3(
        tup,
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
        header_up_to_dynamic_item = bits_to_bytes(
            tuple_encoding.get_head_bit_offset(dynamic_index)
        )

        tail_offset = factory.extract_uint16(
            updated_data, header_up_to_dynamic_item, "tail_offset"
        )
        # have to add the new length and then subtract the original to avoid underflow
        tail_offset = factory.add(tail_offset, new_value_length, "tail_offset")
        tail_offset = factory.sub(tail_offset, item_length, "tail_offset")
        tail_offset_bytes = factory.as_u16_bytes(tail_offset, "tail_offset_bytes")

        updated_data = factory.replace(
            updated_data, header_up_to_dynamic_item, tail_offset_bytes, "updated_data"
        )
    return updated_data
