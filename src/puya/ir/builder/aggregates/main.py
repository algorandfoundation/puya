import typing
from collections.abc import Sequence

import attrs

from puya import log
from puya.avm import AVMType
from puya.errors import InternalError
from puya.ir import (
    models,
    models as ir,
)
from puya.ir._puya_lib import PuyaLibIR
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import OpFactory
from puya.ir.builder.aggregates import arc4_codecs, sequence, tup
from puya.ir.encodings import ArrayEncoding, Encoding, TupleEncoding
from puya.ir.mutating_register_context import MutatingRegisterContext
from puya.parse import SourceLocation
from puya.utils import bits_to_bytes

logger = log.get_logger(__name__)


def lower_aggregate_nodes(program: ir.Program) -> None:
    embedded_funcs = {PuyaLibIR(s.id): s for s in program.subroutines if s.id in PuyaLibIR}
    for sub in program.all_subroutines:
        replacer = _AggregateNodeReplacer(embedded_funcs=embedded_funcs, subroutine=sub)
        replacer.process_and_validate()


@attrs.define(kw_only=True)
class _AggregateNodeReplacer(MutatingRegisterContext):
    @typing.override
    def visit_value_encode(self, encode: models.ValueEncode) -> models.ValueProvider:
        self.modified = True
        return arc4_codecs.encode_value(
            self,
            values=encode.values,
            value_type=encode.value_type,
            encoding=encode.encoding,
            loc=encode.source_location,
        )

    @typing.override
    def visit_value_decode(self, decode: models.ValueDecode) -> models.ValueProvider:
        self.modified = True
        return arc4_codecs.decode_value(
            self,
            decode.value,
            encoding=decode.encoding,
            target_type=decode.decoded_type,
            loc=decode.source_location,
        )

    @typing.override
    def visit_array_read_index(self, read: ir.ArrayReadIndex) -> ir.ValueProvider:
        self.modified = True

        return sequence.read_at_index(
            self,
            array_encoding=read.array_encoding,
            array=read.array,
            index=read.index,
            loc=read.source_location,
            assert_bounds=read.check_bounds,
        )

    @typing.override
    def visit_array_write_index(self, write: ir.ArrayWriteIndex) -> ir.Value:
        self.modified = True

        return sequence.write_at_index(
            self,
            array_encoding=write.array_encoding,
            array=write.array,
            index=write.index,
            value=write.value,
            loc=write.source_location,
        )

    @typing.override
    def visit_aggregate_read_index(self, read: ir.AggregateReadIndex) -> ir.Value:
        self.modified = True

        loc = read.source_location
        factory = OpFactory(self, loc)

        aggregate_encoding = read.aggregate_encoding
        base = read.base
        if (
            not aggregate_encoding.is_dynamic
        ):  # and aggregate_encoding.checked_num_bytes > MAX_BYTES_LENGTH:
            total_offset = self._get_fixed_offset(aggregate_encoding, read.indexes, loc)
            if read.element_encoding.is_bit:
                return factory.get_bit(value=base, index=total_offset)
            else:
                return factory.extract3(
                    base, total_offset, read.element_encoding.checked_num_bytes
                )

        base_encoding: Encoding = aggregate_encoding
        # TODO: for fixed sized types handle read.indexes as a single op using an offset and length
        for index in read.indexes:
            if isinstance(base_encoding, TupleEncoding):
                assert isinstance(index, int), "expected int"
                base = tup.read_at_index(
                    self,
                    base_encoding,
                    base,
                    index,
                    loc,
                )
                base_encoding = base_encoding.elements[index]
            elif isinstance(base_encoding, ArrayEncoding):
                if isinstance(index, int):
                    index = factory.constant(index)
                base = sequence.read_at_index(
                    self, base_encoding, base, index, loc, assert_bounds=read.check_bounds
                )
                base_encoding = base_encoding.element
            else:
                raise InternalError("invalid aggregate encoding and index", loc)

        return base

    @typing.override
    def visit_aggregate_write_index(self, write: ir.AggregateWriteIndex) -> ir.Value:
        self.modified = True

        loc = write.source_location
        factory = OpFactory(self, loc)

        aggregate_encoding = write.aggregate_encoding
        base = write.base
        bases = []
        # special handling when the base value is too big to fit on the stack e.g.
        # when there is a box involved
        if (
            not aggregate_encoding.is_dynamic
        ):  # and aggregate_encoding.checked_num_bytes > MAX_BYTES_LENGTH:
            total_offset = self._get_fixed_offset(aggregate_encoding, write.indexes, loc)
            if write.element_encoding.is_bit:
                value = write.value
                if value.ir_type.avm_type == AVMType.uint64:
                    # TODO: ensure coverage of this, might need to update requires_conversion
                    is_true = value
                else:
                    is_true = factory.get_bit(value, 0, "is_true")
                return factory.set_bit(value=base, index=total_offset, bit=is_true)
            else:
                return factory.replace(base, total_offset, write.value)

        base_encoding: Encoding = aggregate_encoding
        for index in write.indexes:
            bases.append((base, base_encoding))
            if isinstance(base_encoding, TupleEncoding):
                assert isinstance(index, int), "expected int"
                base = tup.read_at_index(
                    self,
                    base_encoding,
                    base,
                    index,
                    loc,
                )
                base_encoding = base_encoding.elements[index]
            elif isinstance(base_encoding, ArrayEncoding):
                if isinstance(index, int):
                    index = factory.constant(index)
                base = sequence.read_at_index(self, base_encoding, base, index, loc)
                base_encoding = base_encoding.element
            else:
                raise InternalError("invalid aggregate encoding and index", loc)

        value = write.value
        for index in reversed(write.indexes):
            base, base_encoding = bases.pop()
            if isinstance(base_encoding, TupleEncoding):
                assert isinstance(index, int), "expected int"
                value = tup.write_at_index(
                    self,
                    base_encoding,
                    base,
                    index,
                    value,
                    loc,
                )
            elif isinstance(base_encoding, ArrayEncoding):
                if isinstance(index, int):
                    index = factory.constant(index)
                value = sequence.write_at_index(self, base_encoding, base, index, value, loc)
            else:
                raise InternalError("invalid aggregate encoding and index", loc)

        return value

    def visit_box_read(self, read: models.BoxRead) -> models.ValueProvider:
        return models.Intrinsic(
            op=AVMOp.box_get,
            args=[read.key],
            types=read.types,
            source_location=read.source_location,
        )

    def visit_box_write(self, write: models.BoxWrite) -> None:
        self.add_op(
            models.Intrinsic(
                op=AVMOp.box_put,
                args=[write.key, write.value],
                source_location=write.source_location,
            )
        )

    def _get_fixed_offset(
        self,
        base_encoding: Encoding,
        indexes: Sequence[int | ir.Value],
        loc: SourceLocation | None,
    ) -> ir.Value:
        factory = OpFactory(self, loc)
        total_offset = factory.constant(0)
        last_i = len(indexes) - 1
        for i, index in enumerate(indexes):
            if isinstance(base_encoding, TupleEncoding):
                assert isinstance(index, int), "expected int"
                bit_offset_int = base_encoding.get_head_bit_offset(index)
                bit_offset: int | ir.Value = bit_offset_int
                byte_offset: int | ir.Value = bits_to_bytes(bit_offset_int)
                base_encoding = base_encoding.elements[index]
            elif isinstance(base_encoding, ArrayEncoding):
                # TODO: assert indexes are < length
                bit_offset = index
                byte_offset = factory.mul(index, base_encoding.element.checked_num_bytes)
                base_encoding = base_encoding.element
            else:
                raise InternalError("invalid aggregate encoding and index", loc)
            if base_encoding.is_bit:
                assert i == last_i, "expected to be last index"
                total_offset = factory.mul(total_offset, 8)
                total_offset = factory.add(total_offset, bit_offset)
            else:
                total_offset = factory.add(total_offset, byte_offset)
        return total_offset
