from algopy import (
    Bytes,
    UInt64,
    subroutine,
    urange,
)
from algopy.op import (
    btoi,
    bzero,
    extract,
    extract_uint16,
    getbit,
    itob,
    replace,
    select_uint64,
    setbit_bytes,
    substring,
)

UINT16_SIZE = 2
UINT64_SIZE = 8
UINT16_OFFSET = UINT64_SIZE - UINT16_SIZE


@subroutine
def dynamic_array_pop_bit(array: Bytes) -> tuple[Bytes, Bytes]:
    """
    Pop the last item from an arc4 dynamic array of arc4 encoded boolean items

    array: The bytes for the source array

    returns: tuple of (The popped item, The updated bytes for the source array)
    """
    array_length = extract_uint16(array, 0)
    length_minus_1 = array_length - 1
    result = replace(array, 0, extract(itob(length_minus_1), UINT16_OFFSET, 0))
    popped_location = length_minus_1 + UINT16_SIZE * 8
    popped = setbit_bytes(b"\x00", 0, getbit(result, popped_location))
    result = setbit_bytes(result, popped_location, 0)
    result = substring(result, 0, UINT16_SIZE + ((length_minus_1 + 7) // 8))
    return popped, result


@subroutine
def dynamic_array_pop_fixed_size(array: Bytes, fixed_byte_size: UInt64) -> tuple[Bytes, Bytes]:
    """
    Pop the last item from an arc4 dynamic array of fixed sized items

    array: The bytes for the source array

    returns: tuple of (The popped item, The updated bytes for the source array)
    """
    array_length = extract_uint16(array, 0)
    length_minus_1 = array_length - 1
    result = replace(array, 0, extract(itob(length_minus_1), UINT16_OFFSET, 0))
    item_location = result.length - fixed_byte_size
    popped = extract(result, item_location, fixed_byte_size)
    result = substring(result, 0, item_location)
    return popped, result


@subroutine
def dynamic_array_pop_byte_length_head(array: Bytes) -> tuple[Bytes, Bytes]:
    """
    Pop the last item from an arc4 dynamic array of items that are prefixed with their length in
    bytes, e.g. arc4.String, arc4.DynamicBytes

    source: The bytes for the source array

    returns: tuple of (The popped item, The updated bytes for the source array)
    """
    array_length = extract_uint16(array, 0)
    length_minus_1 = array_length - 1
    popped_header_offset = length_minus_1 * UINT16_SIZE
    head_and_tail = extract(array, UINT16_SIZE, 0)
    popped_offset = extract_uint16(head_and_tail, popped_header_offset)

    popped = substring(head_and_tail, popped_offset, head_and_tail.length)
    head_and_tail = substring(head_and_tail, 0, popped_header_offset) + substring(
        head_and_tail, popped_header_offset + 2, popped_offset
    )

    updated = extract(
        itob(length_minus_1), UINT16_OFFSET, UINT16_SIZE
    ) + recalculate_head_for_elements_with_byte_length_head(
        array_head_and_tail=head_and_tail, length=length_minus_1, start_at_index=UInt64(0)
    )

    return popped, updated


@subroutine
def dynamic_array_pop_dynamic_element(array: Bytes) -> tuple[Bytes, Bytes]:
    """
    Pop the last item from an arc4 dynamic array of dynamically sized items

    array: The bytes for the source array

    returns: tuple of (The popped item, The updated bytes for the source array)
    """
    array_length = extract_uint16(array, 0)
    length_minus_1 = array_length - 1
    popped_header_offset = length_minus_1 * UINT16_SIZE
    head_and_tail = extract(array, UINT16_SIZE, 0)
    popped_offset = extract_uint16(head_and_tail, popped_header_offset)

    popped = substring(head_and_tail, popped_offset, head_and_tail.length)

    new_head = Bytes()
    for head_offset in urange(0, length_minus_1 * UINT16_SIZE, UINT16_SIZE):
        item_offset = extract_uint16(head_and_tail, head_offset)
        item_offset -= UINT16_SIZE
        new_head += extract(itob(item_offset), UINT16_OFFSET, UINT16_SIZE)

    updated = (
        extract(itob(length_minus_1), UINT16_OFFSET, UINT16_SIZE)
        + new_head
        + substring(head_and_tail, popped_header_offset + UINT16_SIZE, popped_offset)
    )

    return popped, updated


@subroutine
def dynamic_array_concat_bits(
    *, array: Bytes, new_items_bytes: Bytes, new_items_count: UInt64, is_packed: bool
) -> Bytes:
    """
    Concat data to an arc4 dynamic array of arc4 encoded boolean values

    array: The bytes for the source array
    new_items_bytes: Either the data portion of an arc4 packed array of booleans
                        or
                     a sparse array of concatenated arc4 booleans
    new_items_count: The count of new items being added
    is_packed: True if new_items_bytes represents a packed array, else False

    returns: The updated bytes for the source array
    """
    array_length = extract_uint16(array, 0)
    new_array_length = array_length + new_items_count
    new_array_length_b = extract(itob(new_array_length), UINT16_OFFSET, 0)
    result = replace(array, 0, new_array_length_b)
    current_bytes = (array_length + 7) // 8
    required_bytes = (new_array_length + 7) // 8
    if current_bytes < required_bytes:
        result += bzero(required_bytes - current_bytes)

    write_offset = array_length + 8 * UINT16_SIZE
    for i in urange(0, new_items_count, UInt64(1) if is_packed else UInt64(8)):
        result = setbit_bytes(result, write_offset, getbit(new_items_bytes, i))
        write_offset += 1

    return result


@subroutine
def dynamic_array_concat_byte_length_head(
    array: Bytes, new_items_bytes: Bytes, new_items_count: UInt64
) -> Bytes:
    """
    Replace a single item in an arc4 dynamic array of items that are prefixed with
    their byte length

    array: The bytes of the source array
    new_items_bytes: The bytes for all new items, concatenated
    new_items_counts: The count of new items being added

    returns: The updated bytes for the source array
    """
    array_length = extract_uint16(array, 0)
    new_length = array_length + new_items_count
    header_end = array_length * UINT16_SIZE + 2

    return extract(
        itob(new_length), UINT16_OFFSET, UINT16_SIZE
    ) + recalculate_head_for_elements_with_byte_length_head(
        array_head_and_tail=(
            substring(array, 2, header_end)
            + bzero(new_items_count * UINT16_SIZE)
            + substring(array, header_end, array.length)
            + new_items_bytes
        ),
        length=new_length,
        start_at_index=UInt64(0),
    )


@subroutine
def dynamic_array_concat_dynamic_element(
    *,
    array_items_count: UInt64,
    array_head_and_tail: Bytes,
    new_items_count: UInt64,
    new_head_and_tail: Bytes,
) -> Bytes:
    new_head = Bytes()
    item_offset_adjustment = new_items_count * UINT16_SIZE
    for head_offset in urange(0, array_items_count * UINT16_SIZE, UINT16_SIZE):
        item_offset = extract_uint16(array_head_and_tail, head_offset)
        new_head += extract(itob(item_offset_adjustment + item_offset), UINT16_OFFSET, UINT16_SIZE)

    item_offset_adjustment = array_head_and_tail.length
    for head_offset in urange(0, new_items_count * UINT16_SIZE, UINT16_SIZE):
        item_offset = extract_uint16(new_head_and_tail, head_offset)
        new_head += extract(itob(item_offset_adjustment + item_offset), UINT16_OFFSET, UINT16_SIZE)
    return (
        extract(itob(array_items_count + new_items_count), UINT16_OFFSET, UINT16_SIZE)
        + new_head
        + substring(
            array_head_and_tail, array_items_count * UINT16_SIZE, array_head_and_tail.length
        )
        + substring(new_head_and_tail, new_items_count * UINT16_SIZE, new_head_and_tail.length)
    )


@subroutine
def dynamic_array_replace_byte_length_head(array: Bytes, new_item: Bytes, index: UInt64) -> Bytes:
    """
    Replace a single item in an arc4 dynamic array of items that are prefixed with
    their byte length

    array: The bytes of the source array
    new_item: The bytes of the new item to be inserted
    index: The index to insert the new item at
    array_length: The length of the array

    returns: The updated bytes for the source array
    """
    size_b = substring(array, 0, UINT16_SIZE)
    array_length = btoi(size_b)
    return size_b + static_array_replace_byte_length_head(
        array_head_and_tail=extract(array, UINT16_SIZE, 0),
        new_item=new_item,
        index=index,
        array_length=array_length,
    )


@subroutine
def dynamic_array_replace_dynamic_element(source: Bytes, new_item: Bytes, index: UInt64) -> Bytes:
    size_b = substring(source, 0, UINT16_SIZE)
    array_length = btoi(size_b)
    return size_b + static_array_replace_dynamic_element(
        array_head_and_tail=extract(source, UINT16_SIZE, 0),
        new_item=new_item,
        index=index,
        array_length=array_length,
    )


@subroutine
def static_array_replace_dynamic_element(
    *, array_head_and_tail: Bytes, new_item: Bytes, index: UInt64, array_length: UInt64
) -> Bytes:
    original_offset = extract_uint16(array_head_and_tail, index * 2)
    next_item_offset = extract_uint16(array_head_and_tail, (index + 1) * 2)
    end_of_tail = array_head_and_tail.length
    is_before_end = array_length - index - 1
    end_offset = select_uint64(end_of_tail, next_item_offset, is_before_end)

    original_item_length = end_offset - original_offset
    new_item_length = new_item.length
    new_head_and_tail = (
        substring(array_head_and_tail, 0, original_offset)
        + new_item
        + substring(array_head_and_tail, end_offset, end_of_tail)
    )
    for head_offset in urange((index + 1) * 2, array_length * 2, 2):
        tail_offset = extract_uint16(new_head_and_tail, head_offset)
        tail_offset += new_item_length
        tail_offset -= original_item_length
        tail_offset_bytes = extract(itob(tail_offset), UINT16_OFFSET, UINT16_SIZE)
        new_head_and_tail = replace(new_head_and_tail, head_offset, tail_offset_bytes)
    return new_head_and_tail


@subroutine
def static_array_replace_byte_length_head(
    array_head_and_tail: Bytes, new_item: Bytes, index: UInt64, array_length: UInt64
) -> Bytes:
    """
    Replace a single item in an arc4 dynamic array of items that are prefixed with
    their byte length

    array_head_and_tail: The head and tail bytes of the source array
    new_item: The bytes of the new item to be inserted
    index: The index to insert the new item at
    array_length: The length of the array

    returns: The updated bytes for the source array
    """
    assert index < array_length, "Index out of bounds"
    offset_for_index = extract_uint16(array_head_and_tail, index * UINT16_SIZE)
    old_item_length = extract_uint16(array_head_and_tail, offset_for_index)
    old_item_end = offset_for_index + old_item_length + UINT16_SIZE
    return recalculate_head_for_elements_with_byte_length_head(
        array_head_and_tail=substring(array_head_and_tail, 0, offset_for_index)
        + new_item
        + substring(array_head_and_tail, old_item_end, array_head_and_tail.length),
        length=array_length,
        start_at_index=index,
    )


@subroutine
def recalculate_head_for_elements_with_byte_length_head(
    array_head_and_tail: Bytes, length: UInt64, start_at_index: UInt64
) -> Bytes:
    """
    Recalculates the offset values of an arc4 static array, where each item's head consists of
    its length in bytes as uint16

    array_data: The static array data
    length: The length of the static array
    start_at_index: Optionally start at a non-zero index for performance optimisation. The offset
                    at this index is assumed to be correct if start_at_index is not 0

    returns: The updated bytes for the source array
    """
    tail_offset = select_uint64(
        length * UINT16_SIZE,
        extract_uint16(array_head_and_tail, start_at_index * UINT16_SIZE),
        start_at_index,  # use length * UINT16_SIZE if 0 otherwise inspect head
    )

    for head_offset in urange(start_at_index * UINT16_SIZE, length * UINT16_SIZE, UINT16_SIZE):
        tail_offset_bytes = extract(itob(tail_offset), UINT16_OFFSET, UINT16_SIZE)
        array_head_and_tail = replace(array_head_and_tail, head_offset, tail_offset_bytes)
        tail_offset += extract_uint16(array_head_and_tail, tail_offset) + UINT16_SIZE
        head_offset += UINT16_SIZE
    return array_head_and_tail
