import typing
from collections import defaultdict

import attrs

from puya import log
from puya.algo_constants import MAX_BYTES_LENGTH
from puya.context import CompileContext
from puya.errors import InternalError
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.encodings import (
    ArrayEncoding,
    Encoding,
    FixedArrayEncoding,
    TupleEncoding,
)
from puya.ir.mutating_register_context import MutatingRegisterContext
from puya.ir.op_utils import OpFactory, assert_value
from puya.ir.optimize.context import IROptimizationContext
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import EncodedType
from puya.ir.visitor import IRTraverser
from puya.parse import SourceLocation, sequential_source_locations_merge
from puya.utils import bits_to_bytes

logger = log.get_logger(__name__)

_TOp = typing.TypeVar("_TOp")


def replace_aggregate_box_ops(
    context: IROptimizationContext, subroutine: models.Subroutine
) -> bool:
    aggregates = _AggregateCollector.collect(subroutine)
    replacer = _AggregateReplacer(
        temp_prefix="box",
        aggregates=aggregates,
        subroutine=subroutine,
        embedded_funcs=context.embedded_funcs,
    )
    replacer.process_and_validate()
    return replacer.modified


class _Ass(typing.NamedTuple, typing.Generic[_TOp]):
    ass: models.Assignment
    op: _TOp


@attrs.define(kw_only=True)
class _AggregateCollector(IRTraverser):
    agg_writes: dict[models.Value, _Ass[models.AggregateWriteIndex]] = attrs.field(factory=dict)
    box_reads: dict[models.Value, _Ass[models.BoxRead]] = attrs.field(factory=dict)
    agg_read_bases: defaultdict[models.Value, list[models.AggregateReadIndex]] = attrs.field(
        factory=lambda: defaultdict(list)
    )

    @classmethod
    def collect(cls, sub: models.Subroutine) -> typing.Self:
        collector = cls()
        collector.visit_all_blocks(sub.body)
        return collector

    @typing.override
    def visit_assignment(self, ass: models.Assignment) -> None:
        source = ass.source
        match source:
            case models.AggregateReadIndex():
                self.agg_read_bases[source.base].append(source)
            case models.AggregateWriteIndex():
                (target,) = ass.targets
                self.agg_writes[target] = _Ass(ass, source)
            case models.BoxRead():
                (value,) = ass.targets
                self.box_reads[value] = _Ass(ass, source)


@attrs.define
class _AggregateReplacer(MutatingRegisterContext):
    aggregates: _AggregateCollector

    def visit_aggregate_read_index(self, read: models.AggregateReadIndex) -> models.ValueProvider:
        if not _box_extract_required(read):
            return read

        maybe_box_register = read.base
        try:
            box_read = self.aggregates.box_reads[maybe_box_register]
        except KeyError:
            return read

        merged_loc = sequential_source_locations_merge(
            (box_read.op.source_location, read.source_location)
        )
        new_read = _combine_box_and_aggregate_read(
            self,
            box_read.op.key,
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
                f"and AggregateReadIndex `{read!s}`\n"
                f"into {new_read!s}",
                location=merged_loc,
            )
            return new_read

    def visit_box_write(self, write: models.BoxWrite) -> models.BoxWrite | None:
        try:
            agg_write_ass = self.aggregates.agg_writes[write.value]
        except KeyError:
            return write
        agg_write = agg_write_ass.op
        if agg_write.aggregate_encoding.is_dynamic:
            return write
        try:
            read_src_ass = self.aggregates.box_reads[agg_write.base]
        except KeyError:
            return write
        read_src = read_src_ass.op
        # can only do an in-place update if the agg write was for a value from the same box
        if write.key != read_src.key:
            return write
        merged_loc = sequential_source_locations_merge(
            (agg_write.source_location, write.source_location)
        )
        new_write = _combine_aggregate_and_box_write(
            self,
            agg_write,
            write.key,
            merged_loc,
        )
        if new_write is None:
            return write
        else:
            self.modified = True
            self.add_op(new_write)
            logger.debug(
                f"combined BoxRead `{agg_write.base!s} = {read_src!s}`\n"
                f"and AggregateWriteIndex `{write.value!s} = {agg_write!s}`\n"
                f"and BoxWrite `{write!s}`\n"
                f"into {new_write!s}",
                location=merged_loc,
            )
            return None


