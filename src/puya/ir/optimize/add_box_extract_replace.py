import typing
from collections.abc import Sequence

import attrs

from puya import log
from puya.algo_constants import MAX_BYTES_LENGTH
from puya.errors import InternalError
from puya.ir import encodings, models
from puya.ir.encodings import ArrayEncoding, BoolEncoding, Encoding, TupleEncoding
from puya.ir.mutating_register_context import MutatingRegisterContext
from puya.ir.op_utils import OpFactory
from puya.ir.optimize.context import IROptimizationContext
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import EncodedType, PrimitiveIRType
from puya.ir.visitor import NoOpIRVisitor
from puya.parse import SourceLocation, sequential_source_locations_merge
from puya.utils import bits_to_bytes

logger = log.get_logger(__name__)


def replace_aggregate_box_ops(
    context: IROptimizationContext, subroutine: models.Subroutine
) -> bool:
    aggregates = _AggregateCollector()
    for block in subroutine.body:
        for op in block.all_ops:
            op.accept(aggregates)
    replacer = _AddDirectBoxOpsVisitor(
        temp_prefix="box",
        aggregates=aggregates,
        subroutine=subroutine,
        embedded_funcs=context.embedded_funcs,
    )
    replacer.process_and_validate()
    return replacer.modified


@attrs.define(kw_only=True)
class _AggregateCollector(NoOpIRVisitor[None]):
    replace_values: dict[models.Value, models.ReplaceValue | models.ArrayPop] = attrs.field(
        factory=dict
    )
    extract_values: dict[models.Value, models.ExtractValue] = attrs.field(factory=dict)
    box_reads: dict[models.Value, models.BoxRead] = attrs.field(factory=dict)

    @typing.override
    def visit_assignment(self, ass: models.Assignment) -> None:
        source = ass.source
        match source:
            case models.ReplaceValue():
                (target,) = ass.targets
                self.replace_values[target] = source
            case models.ExtractValue():
                (target,) = ass.targets
                self.extract_values[target] = source
            case models.BoxRead():
                (value,) = ass.targets
                self.box_reads[value] = source
            case models.ArrayPop(
                base_type=EncodedType(encoding=ArrayEncoding(length_header=True))
            ):
                (target,) = ass.targets
                self.replace_values[target] = source


