import itertools
import typing
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence

import attrs

from puya import log
from puya.avm import AVMType
from puya.errors import InternalError
from puya.ir import (
    models,
    models as ir,
)
from puya.ir._puya_lib import PuyaLibIR
from puya.ir.builder._utils import OpFactory, assign_targets
from puya.ir.builder.aggregates import arc4_codecs, sequence, tup
from puya.ir.encodings import ArrayEncoding, Encoding, TupleEncoding
from puya.ir.models import Register, Subroutine, Value, ValueProvider, ValueTuple
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import IRType
from puya.ir.visitor import IRTraverser
from puya.ir.visitor_mutator import IRMutator
from puya.parse import SourceLocation
from puya.utils import bits_to_bytes

logger = log.get_logger(__name__)


def lower_aggregate_nodes(program: ir.Program, subroutine: ir.Subroutine) -> bool:
    existing_versions = _VersionGatherer.gather(subroutine)
    embedded_funcs = {PuyaLibIR(s.id): s for s in program.subroutines if s.id in PuyaLibIR}
    replacer = _AggregateNodeReplacer(versions=existing_versions, embedded_funcs=embedded_funcs)
    for block in subroutine.body:
        replacer.visit_block(block)
    return replacer.modified


@attrs.define
class _VersionGatherer(IRTraverser):
    versions: dict[str, int] = attrs.field(factory=dict)

    @classmethod
    def gather(cls, sub: ir.Subroutine) -> dict[str, int]:
        visitor = cls()
        visitor.visit_all_blocks(sub.body)
        return visitor.versions

    def visit_register(self, reg: ir.Register) -> None:
        self.versions[reg.name] = max(self.versions.get(reg.name, 0), reg.version)


@attrs.define(kw_only=True)
class _AggregateNodeReplacer(IRMutator, IRRegisterContext):
    _versions: dict[str, int]
    modified: bool = False
    _tmp_counters: defaultdict[str, Iterator[int]] = attrs.field(
        factory=lambda: defaultdict(itertools.count)
    )
    _embedded_funcs: Mapping[PuyaLibIR, Subroutine]

    def resolve_embedded_func(self, full_name: PuyaLibIR) -> Subroutine:
        return self._embedded_funcs[full_name]

    def materialise_value_provider(
        self, value_provider: ValueProvider, description: str | Sequence[str]
    ) -> list[Value]:
        if isinstance(value_provider, Value):
            return [value_provider]
        elif isinstance(value_provider, ValueTuple):
            return list(value_provider.values)
        descriptions = (
            [description] * len(value_provider.types)
            if isinstance(description, str)
            else description
        )
        targets: list[Register] = [
            self.new_register(self.next_tmp_name(desc), ir_type, value_provider.source_location)
            for ir_type, desc in zip(value_provider.types, descriptions, strict=True)
        ]
        assign_targets(
            self,
            source=value_provider,
            targets=targets,
            assignment_location=value_provider.source_location,
        )
        return list(targets)

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

    # region IRRegisterContext

    def _next_version(self, name: str) -> int:
        try:
            version = self._versions[name] + 1
        except KeyError:
            version = 1
        self._versions[name] = version
        return version

    @typing.override
    def new_register(
        self, name: str, ir_type: IRType, location: SourceLocation | None
    ) -> ir.Register:
        return ir.Register(
            name=name,
            version=self._next_version(name),
            ir_type=ir_type,
            source_location=location,
        )

    @typing.override
    def next_tmp_name(self, description: str) -> str:
        counter_value = next(self._tmp_counters[description])
        # array prefix ensure uniqueness with other temps
        return f"array{ir.TMP_VAR_INDICATOR}{description}{ir.TMP_VAR_INDICATOR}{counter_value}"

    @typing.override
    def add_assignment(
        self, targets: list[ir.Register], source: ir.ValueProvider, loc: SourceLocation | None
    ) -> None:
        self.add_op(ir.Assignment(targets=targets, source=source, source_location=loc))

    @typing.override
    def add_op(self, op: ir.Op) -> None:
        self.current_block_ops.append(op)

    # endregion