def _combine_aggregate_and_box_write(
    context: IRRegisterContext,
    agg_write: models.AggregateWriteIndex,
    box_key: models.Value,
    loc: SourceLocation | None,
) -> models.Op:
    factory = OpFactory(context, loc)

    base_encoding: Encoding = agg_write.aggregate_encoding
    indexes = agg_write.indexes
    check_array_bounds = False
    box_offset = factory.constant(0)
    # TODO: determine for writes if calculating the offset and asserting indexes
    #       is more efficient than doing N reads & writes
    for index in indexes:
        if isinstance(base_encoding, TupleEncoding) and isinstance(index, int):
            bit_offset = base_encoding.get_head_bit_offset(index)
            element_offset: int | models.Value = bits_to_bytes(bit_offset)
            has_trailing_data = (index + 1) != len(base_encoding.elements)
            # if we aren't reading the last item of a tuple
            # then any following array read will need a bounds check
            check_array_bounds = check_array_bounds or has_trailing_data
            base_encoding = base_encoding.elements[index]
        elif isinstance(base_encoding, FixedArrayEncoding):
            if check_array_bounds:
                index_ok = factory.lt(index, base_encoding.size, "index_ok")
                assert_value(
                    context, index_ok, error_message="index out of bounds", source_location=loc
                )
            element_offset = factory.mul(
                index, base_encoding.element.checked_num_bytes, "element_offset"
            )
            base_encoding = base_encoding.element
            # always need to check array bounds after the first array read
            check_array_bounds = True
        else:
            raise InternalError("invalid aggregate encoding and index", loc)
        box_offset = factory.add(box_offset, element_offset, "offset")
    return factory.box_replace(
        box_key,
        box_offset,
        agg_write.value,
    )


def _box_extract_required(read: models.AggregateReadIndex) -> bool:
    aggregate_encoding = read.aggregate_encoding
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
    agg_read: models.AggregateReadIndex,
    loc: SourceLocation | None,
) -> models.ValueProvider | None:
    # TODO: it is also feasible and practical to support a DynamicArray of fixed elements at the
    #       root level, as this just requires a box_extract for the length
    factory = OpFactory(context, loc)
    indexes = agg_read.indexes
    check_array_bounds = False
    if agg_read.element_encoding.is_bit:
        # bit reads can't be done directly from a box
        # so read up to previous aggregate and then return
        if len(indexes) == 1:
            return None
        else:
            read_agg_up_to_bit = attrs.evolve(agg_read, indexes=indexes[:-1])
            box_extract = _combine_box_and_aggregate_read(
                context, box_key, read_agg_up_to_bit, loc
            )
            # should always give a value since bit reads can't be nested
            assert box_extract is not None, "expected box_extract"
            box_extract = factory.materialise_single(box_extract, "box_read_from_agg")
            return attrs.evolve(
                agg_read,
                base=box_extract,
                indexes=indexes[-1:],
            )

    box_offset = factory.constant(0)
    base_encoding: Encoding = agg_read.aggregate_encoding
    next_index = 0
    for index in indexes:
        if isinstance(base_encoding, TupleEncoding) and isinstance(index, int):
            bit_offset = base_encoding.get_head_bit_offset(index)
            element_offset: int | models.Value = bits_to_bytes(bit_offset)
            has_trailing_data = (index + 1) != len(base_encoding.elements)
            # if we aren't reading the last item of a tuple
            # then any following array read will need a bounds check
            check_array_bounds = check_array_bounds or has_trailing_data
            base_encoding = base_encoding.elements[index]
        elif isinstance(base_encoding, FixedArrayEncoding):
            if check_array_bounds:
                index_ok = factory.lt(index, base_encoding.size, "index_ok")
                assert_value(
                    context, index_ok, error_message="index out of bounds", source_location=loc
                )
            element_offset = factory.mul(
                index, base_encoding.element.checked_num_bytes, "element_offset"
            )
            base_encoding = base_encoding.element
            # always need to check array bounds after the first array read
            check_array_bounds = True
        else:
            raise InternalError("invalid aggregate encoding and index", loc)
        box_offset = factory.add(box_offset, element_offset, "offset")
        next_index += 1
        # exit loop if the resulting value can fit on stack
        # generally more optimizations are possible the sooner a value is read
        if base_encoding.checked_num_bytes < MAX_BYTES_LENGTH:
            break

    box_extract = factory.box_extract(
        box_key,
        box_offset,
        base_encoding.checked_num_bytes,
        ir_type=EncodedType(base_encoding),
    )
    remaining_indexes = agg_read.indexes[next_index:]
    if not remaining_indexes:
        return box_extract

    box_extract = factory.materialise_single(box_extract, "box_read_from_agg")
    assert isinstance(base_encoding, TupleEncoding | ArrayEncoding), "expected aggregate encoding"
    new_agg_read = attrs.evolve(
        agg_read,
        base=box_extract,
        aggregate_encoding=base_encoding,
        indexes=remaining_indexes,
        check_bounds=False,
        source_location=loc,
    )
    assert (
        agg_read.element_encoding == new_agg_read.element_encoding
    ), "expected encodings to be preserved"
    return new_agg_read