@attrs.define
class _AddDirectBoxOpsVisitor(MutatingRegisterContext):
    aggregates: _AggregateCollector
    modified: bool = False

    def visit_array_length(self, length: models.ArrayLength) -> models.ValueProvider:
        if not length.array_encoding.length_header:
            return length

        loc = length.source_location
        base = length.base

        # look through extract values to find underlying box read
        maybe_extract_value = None
        try:
            maybe_extract_value = self.aggregates.extract_values[base]
        except KeyError:
            maybe_box_register = base
        else:
            maybe_box_register = maybe_extract_value.base
        loc = sequential_source_locations_merge((maybe_box_register.source_location, loc))

        try:
            box_read = self.aggregates.box_reads[maybe_box_register]
        except KeyError:
            return length

        loc = sequential_source_locations_merge((box_read.source_location, loc))

        factory = OpFactory(self, loc)
        if not maybe_extract_value:
            offset: models.Value | int = 0
        else:
            fixed_offset = _get_fixed_byte_offset(
                factory,
                box_key=box_read.key,
                encoding=maybe_extract_value.base_type.encoding,
                indexes=maybe_extract_value.indexes,
                stop_at_valid_stack_value=False,
            )
            offset = fixed_offset.offset
        length_bytes = factory.box_extract(box_read.key, offset, 2, ir_type=PrimitiveIRType.bytes)
        return factory.btoi(length_bytes, temp_desc="array_length")

    def visit_extract_value(self, read: models.ExtractValue) -> models.ValueProvider:
        # find box read
        try:
            box_read = self.aggregates.box_reads[read.base]
        except KeyError:
            return read

        aggregate_encoding = read.base_type.encoding
        # can only read fixed size elements
        if read.ir_type.num_bytes is None:
            return read
        # box_extract is only required if the aggregate doesn't fit on the stack or aggregate
        # is dynamic
        if (
            aggregate_encoding.is_fixed
            and aggregate_encoding.checked_num_bytes <= MAX_BYTES_LENGTH
        ):
            return read
        # TODO: there are more scenarios where it can be more efficient e.g.
        #       a box_extract with constant offsets can be more efficient if it also eliminates
        #       the exists assertion, however this requires knowledge of other consumers of the
        #       box read

        merged_loc = sequential_source_locations_merge(
            (box_read.source_location, read.source_location)
        )
        new_read = _combine_box_and_aggregate_read(self, box_read.key, read, merged_loc)
        assert new_read.types == read.types, "expected replacement types to match"
        self.modified = True
        logger.debug(
            f"combined `{read.base !s} = {box_read!s}; {read!s}` into `{new_read!s}`",
            location=merged_loc,
        )
        return new_read

    def visit_box_write(self, write: models.BoxWrite) -> models.BoxWrite | None:
        try:
            replace_value_or_pop = self.aggregates.replace_values[write.value]
        except KeyError:
            return write

        # find corresponding read
        try:
            read_src = self.aggregates.box_reads[replace_value_or_pop.base]
        except KeyError:
            return write

        # can only do an in-place update if the agg write was for a value from the same box
        if write.key != read_src.key:
            return write

        # dynamic array
        if isinstance(replace_value_or_pop, models.ArrayPop):
            self._handle_array_pop(write, replace_value_or_pop)
            self.modified = True
            logger.debug(
                f"combined `{replace_value_or_pop.base!s} = {read_src!s}"
                f"; {write.value!s} = {replace_value_or_pop!s}"
                f"; {write!s}`"
                " into `box_splice; box_replace; box_resize`",
                location=replace_value_or_pop.source_location,
            )
            return None

        assert isinstance(replace_value_or_pop, models.ReplaceValue)
        array_pop = self.aggregates.replace_values.get(replace_value_or_pop.value)

        # dynamic array in an aggregate
        if isinstance(array_pop, models.ArrayPop):
            num_box_replaces = self._handle_replace_value_and_array_pop(
                write, replace_value_or_pop, array_pop
            )
            if not num_box_replaces:
                return write
            self.modified = True
            logger.debug(
                f"combined `{replace_value_or_pop.base!s} = {read_src!s}"
                f"; {write.value!s} = {replace_value_or_pop!s}"
                f"; {replace_value_or_pop.value!s} = {array_pop!s}"
                f"; {write!s}`"
                f" into `box_splice; {num_box_replaces} x box_replace; box_resize`",
                location=array_pop.source_location,
            )
            return None

        # fixed size aggregate (tuple or array)
        if not self._handle_replace_value(write, replace_value_or_pop):
            return write
        self.modified = True
        new_write = self.current_block_ops[-1]
        logger.debug(
            f"combined `{replace_value_or_pop.base!s} = {read_src!s}"
            f"; {write.value!s} = {replace_value_or_pop!s}"
            f"; {write!s}`"
            f" into `{new_write!s}`",
            location=new_write.source_location,
        )
        return None

    def _handle_array_pop(self, write: models.BoxWrite, array_pop: models.ArrayPop) -> None:
        array_encoding = array_pop.base_type.encoding
        assert isinstance(array_encoding, encodings.ArrayEncoding), "expected ArrayEncoding"
        assert array_encoding.length_header, "expected length header"
        factory = OpFactory(self, array_pop.source_location)
        box_offset = factory.constant(0)
        _pop_index_from_array(factory, array_encoding, write.key, box_offset, array_pop.index)
        self.modified = True

    def _handle_replace_value_and_array_pop(
        self,
        write: models.BoxWrite,
        replace_value: models.ReplaceValue,
        array_pop: models.ArrayPop,
    ) -> int:
        # can only perform dynamic offset updates for statically determinable offsets
        dynamic_offsets = _get_dynamic_offsets_requiring_update(
            replace_value.base_type.encoding, replace_value.indexes
        )
        if dynamic_offsets is None:
            return 0
        array_encoding = array_pop.base_type.encoding
        assert isinstance(array_encoding, encodings.ArrayEncoding), "expected ArrayEncoding"
        assert array_encoding.length_header, "expected length header"
        box_key = write.key
        factory = OpFactory(self, array_pop.source_location)
        array_offset = _get_fixed_byte_offset(
            factory,
            box_key=box_key,
            encoding=replace_value.base_type.encoding,
            indexes=replace_value.indexes,
            stop_at_valid_stack_value=False,
        )
        assert array_offset.encoding == array_encoding, "encodings should match"
        _pop_index_from_array(
            factory, array_encoding, box_key, array_offset.offset, array_pop.index
        )
        element_size = array_encoding.element.checked_num_bytes
        for offset in dynamic_offsets:
            offset_value = factory.box_extract_u16(box_key, offset)
            new_offset_value = factory.sub(offset_value, element_size)
            new_offset_value_u16 = factory.as_u16_bytes(new_offset_value)
            factory.box_replace(box_key, offset, new_offset_value_u16)
        return len(dynamic_offsets) + 1

    def _handle_replace_value(
        self, write: models.BoxWrite, replace_value: models.ReplaceValue
    ) -> bool:
        # only support fixed size writes
        encoding = replace_value.base_type.encoding
        indexes = list(reversed(replace_value.indexes))
        while indexes:
            index = indexes.pop()
            if isinstance(encoding, encodings.TupleEncoding) and isinstance(index, int):
                encoding = encoding.elements[index]
            elif isinstance(encoding, encodings.ArrayEncoding):
                encoding = encoding.element
            else:
                raise InternalError("invalid index sequence", replace_value.source_location)
        if encoding.is_dynamic:
            return False

        merged_loc = sequential_source_locations_merge(
            (replace_value.source_location, write.source_location)
        )
        _combine_aggregate_and_box_write(self, replace_value, write.key, merged_loc)
        return True


