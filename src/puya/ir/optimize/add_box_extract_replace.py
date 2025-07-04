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
from puya.ir.types_ import EncodedType
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
    agg_writes: dict[models.Value, models.ReplaceValue] = attrs.field(factory=dict)
    box_reads: dict[models.Value, models.BoxRead] = attrs.field(factory=dict)

    @typing.override
    def visit_assignment(self, ass: models.Assignment) -> None:
        source = ass.source
        match source:
            case models.ReplaceValue():
                (target,) = ass.targets
                self.agg_writes[target] = source
            case models.BoxRead():
                (value,) = ass.targets
                self.box_reads[value] = source


@attrs.define
class _AddDirectBoxOpsVisitor(MutatingRegisterContext):
    aggregates: _AggregateCollector

    def visit_extract_value(self, read: models.ExtractValue) -> models.ValueProvider:
        if not _box_extract_required(read):
            return read

        maybe_box_register = read.base
        try:
            box_read = self.aggregates.box_reads[maybe_box_register]
        except KeyError:
            return read

        merged_loc = sequential_source_locations_merge(
            (box_read.source_location, read.source_location)
        )
        new_read = _combine_box_and_aggregate_read(
            self,
            box_read.key,
            read,
            merged_loc,
        )
        if new_read is None:
            return read
        else:
            assert new_read.types == read.types, "expected replacement types to match"
            self.modified = True
            logger.debug(
                f"combined BoxRead `{maybe_box_register!s} = {box_read!s}`\n"
                f"and ExtractValue `{read!s}`\n"
                f"into {new_read!s}",
                location=merged_loc,
            )
            return new_read

    def visit_box_write(self, write: models.BoxWrite) -> models.BoxWrite | None:
        # find aggregate
        try:
            agg_write = self.aggregates.agg_writes[write.value]
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
        new_write = _combine_aggregate_and_box_write(
            self,
            agg_write,
            write.key,
            merged_loc,
        )
        self.add_op(new_write)
        logger.debug(
            f"combined BoxRead `{agg_write.base!s} = {read_src!s}`\n"
            f"and ReplaceValue `{write.value!s} = {agg_write!s}`\n"
            f"and BoxWrite `{write!s}`\n"
            f"into {new_write!s}",
            location=merged_loc,
        )
        return None


def _box_extract_required(read: models.ExtractValue) -> bool:
    aggregate_encoding = read.base_type.encoding
    # dynamic encodings not supported with box_extract optimization currently
    if aggregate_encoding.is_dynamic:
        return False
    # box_extract is required if the aggregate doesn't fit on the stack
    return aggregate_encoding.checked_num_bytes > MAX_BYTES_LENGTH
    # TODO: there are more scenarios where it can be more efficient e.g.
    #       a box_extract with constant offsets can be more efficient if it also eliminates
    #       the exists assertion, however this requires knowledge of other consumers of the
    #       box read


def _combine_box_and_aggregate_read(
    context: IRRegisterContext,
    box_key: models.Value,
    agg_read: models.ExtractValue,
    loc: SourceLocation | None,
) -> models.ValueProvider:
    # TODO: it is also feasible and practical to support a DynamicArray of fixed elements at the
    #       root level, as this just requires a box_extract for the length
    factory = OpFactory(context, loc)
    fixed_offset = _get_fixed_byte_offset(
        context,
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

    encoding_at_offset = fixed_offset.encoding
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
    return factory.box_replace(
        box_key,
        fixed_offset.offset,
        value,
    )


@attrs.frozen
class _FixedOffset:
    offset: models.Value
    encoding: Encoding
    remaining_indexes: Sequence[int | models.Value]


def _get_fixed_byte_offset(
    context: IRRegisterContext,
    *,
    encoding: Encoding,
    indexes: Sequence[int | models.Value],
    loc: SourceLocation | None,
    stop_at_valid_stack_value: bool,
) -> _FixedOffset:
    factory = OpFactory(context, loc)
    check_array_bounds = False
    box_offset = factory.constant(0)
    next_index = 0
    for index in indexes:
        if isinstance(encoding, TupleEncoding) and isinstance(index, int):
            bit_offset = encoding.get_head_bit_offset(index)
            has_trailing_data = (index + 1) != len(encoding.elements)
            encoding = encoding.elements[index]

            # stop if element is a bit, as that can't be extracted directly
            if encoding.is_bit:
                return _get_fixed_byte_offset_from_bit_offset(factory, box_offset, bit_offset)
            element_offset: int | models.Value = bits_to_bytes(bit_offset)

            # if we aren't reading the last item of a tuple
            # then any following array read will need a bounds check
            check_array_bounds = check_array_bounds or has_trailing_data
        elif isinstance(encoding, ArrayEncoding):
            assert encoding.size is not None
            if check_array_bounds:
                index_ok = factory.lt(index, encoding.size, "index_ok")
                assert_value(
                    context, index_ok, error_message="index out of bounds", source_location=loc
                )
            encoding = encoding.element

            # stop if element is a bit, as that can't be extracted directly
            if encoding.is_bit:
                return _get_fixed_byte_offset_from_bit_offset(factory, box_offset, index)

            element_offset = factory.mul(index, encoding.checked_num_bytes, "element_offset")

            # always need to check array bounds after the first array read
            check_array_bounds = True
        else:
            raise InternalError("invalid aggregate encoding and index", loc)
        box_offset = factory.add(box_offset, element_offset, "offset")
        next_index += 1
        # exit loop if the resulting value can fit on stack
        # generally more optimizations are possible the sooner a value is read
        if encoding.checked_num_bytes < MAX_BYTES_LENGTH and stop_at_valid_stack_value:
            break
        # bits can't be read or written directly and should have been handled already
        assert not encoding.is_bit, "can't read bits directly"

    if encoding.checked_num_bytes > MAX_BYTES_LENGTH:
        logger.warning(f"value exceeds {MAX_BYTES_LENGTH} bytes", location=loc)

    return _FixedOffset(
        offset=box_offset, encoding=encoding, remaining_indexes=indexes[next_index:]
    )


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
