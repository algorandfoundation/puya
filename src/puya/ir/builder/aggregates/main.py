import typing

import attrs

from puya import log
from puya.errors import InternalError
from puya.ir import (
    models as ir,
    types_ as types,
)
from puya.ir._puya_lib import PuyaLibIR
from puya.ir.avm_ops import AVMOp
from puya.ir.builder.aggregates import arc4_codecs, sequence, tup
from puya.ir.encodings import ArrayEncoding, Encoding, TupleEncoding
from puya.ir.mutating_register_context import MutatingRegisterContext
from puya.ir.op_utils import assert_value

logger = log.get_logger(__name__)


def lower_aggregate_nodes(program: ir.Program) -> None:
    embedded_funcs = {PuyaLibIR(s.id): s for s in program.subroutines if s.id in PuyaLibIR}
    for sub in program.all_subroutines:
        replacer = _AggregateNodeReplacer(
            embedded_funcs=embedded_funcs, subroutine=sub, temp_prefix="aggregate"
        )
        for block in sub.body:
            replacer.visit_block(block)
        sub.validate_with_ssa()


@attrs.define(kw_only=True)
class _AggregateNodeReplacer(MutatingRegisterContext):
    @typing.override
    def visit_bytes_encode(self, encode: ir.BytesEncode) -> ir.ValueProvider:
        return arc4_codecs.encode_to_bytes(
            self,
            values=encode.values,
            values_type=encode.values_type,
            encoding=encode.encoding,
            error_message_override=encode.error_message_override,
            loc=encode.source_location,
        )

    @typing.override
    def visit_decode_bytes(self, decode: ir.DecodeBytes) -> ir.ValueProvider:
        return arc4_codecs.decode_bytes(
            self,
            decode.value,
            encoding=decode.encoding,
            target_type=decode.ir_type,
            error_message_override=decode.error_message_override,
            loc=decode.source_location,
        )

    @typing.override
    def visit_array_length(self, length: ir.ArrayLength) -> ir.ValueProvider:
        return sequence.get_length(
            self, length.array_encoding, length.base, length.source_location
        )

    @typing.override
    def visit_extract_value(self, read: ir.ExtractValue) -> ir.Value:
        loc = read.source_location

        aggregate_encoding = read.base_type.encoding
        base = read.base
        base_encoding: Encoding = aggregate_encoding
        for index in read.indexes:
            if isinstance(base_encoding, TupleEncoding):
                assert isinstance(index, int), "expected int"
                base = tup.read_at_index(self, base_encoding, base, index, loc)
                base_encoding = base_encoding.elements[index]
            elif isinstance(base_encoding, ArrayEncoding):
                if isinstance(index, int):
                    index = ir.UInt64Constant(value=index, source_location=loc)
                base = sequence.read_at_index(
                    self, base_encoding, base, index, loc, assert_bounds=read.check_bounds
                )
                base_encoding = base_encoding.element
            else:
                raise InternalError("invalid aggregate encoding and index", loc)

        return base

    @typing.override
    def visit_replace_value(self, write: ir.ReplaceValue) -> ir.Value:
        loc = write.source_location

        aggregate_encoding = write.base_type.encoding
        base = write.base
        bases = []
        base_encoding: Encoding = aggregate_encoding
        for index in write.indexes:
            bases.append((base, base_encoding))
            if isinstance(base_encoding, TupleEncoding):
                assert isinstance(index, int), "expected int"
                base = tup.read_at_index(self, base_encoding, base, index, loc)
                base_encoding = base_encoding.elements[index]
            elif isinstance(base_encoding, ArrayEncoding):
                if isinstance(index, int):
                    index = ir.UInt64Constant(value=index, source_location=loc)
                base = sequence.read_at_index(self, base_encoding, base, index, loc)
                base_encoding = base_encoding.element
            else:
                raise InternalError("invalid aggregate encoding and index", loc)

        value = write.value
        for index in reversed(write.indexes):
            base, base_encoding = bases.pop()
            if isinstance(base_encoding, TupleEncoding):
                assert isinstance(index, int), "expected int"
                value = tup.write_at_index(self, base_encoding, base, index, value, loc)
            elif isinstance(base_encoding, ArrayEncoding):
                if isinstance(index, int):
                    index = ir.UInt64Constant(value=index, source_location=loc)
                value = sequence.write_at_index(self, base_encoding, base, index, value, loc)
            else:
                raise InternalError("invalid aggregate encoding and index", loc)

        return value

    @typing.override
    def visit_box_read(self, read: ir.BoxRead) -> ir.ValueProvider:
        loc = read.source_location

        box_get = ir.Intrinsic(
            op=AVMOp.box_get,
            args=[read.key],
            types=[*read.types, types.bool_],
            source_location=loc,
        )
        box_value, box_exists = self.materialise_value_provider(box_get, "box_get")
        assert_value(
            self, box_exists, error_message=read.exists_assertion_message, source_location=loc
        )
        return box_value

    @typing.override
    def visit_box_write(self, write: ir.BoxWrite) -> ir.Intrinsic:
        if write.delete_first:
            self.add_op(
                ir.Intrinsic(
                    op=AVMOp.box_del,
                    args=[write.key],
                    source_location=write.source_location,
                )
            )
        return ir.Intrinsic(
            op=AVMOp.box_put,
            args=[write.key, write.value],
            source_location=write.source_location,
        )