def _get_dynamic_offsets_requiring_update(
    encoding: encodings.Encoding, indexes: Sequence[models.Value | int]
) -> list[int] | None:
    result = list[int]()
    indexes = list(reversed(indexes))
    box_offset = 0
    while indexes:
        index = indexes.pop()
        if isinstance(encoding, encodings.TupleEncoding) and isinstance(index, int):
            next_index = index + 1
            # track any other dynamic offsets after the indexed element
            result.extend(
                box_offset + bits_to_bytes(encoding.get_head_bit_offset(el_idx))
                for el_idx, el in enumerate(encoding.elements[next_index:], start=next_index)
                if el.is_dynamic
            )
            box_offset += bits_to_bytes(encoding.get_head_bit_offset(index))
            encoding = encoding.elements[index]
        else:
            # an array index means the offset is no longer statically determinable
            return None
    return result


def _pop_index_from_array(
    factory: OpFactory,
    encoding: ArrayEncoding,
    box_key: models.Value,
    box_offset: models.Value,
    index: models.Value | None,
) -> None:
    arr_len = factory.box_extract_u16(box_key, box_offset)
    new_arr_len = factory.sub(arr_len, 1)
    if index is None:
        # don't assert array length if index is not specified
        # as the new_arr_len op will fail if arr_len is 0
        index = new_arr_len
    else:
        _check_array_length(factory, encoding, box_key, box_offset, index)
    new_arr_len_u16 = factory.as_u16_bytes(new_arr_len)
    factory.box_replace(box_key, box_offset, new_arr_len_u16)
    box_offset = factory.add(box_offset, 2)
    # assumes index has already been asserted, and box_offset points to head portion of array
    element_size = encoding.element.checked_num_bytes
    index_offset = factory.mul(index, element_size)
    absolute_index_offset = factory.add(box_offset, index_offset)
    factory.box_splice(
        box_key=box_key, index=absolute_index_offset, length=element_size, value=b""
    )
    box_size, _ = factory.box_len(box_key)
    new_size = factory.sub(box_size, element_size)
    factory.box_resize(box_key, new_size)


def _combine_box_and_aggregate_read(
    context: IRRegisterContext,
    box_key: models.Value,
    agg_read: models.ExtractValue,
    loc: SourceLocation | None,
) -> models.ValueProvider:
    factory = OpFactory(context, loc)
    fixed_offset = _get_fixed_byte_offset(
        factory,
        box_key=box_key,
        encoding=agg_read.base_type.encoding,
        indexes=agg_read.indexes,
        stop_at_valid_stack_value=True,
    )
    encoding_at_offset = fixed_offset.encoding
    extract_ir_type = EncodedType(encoding_at_offset)
    box_extract = factory.box_extract(
        box_key,
        fixed_offset.offset,
        encoding_at_offset.checked_num_bytes,
        ir_type=extract_ir_type,
    )
    remaining_indexes = fixed_offset.remaining_indexes
    if not remaining_indexes:
        return box_extract

    assert isinstance(
        encoding_at_offset, TupleEncoding | ArrayEncoding
    ), "expected aggregate encoding"
    new_agg_read = attrs.evolve(
        agg_read,
        base=box_extract,
        base_type=extract_ir_type,
        indexes=remaining_indexes,
        source_location=loc,
    )
    return new_agg_read


