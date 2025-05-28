import itertools
import typing
from collections import defaultdict
from collections.abc import Iterator, Mapping, Sequence

import attrs

from puya import log
from puya.ir import (
    models,
    models as ir,
)
from puya.ir._puya_lib import PuyaLibIR
from puya.ir.builder._utils import OpFactory, assign_targets
from puya.ir.builder.aggregates import arc4_codecs, sequence, tup
from puya.ir.encodings import Encoding, TupleEncoding
from puya.ir.models import Register, Subroutine, Value, ValueProvider, ValueTuple
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import IRType
from puya.ir.visitor import IRTraverser
from puya.ir.visitor_mutator import IRMutator
from puya.parse import SourceLocation

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

        loc = read.source_location

        builder = sequence.get_builder(
            self,
            array_encoding=read.array_encoding,
            assert_bounds=read.check_bounds,
            loc=loc,
        )
        return builder.read_at_index(read.array, read.index)

    @typing.override
    def visit_array_write_index(self, write: ir.ArrayWriteIndex) -> ir.Value:
        self.modified = True

        loc = write.source_location

        builder = sequence.get_builder(
            self,
            array_encoding=write.array_encoding,
            loc=loc,
        )
        return builder.write_at_index(write.array, write.index, write.value)

    @typing.override
    def visit_tuple_read_index(self, read: ir.TupleReadIndex) -> ir.Value:
        self.modified = True

        loc = read.source_location

        tuple_encoding: Encoding = read.tuple_encoding
        base = read.base
        # TODO: for fixed sized types handle read.indexes as a single op using an offset and length
        for index in read.indexes:
            assert isinstance(tuple_encoding, TupleEncoding), "expected TupleEncoding"
            base = tup.read_at_index(
                self,
                tuple_encoding,
                base,
                index,
                loc,
            )
            tuple_encoding = tuple_encoding.elements[index]

        return base

    @typing.override
    def visit_tuple_write_index(self, write: ir.TupleWriteIndex) -> ir.Value:
        self.modified = True

        loc = write.source_location
        try:
            (index,) = write.indexes
        except ValueError:
            raise NotImplementedError("multi-index writes") from None

        return tup.write_at_index(
            self,
            write.tuple_encoding,
            write.base,
            index,
            write.value,
            loc,
        )

    @typing.override
    def visit_array_concat(self, append: ir.ArrayConcat) -> ir.Register:
        self.modified = True
        factory = OpFactory(self, append.source_location)
        array_contents = factory.concat(
            append.array,
            append.other,
            "array_contents",
            error_message="max array length exceeded",
        )
        return array_contents

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
