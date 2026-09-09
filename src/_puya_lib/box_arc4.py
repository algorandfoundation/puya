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


@subroutine(inline=True)
def _bits_to_bytes(num_bits: UInt64) -> UInt64:
    return (num_bits + 7) // 8


@subroutine
def box_dynamic_array_pop_bit(box_key: Bytes, array_offset: UInt64) -> UInt64:
    """
    Modifies a box's content by popping the last element of an
    ARC-4 dynamic array of bit packed booleans

    box_key: The box_key to manipulate
    array_offset: The offset in bytes to the start of the array

    returns: The number of bytes the array shrunk by (0 or 1)
    """
    # update length header of array
    arr_len = _box_extract_u16(box_key, array_offset)
    new_arr_len = arr_len - 1  # on error: empty array
    new_arr_len_u16 = _as_uint16(new_arr_len)
    op.Box.replace(box_key, array_offset, new_arr_len_u16)

    # the popped bit is the last bit of the array data
    byte_offset = array_offset + 2 + new_arr_len // 8
    bit_offset = new_arr_len % 8
    if bit_offset == 0:
        # popped bit was the only bit in the last byte, so remove that byte entirely
        op.Box.splice(box_key, byte_offset, 1, b"")
        box_size, _exists = op.Box.length(box_key)
        op.Box.resize(box_key, box_size - 1)
        return UInt64(1)
    # otherwise clear the popped bit so padding bits remain zero
    byte = op.Box.extract(box_key, byte_offset, 1)
    byte = op.setbit_bytes(byte, bit_offset, False)  # noqa: FBT003
    op.Box.replace(box_key, byte_offset, byte)
    return UInt64(0)


@subroutine
def box_dynamic_array_concat_bits(
    box_key: Bytes,
    array_offset: UInt64,
    new_items_bytes: Bytes,
    new_items_count: UInt64,
    read_step: UInt64,
) -> UInt64:
    """
    Modifies a box's content by concatenating data to an arc4 dynamic array of
    bit packed booleans

    box_key: The box_key to manipulate
    array_offset: The offset in bytes to the start of the array
    new_items_bytes: Either the data portion of an arc4 packed array of booleans
                        or
                     a sparse array of concatenated arc4 booleans
    new_items_count: The count of new items being added
    read_step: How many bits to advance when reading new items,
               1 for packed bools or 8 for concatenated bools

    returns: The number of bytes the array grew by
    """
    arr_len = _box_extract_u16(box_key, array_offset)
    new_arr_len = arr_len + new_items_count
    # Bit packed arrays can exceed 65535 elements within a box, so prevent the
    # uint16 length header from wrapping.
    assert new_arr_len <= 65535, "max array length exceeded"
    data_offset = array_offset + 2
    current_bytes = _bits_to_bytes(arr_len)
    required_bytes = _bits_to_bytes(new_arr_len)
    extra_bytes = required_bytes - current_bytes

    # increase box size and insert zeroed bytes at the end of the current array data
    if extra_bytes:
        box_size, _exists = op.Box.length(box_key)
        op.Box.resize(box_key, box_size + extra_bytes)
        op.Box.splice(box_key, data_offset + current_bytes, 0, op.bzero(extra_bytes))

    # update array length header with new count
    new_arr_len_u16 = _as_uint16(new_arr_len)
    op.Box.replace(box_key, array_offset, new_arr_len_u16)

    # copy the new bits into the array, one byte of the box at a time
    read_offset = UInt64(0)
    write_offset = arr_len
    while write_offset < new_arr_len:
        byte_offset = data_offset + write_offset // 8
        bit_offset = write_offset % 8
        byte = op.Box.extract(box_key, byte_offset, 1)
        while bit_offset < 8 and write_offset < new_arr_len:
            byte = op.setbit_bytes(byte, bit_offset, op.getbit(new_items_bytes, read_offset))
            bit_offset += 1
            write_offset += 1
            read_offset += read_step
        op.Box.replace(box_key, byte_offset, byte)
    return extra_bytes