def _combine_aggregate_and_box_write(
    context: IRRegisterContext,
    replace_value: models.ReplaceValue,
    box_key: models.Value,
    loc: SourceLocation | None,
) -> None:
    factory = OpFactory(context, loc)
    # TODO: determine for writes if calculating the offset and asserting indexes
    #       is more efficient than doing N reads & writes
    fixed_offset = _get_fixed_byte_offset(
        factory,
        box_key=box_key,
        encoding=replace_value.base_type.encoding,
        indexes=replace_value.indexes,
        stop_at_valid_stack_value=False,
    )
    if not fixed_offset.remaining_indexes:
        value = replace_value.value
    else:
        # currently only occurs when replace_value.encoding.is_bit
        encoding = fixed_offset.encoding
        extract_ir_type = EncodedType(encoding)
        box_extract = factory.box_extract(
            box_key,
            fixed_offset.offset,
            fixed_offset.encoding.checked_num_bytes,
            ir_type=extract_ir_type,
        )
        assert isinstance(encoding, TupleEncoding | ArrayEncoding), "expected aggregate encoding"
        value = factory.materialise_single(
            models.ReplaceValue(
                base=box_extract,
                base_type=extract_ir_type,
                value=replace_value.value,
                indexes=fixed_offset.remaining_indexes,
                source_location=loc,
            )
        )
    factory.box_replace(box_key, fixed_offset.offset, value)


@attrs.frozen
class _FixedOffset:
    offset: models.Value
    encoding: Encoding
    remaining_indexes: Sequence[int | models.Value]


def _get_fixed_byte_offset(
    factory: OpFactory,
    *,
    box_key: models.Value,
    encoding: Encoding,
    indexes: Sequence[int | models.Value],
    stop_at_valid_stack_value: bool,
) -> _FixedOffset:
    box_offset = factory.constant(0)
    return _get_nested_fixed_byte_offset(
        factory,
        box_offset=box_offset,
        box_key=box_key,
        encoding=encoding,
        indexes=indexes,
        stop_at_valid_stack_value=stop_at_valid_stack_value,
        check_array_bounds=False,
    )


def _get_nested_fixed_byte_offset(
    factory: OpFactory,
    *,
    box_offset: models.Value,
    box_key: models.Value,
    encoding: Encoding,
    indexes: Sequence[int | models.Value],
    stop_at_valid_stack_value: bool,
    check_array_bounds: bool,
) -> _FixedOffset:
    index, *remaining_indexes = indexes

    if isinstance(encoding, TupleEncoding) and isinstance(index, int):
        index_encoding = encoding.elements[index]
        # stop if element is a bit, as that can't be extracted directly
        if index_encoding.is_bit:
            index_bits_offset = encoding.get_head_bit_offset(index)
            return _get_fixed_byte_offset_from_bit_offset(factory, box_offset, index_bits_offset)
        element_offset = _get_tuple_element_byte_offset(
            factory, box_offset=box_offset, box_key=box_key, encoding=encoding, index=index
        )
        # if not already checking array bounds, only need to start if there is trailing data
        check_array_bounds = check_array_bounds or _has_trailing_data(encoding, index)
    elif isinstance(encoding, ArrayEncoding):
        index_encoding = encoding.element
        if check_array_bounds:
            _check_array_length(factory, encoding, box_key, box_offset, index)
        if encoding.length_header:
            box_offset = factory.add(box_offset, 2)
        # stop if element is a bit, as that can't be extracted directly
        if index_encoding.is_bit:
            return _get_fixed_byte_offset_from_bit_offset(factory, box_offset, index)
        element_offset = _get_array_element_byte_offset(
            factory, box_offset=box_offset, box_key=box_key, encoding=encoding, index=index
        )
        # always need to check array bounds after the first array read
        check_array_bounds = True
    else:
        raise InternalError("invalid aggregate encoding and index")

    offset = factory.add(box_offset, element_offset, "offset")
    if (not remaining_indexes) or (
        # exit loop if the resulting value can fit on stack
        # generally more optimizations are possible the sooner a value is read
        stop_at_valid_stack_value
        and index_encoding.is_fixed
        and index_encoding.checked_num_bytes <= MAX_BYTES_LENGTH
    ):
        return _FixedOffset(
            offset=offset, encoding=index_encoding, remaining_indexes=remaining_indexes
        )
    else:
        return _get_nested_fixed_byte_offset(
            factory,
            box_offset=offset,
            box_key=box_key,
            encoding=index_encoding,
            indexes=remaining_indexes,
            stop_at_valid_stack_value=stop_at_valid_stack_value,
            check_array_bounds=check_array_bounds,
        )


