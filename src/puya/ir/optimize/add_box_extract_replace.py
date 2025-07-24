import typing
from collections.abc import Sequence

import attrs

from puya import log
from puya.algo_constants import MAX_BYTES_LENGTH
from puya.errors import InternalError
from puya.ir import models
from puya.ir.encodings import ArrayEncoding, BoolEncoding, Encoding, TupleEncoding
from puya.ir.mutating_register_context import MutatingRegisterContext
from puya.ir.op_utils import OpFactory, assert_value
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
    replace_values: dict[models.Value, models.ReplaceValue] = attrs.field(factory=dict)
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
                self,
                box_key=box_read.key,
                encoding=maybe_extract_value.base_type.encoding,
                indexes=maybe_extract_value.indexes,
                loc=maybe_extract_value.source_location,
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
            f"combined BoxRead `{read.base !s} = {box_read!s}`\n"
            f"and ExtractValue `{read!s}`\n"
            f"into {new_read!s}",
            location=merged_loc,
        )
        return new_read

    def visit_box_write(self, write: models.BoxWrite) -> models.BoxWrite | None:
        # find aggregate
        try:
            agg_write = self.aggregates.replace_values[write.value]
        except KeyError:
            return write

        # only support fixed size boxes
        if agg_write.base_type.encoding.is_dynamic:
            return write

        # find corresponding read
        try:
            read_src = self.aggregates.box_reads[agg_write.base]
        except KeyError:
            return write

        # can only do an in-place update if the agg write was for a value from the same box
        if write.key != read_src.key:
            return write

        self.modified = True
        merged_loc = sequential_source_locations_merge(
            (agg_write.source_location, write.source_location)
        )
        new_write = _combine_aggregate_and_box_write(self, agg_write, write.key, merged_loc)
        self.add_op(new_write)
        logger.debug(
            f"combined BoxRead `{agg_write.base!s} = {read_src!s}`\n"
            f"and ReplaceValue `{write.value!s} = {agg_write!s}`\n"
            f"and BoxWrite `{write!s}`\n"
            f"into {new_write!s}",
            location=merged_loc,
        )
        return None


def _combine_box_and_aggregate_read(
    context: IRRegisterContext,
    box_key: models.Value,
    agg_read: models.ExtractValue,
    loc: SourceLocation | None,
) -> models.ValueProvider:
    factory = OpFactory(context, loc)
    fixed_offset = _get_fixed_byte_offset(
        context,
        box_key=box_key,
        encoding=agg_read.base_type.encoding,
        indexes=agg_read.indexes,
        loc=loc,
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
        context,
        box_key=box_key,
        encoding=agg_write.base_type.encoding,
        indexes=agg_write.indexes,
        loc=loc,
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
    context: IRRegisterContext,
    *,
    box_key: models.Value,
    encoding: Encoding,
    indexes: Sequence[int | models.Value],
    loc: SourceLocation | None,
    stop_at_valid_stack_value: bool,
) -> _FixedOffset:
    factory = OpFactory(context, loc)
    check_array_bounds = False
    box_offset = factory.constant(0)
    indexes = list(indexes)
    while indexes:
        index = indexes.pop(0)
        if isinstance(encoding, TupleEncoding) and isinstance(index, int):
            bit_offset = encoding.get_head_bit_offset(index)
            dynamic_indexes = [
                idx for idx, element in enumerate(encoding.elements) if element.is_dynamic
            ]
            if encoding.is_dynamic:
                # dynamic encodings have a tail portion
                # an element would only have no trailing data if it was the last part of the tail
                # and was made up o fixed size elements,
                # therefore, if index_element is the last dynamic element and is a dynamic array
                # with a fixed sized element, then it has no trailing data
                index_element = encoding.elements[index]
                has_trailing_data = not (
                    isinstance(index_element, ArrayEncoding)
                    and index_element.is_dynamic
                    and index_element.element.is_fixed
                    and index == dynamic_indexes[-1]
                )
            else:
                # for fixed encodings only the last element has no trailing data
                has_trailing_data = (index + 1) != len(encoding.elements)
            tail_bit_offset = encoding.get_head_bit_offset(None)
            encoding = encoding.elements[index]
            # stop if element is a bit, as that can't be extracted directly
            if encoding.is_bit:
                return _get_fixed_byte_offset_from_bit_offset(factory, box_offset, bit_offset)
            element_offset: int | models.Value = bits_to_bytes(bit_offset)
            if encoding.is_dynamic:
                # first dynamic index is always at the start of the tail:
                if index == dynamic_indexes[0]:
                    element_offset = tail_bit_offset // 8
                else:
                    element_offset_offset = factory.add(box_offset, element_offset)
                    element_offset = factory.box_extract_u16(box_key, element_offset_offset)

            # if we aren't reading the last item of a tuple
            # then any following array read will need a bounds check
            check_array_bounds = check_array_bounds or has_trailing_data
        elif isinstance(encoding, ArrayEncoding):
            if check_array_bounds:
                if encoding.length_header:
                    size: models.Value | int = factory.box_extract_u16(box_key, box_offset)
                else:
                    assert encoding.size is not None, "expected fixed size array"
                    size = encoding.size
                index_ok = factory.lt(index, size, "index_ok")
                assert_value(
                    context, index_ok, error_message="index out of bounds", source_location=loc
                )
            if encoding.length_header:
                header_offset = 2
            else:
                header_offset = 0

            encoding = encoding.element

            # stop if element is a bit, as that can't be extracted directly
            if encoding.is_bit:
                index_offset = factory.add(index, header_offset * 8)
                return _get_fixed_byte_offset_from_bit_offset(factory, box_offset, index_offset)

            if encoding.is_fixed:
                index_bytes_offset = factory.mul(
                    index, encoding.checked_num_bytes, "index_bytes_offset"
                )
                element_offset = factory.add(index_bytes_offset, header_offset, "element_offset")
            else:
                index_offset = factory.mul(2, index)
                # the offset into head from the start of this element that contains the data offset
                element_offset_offset = factory.add(header_offset, index_offset)
                box_absolute_offset_offset = factory.add(box_offset, element_offset_offset)
                element_offset = factory.box_extract_u16(box_key, box_absolute_offset_offset)

            # always need to check array bounds after the first array read
            check_array_bounds = True
        else:
            raise InternalError("invalid aggregate encoding and index", loc)
        box_offset = factory.add(box_offset, element_offset, "offset")
        # exit loop if the resulting value can fit on stack
        # generally more optimizations are possible the sooner a value is read
        if (
            stop_at_valid_stack_value
            and encoding.is_fixed
            and encoding.checked_num_bytes < MAX_BYTES_LENGTH
        ):
            break
        # bits can't be read or written directly and should have been handled already
        assert not encoding.is_bit, "can't read bits directly"

    return _FixedOffset(offset=box_offset, encoding=encoding, remaining_indexes=indexes)


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
