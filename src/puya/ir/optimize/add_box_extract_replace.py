import typing
from collections.abc import Sequence

import attrs

from puya import log
from puya.algo_constants import MAX_BYTES_LENGTH
from puya.errors import InternalError
from puya.ir import encodings, models
from puya.ir._puya_lib import PuyaLibIR
from puya.ir.avm_ops import AVMOp
from puya.ir.encodings import ArrayEncoding, BoolEncoding, Encoding, TupleEncoding
from puya.ir.mutating_register_context import MutatingRegisterContext
from puya.ir.op_utils import OpFactory
from puya.ir.optimize.context import IROptimizationContext
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
    # also exit early if none of the nodes we modify were found
    if not (
        aggregates.has_box_write
        or aggregates.extract_values
        or aggregates.intrinsic_reads
        or aggregates.intrinsic_lens
        or aggregates.has_array_length
    ):
        return False
    replacer = _AddInplaceBoxReadWritesVisitor(
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
    aggregate_mutations: dict[
        models.Value, models.ReplaceValue | models.ArrayPop | models.ArrayConcat
    ] = attrs.field(factory=dict)
    extract_values: dict[models.Value, models.ExtractValue] = attrs.field(factory=dict)
    intrinsic_reads: dict[models.Value, models.Intrinsic] = attrs.field(factory=dict)
    intrinsic_lens: dict[models.Value, models.Intrinsic] = attrs.field(factory=dict)
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
            self.aggregate_mutations[self._target] = write

    @typing.override
    def visit_array_pop(self, pop: models.ArrayPop) -> None:
        if self._target:
            self.aggregate_mutations[self._target] = pop

    @typing.override
    def visit_array_concat(self, concat: models.ArrayConcat) -> None:
        if self._target:
            self.aggregate_mutations[self._target] = concat

    @typing.override
    def visit_extract_value(self, read: models.ExtractValue) -> None:
        if self._target:
            self.extract_values[self._target] = read

    @typing.override
    def visit_box_read(self, read: models.BoxRead) -> None:
        if self._target:
            self.box_reads[self._target] = read

    @typing.override
    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> None:
        if _is_box_read_intrinsic_op(intrinsic):
            self.intrinsic_reads[intrinsic.args[0]] = intrinsic
        elif _is_box_len_intrinsic_op(intrinsic):
            self.intrinsic_lens[intrinsic.args[0]] = intrinsic
        else:
            return


def _is_box_read_intrinsic_op(intrinsic: models.Intrinsic) -> bool:
    match intrinsic.op, intrinsic.immediates:
        case (AVMOp.extract3 | AVMOp.substring3, []):
            return True
        case (AVMOp.extract, [int(), int(l)]) if l > 0:
            return True
        case _:
            return False


def _is_box_len_intrinsic_op(intrinsic: models.Intrinsic) -> bool:
    return intrinsic.op is AVMOp.len_


@attrs.define
class _AddInplaceBoxReadWritesVisitor(MutatingRegisterContext):
    """
    Optimises BoxRead and BoxWrite ops into box operations that operate directly on a box's
    content without loading it into a register.
    This allows having data types in boxes whose size exceed the AVM stack limit (4k)

    Currently, will optimise fixed size types or a dynamic array of fixed size elements
    """

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
        return factory.box_extract_u16(box_read.key, offset)

    def visit_extract_value(self, read: models.ExtractValue) -> models.ValueProvider | None:
        # find box read
        try:
            box_read = self.aggregates.box_reads[read.base]
        except KeyError:
            return None

        aggregate_encoding = read.base_type.encoding
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

        final_encoding = _get_element_encoding(
            aggregate_encoding, read.indexes, read.source_location
        )
        factory = OpFactory(self, merged_loc)
        if final_encoding.is_fixed:
            new_read = _combine_box_read_and_extract_value(factory, box_read.key, read)
        elif _is_dynamic_array_fixed_element(final_encoding):
            new_read = _combine_box_read_and_dynamic_array_read(factory, box_read.key, read)
        else:
            # unsupported
            return None

        assert new_read.types == read.types, "expected replacement types to match"
        self.modified = True
        logger.debug(
            f"combined BoxRead `{read.base !s} = {box_read!s}`\n"
            f"and ExtractValue `{read!s}`\n"
            f"into {new_read!s}",
            location=merged_loc,
        )
        return new_read

    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> models.ValueProvider | None:
        if _is_box_read_intrinsic_op(intrinsic):
            return self._handle_intrinsic_read(intrinsic)
        elif _is_box_len_intrinsic_op(intrinsic):
            return self._handle_intrinsic_len(intrinsic)
        else:
            return None

    def visit_box_write(self, write: models.BoxWrite) -> models.Op | None:
        # see if this box write relates to a mutation we can potentially optimise
        try:
            mutation = self.aggregates.aggregate_mutations[write.value]
        except KeyError:
            return None

        # find corresponding read
        try:
            read_src = self.aggregates.box_reads[mutation.base]
        except KeyError:
            return None

        # can only do an update if the mutation was for a value from the same box
        if write.key != read_src.key:
            return None

        if isinstance(mutation, models.ReplaceValue):
            array_mutation = self.aggregates.aggregate_mutations.get(mutation.value)
            match array_mutation:
                # occurs when box value type is a tuple with a dynamic array member being popped
                # e.g. self.box.value.array_member.pop()
                case models.ArrayPop():
                    return self._combine_box_write_and_nested_array_pop(
                        write, mutation, array_mutation, read_src
                    )
                # occurs when box value type is a tuple with a dynamic array member being extended
                # e.g. self.box.value.array_member.extend(some_iterable) OR
                #      self.box.value.array_member.append(item)
                case models.ArrayConcat():
                    return self._combine_box_write_and_nested_array_concat(
                        write, mutation, array_mutation, read_src
                    )
                case _:
                    # remaining cases occur when box value type is a tuple/struct being mutated
                    # e.g. self.box.value.foo.bar.bax = ...
                    return self._combine_box_write_and_replace_value(write, mutation, read_src)

        dynamic_array_of_fixed_size_enc = _maybe_dynamic_array_fixed_element(mutation.base_type)
        if dynamic_array_of_fixed_size_enc:
            match mutation:
                case models.ArrayPop():
                    # occurs when box value type is a dynamic array being popped
                    # e.g. self.box.value.pop()
                    return self._combine_box_write_and_array_pop(
                        write, mutation, read_src, dynamic_array_of_fixed_size_enc
                    )
                case models.ArrayConcat():
                    # occurs when box value type is a dynamic array being extended
                    # e.g. self.box.value.extend(some_iterable) OR
                    #      self.box.value.append(item)
                    return self._combine_box_write_and_array_concat(
                        write, mutation, read_src, dynamic_array_of_fixed_size_enc
                    )
        return None

    def _handle_intrinsic_read(self, intrinsic: models.Intrinsic) -> models.ValueProvider | None:
        # find box read
        try:
            box_read = self.aggregates.box_reads[intrinsic.args[0]]
        except KeyError:
            return None

        merged_loc = sequential_source_locations_merge(
            (intrinsic.source_location, box_read.source_location)
        )

        factory = OpFactory(self, merged_loc)

        match (intrinsic.op, intrinsic.args, intrinsic.immediates):
            case (AVMOp.extract3, [_, offset, length], []):
                pass
            case (AVMOp.extract, _, [int(offset), int(length)]) if length > 0:
                pass
            case (AVMOp.substring3, [_, offset, end], []):
                length = factory.sub(end, offset, "substring3_length")
            case _:
                raise InternalError("unexpected intrinsic op", merged_loc)

        box_extract = factory.box_extract(
            box_read.key,
            offset,
            length,
            ir_type=intrinsic.types[0],
        )

        self.modified = True
        logger.debug(
            f"combined BoxRead `{intrinsic.args[0] !s} = {box_read!s}`\n"
            f"and Intrinsic `{intrinsic!s}`\n"
            f"into {box_extract!s}",
            location=merged_loc,
        )
        return box_extract

    def _handle_intrinsic_len(self, intrinsic: models.Intrinsic) -> models.ValueProvider | None:
        # find box read
        try:
            box_read = self.aggregates.box_reads[intrinsic.args[0]]
        except KeyError:
            return None

        merged_loc = sequential_source_locations_merge(
            (intrinsic.source_location, box_read.source_location)
        )

        get_box_len = models.Intrinsic(
            op=AVMOp.box_len,
            args=[box_read.key],
            types=[PrimitiveIRType.uint64, PrimitiveIRType.bool],
            source_location=merged_loc,
        )

        box_len, _ = self.materialise_value_provider(get_box_len, ("box_len", "_"))

        self.modified = True
        logger.debug(
            f"combined BoxRead `{intrinsic.args[0] !s} = {box_read!s}`\n"
            f"and Intrinsic `{intrinsic!s}`\n"
            f"into {box_len!s}",
            location=merged_loc,
        )
        return box_len

    def _combine_box_write_and_array_pop(
        self,
        write: models.BoxWrite,
        array_pop: models.ArrayPop,
        read_src: models.BoxRead,
        array_encoding: encodings.ArrayEncoding,
    ) -> models.Op:
        loc = array_pop.source_location
        factory = OpFactory(self, loc)
        pop = _pop_index_from_array_in_place(
            factory,
            array_encoding,
            box_key=write.key,
            array_offset=0,
        )
        self.modified = True
        logger.debug(
            f"combined `{array_pop.base!s} = {read_src!s}"
            f"; {write.value!s} = {array_pop!s}"
            f"; {write}`"
            f" into `{PuyaLibIR.box_dynamic_array_pop_fixed_size}()`",
            location=array_pop.source_location,
        )
        return pop

    def _combine_box_write_and_array_concat(
        self,
        write: models.BoxWrite,
        array_concat: models.ArrayConcat,
        read_src: models.BoxRead,
        array_encoding: encodings.ArrayEncoding,
    ) -> models.Op:
        loc = array_concat.source_location
        factory = OpFactory(self, loc)
        concat = _extend_array_in_place(
            factory,
            array_encoding,
            box_key=write.key,
            array_offset=0,
            new_items_bytes=array_concat.items,
            new_items_count=array_concat.num_items,
        )
        self.modified = True
        logger.debug(
            f"combined `{array_concat.base!s} = {read_src!s}"
            f"; {write.value!s} = {array_concat!s}"
            f" into `{PuyaLibIR.box_dynamic_array_concat_fixed}()`",
            location=loc,
        )
        return concat

    def _combine_box_write_and_nested_array_pop(
        self,
        write: models.BoxWrite,
        replace_value: models.ReplaceValue,
        mutation: models.ArrayPop,
        read_src: models.BoxRead,
    ) -> models.Op | None:
        loc = mutation.source_location
        array_encoding = _maybe_dynamic_array_fixed_element(mutation.base_type)
        assert array_encoding is not None, "expected array encoding"
        array_offset = self._maybe_update_tuple_nested_array_offsets(
            box_key=write.key,
            replace_value=replace_value,
            array_encoding=array_encoding,
            inc_or_dec="dec",
            offset_delta=array_encoding.element.checked_num_bytes,
            loc=loc,
        )
        # return if no update occurred
        if not array_offset:
            return None
        factory = OpFactory(self, loc)
        pop = _pop_index_from_array_in_place(
            factory,
            array_encoding,
            box_key=write.key,
            array_offset=array_offset,
        )
        self.modified = True
        logger.debug(
            f"combined `{replace_value.base!s} = {read_src!s}"
            f"; {write.value!s} = {replace_value!s}"
            f"; {replace_value.value!s} = {mutation!s}"
            f"; {write!s}`"
            f" into `{pop}`",
            location=mutation.source_location,
        )
        return pop

    def _combine_box_write_and_nested_array_concat(
        self,
        write: models.BoxWrite,
        replace_value: models.ReplaceValue,
        mutation: models.ArrayConcat,
        read_src: models.BoxRead,
    ) -> models.Op | None:
        """
        Combines a BoxWrite, ReplaceValue and ArrayConcat into operations that work
        directly on the box.
        """
        loc = mutation.source_location
        factory = OpFactory(self, loc)
        array_encoding = _maybe_dynamic_array_fixed_element(mutation.base_type)
        assert array_encoding is not None, "expected array encoding"
        element_size = array_encoding.element.checked_num_bytes

        array_offset = self._maybe_update_tuple_nested_array_offsets(
            box_key=write.key,
            replace_value=replace_value,
            array_encoding=array_encoding,
            inc_or_dec="inc",
            offset_delta=factory.mul(mutation.num_items, element_size),
            loc=loc,
        )
        if not array_offset:
            return None
        concat = _extend_array_in_place(
            factory,
            array_encoding,
            box_key=write.key,
            array_offset=array_offset,
            new_items_bytes=mutation.items,
            new_items_count=mutation.num_items,
        )
        self.modified = True
        logger.debug(
            f"combined `{replace_value.base!s} = {read_src!s}"
            f"; {write.value!s} = {replace_value!s}"
            f"; {replace_value.value!s} = {mutation!s}"
            f"; {write!s}`"
            f" into `{concat}`",
            location=mutation.source_location,
        )
        return concat

    def _maybe_update_tuple_nested_array_offsets(
        self,
        box_key: models.Value,
        replace_value: models.ReplaceValue,
        array_encoding: ArrayEncoding,
        inc_or_dec: typing.Literal["inc", "dec"],
        offset_delta: models.Value | int,
        loc: SourceLocation | None,
    ) -> models.Value | None:
        """
        When a dynamic array is nested inside a tuple, this will update relevant head pointers
        to ensure offsets are correct after resizing a dynamic array by offset_delta
        """
        factory = OpFactory(self, loc)
        tuple_dynamic_offsets = _get_tuple_dynamic_offsets_requiring_update(
            factory,
            box_key,
            replace_value.base_type.encoding,
            replace_value.indexes,
        )
        if tuple_dynamic_offsets is None:
            return None
        array_offset = _get_fixed_byte_offset(
            factory,
            box_key=box_key,
            encoding=replace_value.base_type.encoding,
            indexes=replace_value.indexes,
            stop_at_valid_stack_value=False,
        )
        assert array_offset.encoding == array_encoding, "encodings should match"
        for offset in tuple_dynamic_offsets:
            invoke = factory.invoke(
                PuyaLibIR[f"box_update_offset_{inc_or_dec}"],
                [box_key, offset, offset_delta],
            )
            self.add_op(invoke)
        return array_offset.offset

    def _combine_box_write_and_replace_value(
        self, write: models.BoxWrite, replace_value: models.ReplaceValue, read_src: models.BoxRead
    ) -> models.Op | None:
        # only support fixed size writes
        # TODO: support writing a whole dynamic array
        #       e.g self.box.value.arr = Array[UInt64]()
        if _get_element_encoding(
            replace_value.base_type.encoding, replace_value.indexes, replace_value.source_location
        ).is_dynamic:
            return None

        merged_loc = sequential_source_locations_merge(
            (replace_value.source_location, write.source_location)
        )
        factory = OpFactory(self, merged_loc)
        # TODO: determine for writes if calculating the offset and asserting indexes
        #       is more efficient than doing N reads & writes
        box_key = write.key
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
            # currently only occurs when agg_write.encoding.is_bit
            encoding = fixed_offset.encoding
            extract_ir_type = EncodedType(encoding)
            box_extract = factory.box_extract(
                box_key,
                fixed_offset.offset,
                fixed_offset.encoding.checked_num_bytes,
                ir_type=extract_ir_type,
            )
            assert isinstance(
                encoding, TupleEncoding | ArrayEncoding
            ), "expected aggregate encoding"
            value = factory.materialise_single(
                models.ReplaceValue(
                    base=box_extract,
                    base_type=extract_ir_type,
                    value=replace_value.value,
                    indexes=fixed_offset.remaining_indexes,
                    source_location=merged_loc,
                )
            )
        replace = factory.box_replace(
            box_key, fixed_offset.offset, value, error_message="index out of bounds"
        )
        self.modified = True
        logger.debug(
            f"combined `{replace_value.base!s} = {read_src!s}"
            f"; {write.value!s} = {replace_value!s}"
            f"; {write!s}`"
            f" into `{replace!s}`",
            location=replace.source_location,
        )
        return replace


def _get_element_encoding(
    encoding: encodings.Encoding, indexes: Sequence[int | models.Value], loc: SourceLocation | None
) -> encodings.Encoding:
    """Get the encoding of the final element after following the index path."""
    indexes = list(reversed(indexes))
    while indexes:
        index = indexes.pop()
        if isinstance(encoding, encodings.TupleEncoding) and isinstance(index, int):
            encoding = encoding.elements[index]
        elif isinstance(encoding, encodings.ArrayEncoding):
            encoding = encoding.element
        else:
            raise InternalError("invalid index sequence", loc)
    return encoding


def _get_tuple_dynamic_offsets_requiring_update(
    factory: OpFactory,
    box_key: models.Value,
    encoding: encodings.Encoding,
    indexes: Sequence[models.Value | int],
) -> list[models.Value] | None:
    """
    Finds all the offsets pointing to head elements that require updating after resizing an array,
    these are all the dynamic tuple members that come after the modified array in its parent tuple,
    and recursively each dynamic member that comes after a modified element.

    Returns None if not a supported scenario
    """
    result = list[models.Value]()
    indexes = list(reversed(indexes))
    box_offset = factory.constant(0)
    while indexes:
        index = indexes.pop()
        if not (isinstance(encoding, encodings.TupleEncoding) and isinstance(index, int)):
            # nested array updates are not supported
            return None
        next_index = index + 1
        # track any other dynamic offsets after the indexed element
        dynamic_indexes = [el_idx for el_idx, el in enumerate(encoding.elements) if el.is_dynamic]
        for el_idx in dynamic_indexes:
            if el_idx >= next_index:
                head_offset = bits_to_bytes(encoding.get_head_bit_offset(el_idx))
                result.append(factory.add(box_offset, head_offset))
        if not indexes:
            # stop if there are no more indexes to process
            break
        element_encoding = encoding.elements[index]
        if not element_encoding.is_dynamic:
            # because this function is only looking at the index sequence to a dynamic array
            # every element in that sequence should also be dynamic
            # if this isn't true for any reason, return early
            return None
        # if there are more indexes to process need to calculate this element's offset
        element_offset: models.Value | int
        # first dynamic element has a statically known offset
        if index == dynamic_indexes[0]:
            # first dynamic element - use tail offset (statically known)
            element_offset = bits_to_bytes(encoding.get_head_bit_offset(None))
        else:
            # Calculate the offset that contains the offset to read from the box
            head_offset = bits_to_bytes(encoding.get_head_bit_offset(index))
            offset_ptr_position = factory.add(box_offset, head_offset)
            # Read the actual offset from the box
            element_offset = factory.box_extract_u16(box_key, offset_ptr_position)
        box_offset = factory.add(box_offset, element_offset)
        encoding = element_encoding
    return result


def _pop_index_from_array_in_place(
    factory: OpFactory,
    encoding: ArrayEncoding,
    *,
    box_key: models.Value,
    array_offset: models.Value | int,
) -> models.Op:
    fixed_element_size = encoding.element.checked_num_bytes
    return factory.invoke(
        PuyaLibIR.box_dynamic_array_pop_fixed_size,
        [box_key, array_offset, fixed_element_size],
    )


def _extend_array_in_place(
    factory: OpFactory,
    encoding: ArrayEncoding,
    *,
    box_key: models.Value,
    array_offset: models.Value | int,
    new_items_bytes: models.Value,
    new_items_count: models.Value,
) -> models.Op:
    fixed_element_size = encoding.element.checked_num_bytes
    return factory.invoke(
        PuyaLibIR.box_dynamic_array_concat_fixed,
        [box_key, array_offset, new_items_bytes, new_items_count, fixed_element_size],
    )


def _combine_box_read_and_extract_value(
    factory: OpFactory,
    box_key: models.Value,
    agg_read: models.ExtractValue,
) -> models.ValueProvider:
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
        error_message="index out of bounds",
    )
    remaining_indexes = fixed_offset.remaining_indexes
    if not remaining_indexes:
        return box_extract

    assert isinstance(
        encoding_at_offset, TupleEncoding | ArrayEncoding
    ), "expected aggregate encoding"
    new_agg_read = models.ExtractValue(
        base=box_extract,
        base_type=extract_ir_type,
        indexes=remaining_indexes,
        check_bounds=agg_read.check_bounds,
        ir_type=agg_read.ir_type,
        source_location=factory.source_location,
    )
    return new_agg_read


