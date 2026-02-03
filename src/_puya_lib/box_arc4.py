from algopy import Bytes, UInt64, op, subroutine


@subroutine
def box_dynamic_array_pop_fixed_size(
    box_key: Bytes, array_offset: UInt64, fixed_byte_size: UInt64
) -> None:
    """
    Modifies a box's content by popping the last element of an
    ARC-4 dynamic array of fixed size elements

    box_key: The box_key to manipulate
    array_offset: The offset in bytes to the start of the array
    fixed_byte_size: The size in bytes of the array element
    """
    # update length header of array
    arr_len = _box_extract_u16(box_key, array_offset)
    new_arr_len = arr_len - 1  # on error: empty array
    index = new_arr_len  # TODO: support popping by index by making this an argument
    new_arr_len_u16 = _as_uint16(new_arr_len)
    op.Box.replace(box_key, array_offset, new_arr_len_u16)

    # remove element from array
    popped_item_offset = array_offset + 2 + index * fixed_byte_size
    op.Box.splice(box_key, popped_item_offset, fixed_byte_size, b"")

    # shrink box by element size
    box_size, _exists = op.Box.length(box_key)
    new_size = box_size - fixed_byte_size
    op.Box.resize(box_key, new_size)


@subroutine
def box_dynamic_array_concat_fixed(
    box_key: Bytes,
    array_offset: UInt64,
    new_items_bytes: Bytes,
    new_items_count: UInt64,
    fixed_element_size: UInt64,
) -> None:
    """
    Modifies a box's content by concatenating data to an arc4 dynamic array of fixed size elements

    box_key: The box_key to manipulate
    array_offset: The offset in bytes to the start of the array
    new_items_count: The count of new items being added (N)
    new_items_bytes: The concatenated bytes of N array elements
    """
    # increase box size to accommodate num_items
    arr_len = _box_extract_u16(box_key, array_offset)
    box_size, _exists = op.Box.length(box_key)
    new_box_size = box_size + new_items_count * fixed_element_size
    op.Box.resize(box_key, new_box_size)

    # update array length header with new count
    new_arr_len = _as_uint16(arr_len + new_items_count)
    op.Box.replace(box_key, array_offset, new_arr_len)

    # splice in new items at end of current array
    end_of_array_offset = array_offset + 2 + arr_len * fixed_element_size
    op.Box.splice(box_key, end_of_array_offset, 0, new_items_bytes)


@subroutine
def box_update_offset_dec(box_key: Bytes, offset: UInt64, value: UInt64) -> None:
    """
    Decrements a ARC-4 head pointer (uint16) in a box, used when removing data from an
    ARC-4 tuple, e.g. when popping an array

    box_key: The box_key to manipulate
    offset: The offset in bytes to the pointer
    value: The amount to decrement by
    """
    offset_value = _box_extract_u16(box_key, offset)
    new_offset_value = offset_value - value
    new_offset_value_u16 = _as_uint16(new_offset_value)
    op.Box.replace(box_key, offset, new_offset_value_u16)


@subroutine
def box_update_offset_inc(box_key: Bytes, offset: UInt64, value: UInt64) -> None:
    """
    Increments a ARC-4 head pointer (uint16) in a box, used when adding data to an
    ARC-4 tuple, e.g. when extending an array

    box_key: The box_key to manipulate
    offset: The offset in bytes to the pointer
    value: The amount to increment by
    """
    offset_value = _box_extract_u16(box_key, offset)
    new_offset_value = offset_value + value
    new_offset_value_u16 = _as_uint16(new_offset_value)
    op.Box.replace(box_key, offset, new_offset_value_u16)


@subroutine(inline=True)
def _box_extract_u16(box_key: Bytes, offset: UInt64) -> UInt64:
    arr_len_bytes = op.Box.extract(box_key, offset, 2)
    return op.btoi(arr_len_bytes)


@subroutine(inline=True)
def _as_uint16(value: UInt64) -> Bytes:
    value_bytes = op.itob(value)
    return op.extract(value_bytes, 6, 2)
