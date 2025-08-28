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
    # all optimizations involve a box read, so exit if none were found
    if not aggregates.box_reads:
        return False
    # also exit early if none of the nodes we visit were found
    if not (aggregates.has_box_write or aggregates.extract_values or aggregates.has_array_length):
        return False
    replacer = _AddDirectBoxOpsVisitor(
        temp_prefix="box",
        aggregates=aggregates,
        subroutine=subroutine,
        embedded_funcs=context.embedded_funcs,
    )
    for block in subroutine.body:
        replacer.visit_block(block)
    return replacer.modified


@attrs.define(kw_only=True)
class _AggregateCollector(NoOpIRVisitor[None]):
    replace_values: dict[models.Value, models.ReplaceValue] = attrs.field(factory=dict)
    extract_values: dict[models.Value, models.ExtractValue] = attrs.field(factory=dict)
    box_reads: dict[models.Value, models.BoxRead] = attrs.field(factory=dict)
    _target: models.Register | None = None
    has_array_length: bool = False
    has_box_write: bool = False

    @typing.override
    def visit_assignment(self, ass: models.Assignment) -> None:
        try:
            (self._target,) = ass.targets
        except ValueError:
            return
        ass.source.accept(self)
        self._target = None

    @typing.override
    def visit_array_length(self, read: models.ArrayLength) -> None:
        self.has_array_length = True

    @typing.override
    def visit_box_write(self, write: models.BoxWrite) -> None:
        self.has_box_write = True

    @typing.override
    def visit_replace_value(self, write: models.ReplaceValue) -> None:
        if self._target:
            self.replace_values[self._target] = write

    @typing.override
    def visit_extract_value(self, read: models.ExtractValue) -> None:
        if self._target:
            self.extract_values[self._target] = read

    @typing.override
    def visit_box_read(self, read: models.BoxRead) -> None:
        if self._target:
            self.box_reads[self._target] = read


@attrs.define
class _AddDirectBoxOpsVisitor(MutatingRegisterContext):
    aggregates: _AggregateCollector
    modified: bool = False

    def visit_array_length(self, length: models.ArrayLength) -> models.ValueProvider | None:
        if not length.array_encoding.length_header:
            return None

        # look through extract values to find underlying box read
        base = length.base
        maybe_extract_value = None
        try:
            maybe_extract_value = self.aggregates.extract_values[base]
        except KeyError:
            maybe_box_register = base
            extract_location = None
        else:
            maybe_box_register = maybe_extract_value.base
            extract_location = maybe_extract_value.source_location

        try:
            box_read = self.aggregates.box_reads[maybe_box_register]
        except KeyError:
            return None

        loc = sequential_source_locations_merge(
            (length.source_location, extract_location, box_read.source_location)
        )

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

    def visit_extract_value(self, read: models.ExtractValue) -> models.ValueProvider | None:
        # find box read
        try:
            box_read = self.aggregates.box_reads[read.base]
        except KeyError:
            return None

        aggregate_encoding = read.base_type.encoding
        # can only read fixed size elements
        if read.ir_type.num_bytes is None:
            return None
        # box_extract is only required if the aggregate doesn't fit on the stack or aggregate
        # is dynamic
        if (
            aggregate_encoding.is_fixed
            and aggregate_encoding.checked_num_bytes <= MAX_BYTES_LENGTH
        ):
            return None
        # TODO: there are more scenarios where it can be more efficient e.g.
        #       a box_extract with constant offsets can be more efficient if it also eliminates
        #       the exists assertion, however this requires knowledge of other consumers of the
        #       box read

        merged_loc = sequential_source_locations_merge(
            (read.source_location, box_read.source_location)
        )
        new_read = _combine_box_and_aggregate_read(self, box_read.key, read, merged_loc)
        assert new_read.types == read.types, "expected replacement types to match"
        self.modified = True
        logger.debug(
            f"combined BoxRead `{read.base !s} = {box_read!s}`\n"
            f"and ExtractValue `{read!s}`\n"
            f"into {new_read!s}",
            location=merged_loc,
        )
        return new_read

    def visit_box_write(self, write: models.BoxWrite) -> models.Op | None:
        # find aggregate
        try:
            agg_write = self.aggregates.replace_values[write.value]
        except KeyError:
            return None

        # only support fixed size writes
        encoding = agg_write.base_type.encoding
        indexes = list(reversed(agg_write.indexes))
        while indexes:
            index = indexes.pop()
            if isinstance(encoding, encodings.TupleEncoding) and isinstance(index, int):
                encoding = encoding.elements[index]
            elif isinstance(encoding, encodings.ArrayEncoding):
                encoding = encoding.element
            else:
                raise InternalError("invalid index sequence", agg_write.source_location)
        if encoding.is_dynamic:
            return None

        # find corresponding read
        try:
            read_src = self.aggregates.box_reads[agg_write.base]
        except KeyError:
            return None

        # can only do an in-place update if the agg write was for a value from the same box
        if write.key != read_src.key:
            return None

        self.modified = True
        merged_loc = sequential_source_locations_merge(
            (write.source_location, agg_write.source_location, read_src.source_location)
        )
        new_write = _combine_aggregate_and_box_write(self, agg_write, write.key, merged_loc)
        logger.debug(
            f"combined BoxRead `{agg_write.base!s} = {read_src!s}`\n"
            f"and ReplaceValue `{write.value!s} = {agg_write!s}`\n"
            f"and BoxWrite `{write!s}`\n"
            f"into {new_write!s}",
            location=merged_loc,
        )
        return new_write


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
    agg_write: models.ReplaceValue,
    box_key: models.Value,
    loc: SourceLocation | None,
) -> models.Op:
    factory = OpFactory(context, loc)
    # TODO: determine for writes if calculating the offset and asserting indexes
    #       is more efficient than doing N reads & writes
    fixed_offset = _get_fixed_byte_offset(
        factory,
        box_key=box_key,
        encoding=agg_write.base_type.encoding,
        indexes=agg_write.indexes,
        stop_at_valid_stack_value=False,
    )
    if not fixed_offset.remaining_indexes:
        value = agg_write.value
    else:
        # currently only occurs when agg_write.encoding.is_bit
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
                value=agg_write.value,
                indexes=fixed_offset.remaining_indexes,
                source_location=loc,
            )
        )
    return factory.box_replace(box_key, fixed_offset.offset, value)


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
            if encoding.length_header:
                size: models.Value | int = factory.box_extract_u16(box_key, box_offset)
            else:
                assert encoding.size is not None, "expected fixed size array"
                size = encoding.size
            index_ok = factory.lt(index, size, "index_ok")
            factory.assert_value(index_ok, error_message="index out of bounds")
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