def _has_trailing_data(encoding: TupleEncoding, index: int) -> bool:
    # if we aren't reading the last item of a tuple
    # then any following array read will need a bounds check
    if encoding.is_fixed:
        # for fixed encodings only the last element has no trailing data
        return index < (len(encoding.elements) - 1)
    # dynamic encodings have a tail portion
    # an element would only have no trailing data if it was the last part of the tail
    # and was made up of fixed size elements,
    # therefore, if index_element is the last dynamic element and is a dynamic array
    # with a fixed sized element, then it has no trailing data
    index_encoding = encoding.elements[index]
    if not (isinstance(index_encoding, ArrayEncoding) and index_encoding.size is None):
        return True
    if index_encoding.element.is_dynamic:
        return True
    return any(element.is_dynamic for element in encoding.elements[index + 1 :])


def _get_tuple_element_byte_offset(
    factory: OpFactory,
    *,
    box_offset: models.Value,
    box_key: models.Value,
    encoding: TupleEncoding,
    index: int,
) -> int | models.Value:
    index_head_offset = bits_to_bytes(encoding.get_head_bit_offset(index))
    if encoding.elements[index].is_fixed:
        return index_head_offset
    elif all(element.is_fixed for element in encoding.elements[:index]):
        # first dynamic index is always at the start of the tail
        tail_bit_offset = encoding.get_head_bit_offset(None)
        return bits_to_bytes(tail_bit_offset)
    else:
        element_offset_offset = factory.add(box_offset, index_head_offset)
        return factory.box_extract_u16(box_key, element_offset_offset)


def _get_array_element_byte_offset(
    factory: OpFactory,
    *,
    box_offset: models.Value,
    box_key: models.Value,
    encoding: ArrayEncoding,
    index: int | models.Value,
) -> models.Value:
    fixed_element_size = encoding.element.num_bytes
    if fixed_element_size is not None:
        return factory.mul(index, fixed_element_size, "element_offset")
    else:
        index_offset = factory.mul(2, index)
        # the offset into head from the start of this element that contains the data offset
        box_absolute_offset_offset = factory.add(box_offset, index_offset)
        return factory.box_extract_u16(box_key, box_absolute_offset_offset)


def _get_fixed_byte_offset_from_bit_offset(
    factory: OpFactory, box_offset: models.Value, element_bit_offset: models.Value | int
) -> _FixedOffset:
    # to read a bit from a box some shenanigans are required
    # 1.) determine which byte the bit resides in
    # 2.) extract that byte
    # 3.) then use get_bit/set_bit to read from the byte

    element_byte_offset = factory.div_floor(element_bit_offset, 8, "element_byte_offset")
    byte_containing_bit_offset = factory.add(
        box_offset, element_byte_offset, "byte_containing_bit_offset"
    )
    bit_index = factory.mod(element_bit_offset, 8, "element_bit_offset")

    return _FixedOffset(
        # offset now points to the byte containing the desired bit
        offset=byte_containing_bit_offset,
        # pretend the byte is just a fixed array of bit packed bools
        encoding=ArrayEncoding.fixed(element=BoolEncoding(), size=8),
        # provide the calculated bit_index as the only remaining index
        remaining_indexes=[bit_index],
    )


def _check_array_length(
    factory: OpFactory,
    encoding: ArrayEncoding,
    box_key: models.Value,
    box_offset: models.Value,
    index: models.Value | int,
) -> None:
    if encoding.length_header:
        size: models.Value | int = factory.box_extract_u16(box_key, box_offset)
    else:
        assert encoding.size is not None, "expected fixed size array"
        size = encoding.size
    index_ok = factory.lt(index, size, "index_ok")
    factory.assert_value(index_ok, error_message="index out of bounds")
