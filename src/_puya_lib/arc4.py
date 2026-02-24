from algopy import (
    Bytes,
    UInt64,
    subroutine,
    urange,
)
from algopy._hints import __pure
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


@__pure
@subroutine(inline=True)
def _itob16(i: UInt64) -> Bytes:
    return extract(itob(i), UINT16_OFFSET, 0)


@__pure
@subroutine
def dynamic_array_pop_bit(array: Bytes) -> Bytes:
    """
    Pop the last item from an arc4 dynamic array of arc4 encoded boolean items

    array: The bytes for the source array

    returns: The updated bytes for the source array
    """
    array_length = extract_uint16(array, 0)
    length_minus_1 = array_length - 1
    result = replace(array, 0, _itob16(length_minus_1))
    popped_location = length_minus_1 + UINT16_SIZE * 8
    result = setbit_bytes(result, popped_location, False)  # noqa: FBT003
    result = substring(result, 0, UINT16_SIZE + ((length_minus_1 + 7) // 8))
    return result


@__pure
@subroutine(inline=True)
def r_trim(b: Bytes, n: UInt64) -> Bytes:
    """Remove the last n bytes from b"""
    return substring(b, 0, b.length - n)


@__pure
@subroutine
def dynamic_array_pop_fixed_size(array: Bytes, fixed_byte_size: UInt64) -> Bytes:
    """
    Pop the last item from an arc4 dynamic array of fixed sized items

    array: The bytes for the source array

    returns: The updated bytes for the source array
    """
    result = r_trim(array, fixed_byte_size)
    array_length = extract_uint16(result, 0)
    length_minus_1 = array_length - 1
    return replace(result, 0, _itob16(length_minus_1))


@__pure
@subroutine
def dynamic_array_pop_byte_length_head(array: Bytes) -> Bytes:
    """
    Pop the last item from an arc4 dynamic array of items that are prefixed with their length in
    bytes, e.g. arc4.String, arc4.DynamicBytes

    source: The bytes for the source array

    returns: The updated bytes for the source array
    """
    array_length = extract_uint16(array, 0)
    length_minus_1 = array_length - 1
    updated = _itob16(length_minus_1)
    head_and_tail = extract(array, UINT16_SIZE, 0)
    popped_header_offset = length_minus_1 * UINT16_SIZE

    popped_offset = extract_uint16(head_and_tail, popped_header_offset)
    new_head_and_tail = substring(head_and_tail, 0, popped_header_offset)
    new_head_and_tail += substring(head_and_tail, popped_header_offset + 2, popped_offset)

    updated += _recalculate_head_for_elements_with_byte_length_head(
        array_head_and_tail=new_head_and_tail, length=length_minus_1, start_at_index=UInt64(0)
    )
    return updated


@__pure
@subroutine
def dynamic_array_pop_dynamic_element(array: Bytes) -> Bytes:
    """
    Pop the last item from an arc4 dynamic array of dynamically sized items

    array: The bytes for the source array

    returns: The updated bytes for the source array
    """
    array_length = extract_uint16(array, 0)
    length_minus_1 = array_length - 1

    updated = _itob16(length_minus_1)
    popped_header_offset = length_minus_1 * UINT16_SIZE
    head_offset = UInt64(UINT16_SIZE)
    while head_offset <= popped_header_offset:
        item_offset = extract_uint16(array, head_offset)
        item_offset -= UINT16_SIZE
        updated += _itob16(item_offset)
        head_offset += UINT16_SIZE

    head_and_tail = extract(array, UINT16_SIZE, 0)
    updated += substring(
        head_and_tail,
        head_offset,
        extract_uint16(head_and_tail, popped_header_offset),
    )

    return updated


@__pure
@subroutine
def dynamic_array_read_dynamic_element(*, array: Bytes, index: UInt64) -> Bytes:
    return static_array_read_dynamic_element(
        array_head_and_tail=extract(array, UINT16_SIZE, 0),
        index=index,
        array_length=extract_uint16(array, 0),
    )


@__pure
@subroutine
def static_array_read_dynamic_element(
    *, array_head_and_tail: Bytes, index: UInt64, array_length: UInt64
) -> Bytes:
    item_start_offset = extract_uint16(array_head_and_tail, index * 2)
    end_of_tail = array_head_and_tail.length
    next_index = index + 1
    next_item_offset = extract_uint16(array_head_and_tail, next_index * 2)
    is_before_end = array_length - next_index  # this will error if index is beyond the length
    item_end_offset = select_uint64(end_of_tail, next_item_offset, is_before_end)
    return substring(array_head_and_tail, item_start_offset, item_end_offset)


@__pure
@subroutine
def dynamic_array_read_byte_length_element(*, array: Bytes, index: UInt64) -> Bytes:
    array_head_and_tail = extract(array, UINT16_SIZE, 0)
    item_start_offset = extract_uint16(array_head_and_tail, index * 2)
    item_length = extract_uint16(array_head_and_tail, item_start_offset)
    return extract(array_head_and_tail, item_start_offset, item_length + 2)


@__pure
@subroutine
def static_array_read_byte_length_element(*, array: Bytes, index: UInt64) -> Bytes:
    item_start_offset = extract_uint16(array, index * 2)
    item_length = extract_uint16(array, item_start_offset)
    return extract(array, item_start_offset, item_length + 2)


@__pure
@subroutine(inline=True)  # inline=True matches historical behaviour of puya
def dynamic_array_concat_fixed(
    *,
    array: Bytes,
    new_items_bytes: Bytes,
    new_items_count: UInt64,
) -> Bytes:
    """
    Concat data to an arc4 dynamic array of fixed size elements

    array: The bytes for the source array
    new_items_count: The count of new items being added (N)
    new_items_bytes: The concatenated bytes of N array elements
    returns: The updated bytes for the source array
    """
    array_length = extract_uint16(array, 0)
    new_array_length = array_length + new_items_count
    new_len_u16 = _itob16(new_array_length)
    result = replace(array, 0, new_len_u16)
    return result + new_items_bytes


@__pure
@subroutine
def dynamic_array_concat_bits(
    *, array: Bytes, new_items_bytes: Bytes, new_items_count: UInt64, read_step: UInt64
) -> Bytes:
    """
    Concat data to an arc4 dynamic array of arc4 encoded boolean values

    array: The bytes for the source array
    new_items_bytes: Either the data portion of an arc4 packed array of booleans
                        or
                     a sparse array of concatenated arc4 booleans
    new_items_count: The count of new items being added
    read_step: How many bits to advance when reading new items,
               1 for packed bools or 8 for concatenated bools

    returns: The updated bytes for the source array
    """
    array_length = extract_uint16(array, 0)
    new_array_length = array_length + new_items_count
    new_array_length_b = _itob16(new_array_length)
    result = replace(array, 0, new_array_length_b)
    current_bytes = (array_length + 7) // 8
    required_bytes = (new_array_length + 7) // 8
    if current_bytes < required_bytes:
        result += bzero(required_bytes - current_bytes)

    read_offset = UInt64(0)
    write_offset = array_length + 8 * UINT16_SIZE
    write_end = write_offset + new_items_count
    while write_offset < write_end:
        result = setbit_bytes(result, write_offset, getbit(new_items_bytes, read_offset))
        write_offset += 1
        read_offset += read_step

    return result


@__pure
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
    ) + _recalculate_head_for_elements_with_byte_length_head(
        array_head_and_tail=(
            substring(array, 2, header_end)
            + bzero(new_items_count * UINT16_SIZE)
            + substring(array, header_end, array.length)
            + new_items_bytes
        ),
        length=new_length,
        start_at_index=UInt64(0),
    )


@__pure
@subroutine
def dynamic_array_concat_dynamic_element(
    *,
    array: Bytes,
    new_head_and_tail: Bytes,
    new_items_count: UInt64,
) -> Bytes:
    array_items_count = extract_uint16(array, 0)
    array_head_and_tail = extract(array, UINT16_SIZE, 0)
    new_head = Bytes()
    item_offset_adjustment = new_items_count * UINT16_SIZE
    for head_offset in urange(0, array_items_count * UINT16_SIZE, UINT16_SIZE):
        item_offset = extract_uint16(array_head_and_tail, head_offset)
        new_head += _itob16(item_offset_adjustment + item_offset)

    head_and_tail_length = array_head_and_tail.length
    for head_offset in urange(0, new_items_count * UINT16_SIZE, UINT16_SIZE):
        item_offset = extract_uint16(new_head_and_tail, head_offset)
        new_head += _itob16(head_and_tail_length + item_offset)
    return (
        _itob16(array_items_count + new_items_count)
        + new_head
        + substring(array_head_and_tail, array_items_count * UINT16_SIZE, head_and_tail_length)
        + substring(new_head_and_tail, new_items_count * UINT16_SIZE, new_head_and_tail.length)
    )


@__pure
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


@__pure
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


@__pure
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
        tail_offset_bytes = _itob16(tail_offset)
        new_head_and_tail = replace(new_head_and_tail, head_offset, tail_offset_bytes)
    return new_head_and_tail


@__pure
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
    offset_for_index = extract_uint16(array_head_and_tail, index * UINT16_SIZE)
    old_item_length = extract_uint16(array_head_and_tail, offset_for_index)
    old_item_end = offset_for_index + old_item_length + UINT16_SIZE
    return _recalculate_head_for_elements_with_byte_length_head(
        array_head_and_tail=substring(array_head_and_tail, 0, offset_for_index)
        + new_item
        + substring(array_head_and_tail, old_item_end, array_head_and_tail.length),
        length=array_length,
        start_at_index=index,
    )


@__pure
@subroutine
def _recalculate_head_for_elements_with_byte_length_head(
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
        tail_offset_bytes = _itob16(tail_offset)
        array_head_and_tail = replace(array_head_and_tail, head_offset, tail_offset_bytes)
        tail_offset += extract_uint16(array_head_and_tail, tail_offset) + UINT16_SIZE
        head_offset += UINT16_SIZE
    return array_head_and_tail


@__pure
@subroutine
def dynamic_assert_index(array: Bytes, index: UInt64) -> None:
    length = extract_uint16(array, 0)
    assert index < length, "index out of bounds"