def _combine_box_read_and_dynamic_array_read(
    factory: OpFactory,
    box_key: models.Value,
    agg_read: models.ExtractValue,
) -> models.ValueProvider:
    array_offset = _get_fixed_byte_offset(
        factory,
        box_key=box_key,
        encoding=agg_read.base_type.encoding,
        indexes=agg_read.indexes,
        stop_at_valid_stack_value=False,
    )
    array_encoding = array_offset.encoding
    assert isinstance(array_encoding, ArrayEncoding), "expected array encoding"
    assert array_encoding.length_header, "expected dynamic array with length header"
    assert array_encoding.element.is_fixed, "expected fixed size elements"

    # Read array length header (2 bytes at array_offset)
    array_length = factory.box_extract_u16(box_key, array_offset.offset)

    # Calculate total bytes: 2 + array_length * element_size
    element_size = array_encoding.element.checked_num_bytes
    data_bytes = factory.mul(array_length, element_size, "data_bytes")
    total_bytes = factory.add(data_bytes, 2, "total_bytes")

    # Extract the entire array
    return factory.box_extract(
        box_key,
        array_offset.offset,
        total_bytes,
        ir_type=agg_read.ir_type,
    )


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
    """
    For a given encoding and index sequence will determine what offset is needed to read
    the final element in the aggregate
    """
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
            _assert_index_is_in_array_bounds(factory, encoding, box_key, box_offset, index)
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


def _assert_index_is_in_array_bounds(
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


def _is_dynamic_array_fixed_element(
    encoding: encodings.Encoding,
) -> typing.TypeGuard[encodings.ArrayEncoding]:
    if not isinstance(encoding, encodings.ArrayEncoding):
        return False
    return encoding.length_header and encoding.element.is_fixed


def _maybe_dynamic_array_fixed_element(typ: EncodedType) -> encodings.ArrayEncoding | None:
    encoding = typ.encoding
    if _is_dynamic_array_fixed_element(encoding):
        return encoding
    else:
        return None