def minimize_box_exist_asserts(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    modified = False
    for block in subroutine.body:
        if _remove_box_exists(block):
            modified = True
    return modified


def _remove_box_exists(block: models.BasicBlock) -> bool:
    #   for any box op that returns an exist flag that is asserted
    #   can remove any asserts after the first one as long as the box register is the same
    #   and no box_del op is called
    #   begin block | subroutine call
    #       exist state of all box keys are unknown
    #   box_create | box_extract | box_put | box_replace | box_resize | box_splice key
    #       set box key as known to exist
    #   box_del key
    #       sett box key as known to not exist
    #   box_get | box_len
    #       if unknown if box exists then keep the assert, assume box exists after assert
    #       if known that box exists then remove any asserts
    #       if known that box does not exist then replace asserts with err

    modified = False
    box_exists = dict[models.Value, bool]()

    box_exists_regs = dict[models.Value, models.Value]()
    for op in block.ops.copy():
        maybe_ass = None
        if isinstance(op, models.Assignment):
            maybe_ass = op
            maybe_intrinsic: models.IRVisitable = op.source
        else:
            maybe_intrinsic = op
        if isinstance(maybe_intrinsic, models.Intrinsic):
            if maybe_intrinsic.op in (
                AVMOp.box_create,
                AVMOp.box_extract,
                AVMOp.box_put,
                AVMOp.box_replace,
                AVMOp.box_resize,
                AVMOp.box_splice,
            ):
                box_key = maybe_intrinsic.args[0]
                box_exists[box_key] = True
            elif maybe_intrinsic.op == AVMOp.box_del:
                # conservative assume could be deleting any box
                box_exists.clear()
            elif maybe_ass and maybe_intrinsic.op in (AVMOp.box_get, AVMOp.box_len):
                box_key = maybe_intrinsic.args[0]
                _, exists_reg = maybe_ass.targets
                box_exists_regs[exists_reg] = box_key
            elif (
                maybe_intrinsic.op == AVMOp.assert_
                and (box_exists_reg := maybe_intrinsic.args[0]) in box_exists_regs
            ):
                box_key = box_exists_regs[box_exists_reg]
                try:
                    box_does_exist = box_exists[box_key]
                except KeyError:
                    # current state of box is unknown, but can assume it exists after this op
                    box_exists[box_key] = True
                    continue
                if box_does_exist:
                    logger.debug(
                        f"box_key {box_key} is known to exist, removing assert",
                        location=op.source_location,
                    )
                    # box exists, so can remove assert
                    block.ops.remove(op)
                    modified = True
        elif isinstance(maybe_intrinsic, models.InvokeSubroutine):
            box_exists.clear()
    return modified
