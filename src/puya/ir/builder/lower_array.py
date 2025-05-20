import itertools
import typing
from collections import defaultdict
from collections.abc import Iterator

import attrs

from puya import log
from puya.ir import (
    models,
    models as ir,
)
from puya.ir.builder import arc4
from puya.ir.builder._utils import OpFactory
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import (
    DynamicArrayEncoding,
    Encoding,
    FixedArrayEncoding,
    IRType,
)
from puya.ir.visitor import IRTraverser
from puya.ir.visitor_mutator import IRMutator
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def lower_array_nodes(subroutine: ir.Subroutine) -> bool:
    existing_versions = _VersionGatherer.gather(subroutine)
    replacer = _ArrayNodeReplacer(versions=existing_versions)
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
class _ArrayNodeReplacer(IRMutator, IRRegisterContext):
    _versions: dict[str, int]
    modified: bool = False
    _tmp_counters: defaultdict[str, Iterator[int]] = attrs.field(
        factory=lambda: defaultdict(itertools.count)
    )

    @typing.override
    def visit_value_encode(self, encode: models.ValueEncode) -> models.ValueProvider:
        self.modified = True
        if len(encode.values) == 1:
            value_provider: models.ValueTuple | models.Value = encode.values[0]
        else:
            value_provider = models.ValueTuple(
                values=encode.values, source_location=encode.source_location
            )
        return arc4.encode_value_provider(
            self,
            value_provider,
            value_type=encode.value_type,
            encoding=encode.encoding,
            loc=encode.source_location,
        )

    @typing.override
    def visit_value_decode(self, decode: models.ValueDecode) -> models.ValueProvider:
        self.modified = True
        return arc4.decode_arc4_value(
            self,
            decode.value,
            encoding=decode.encoding,
            target_type=decode.decoded_type,
            loc=decode.source_location,
        )

    @typing.override
    def visit_array_read_index(self, read: ir.ArrayReadIndex) -> ir.ValueProvider:
        self.modified = True
        return self._read_item(
            read.array, read.index, read.array_encoding.element, read.source_location
        )

    @typing.override
    def visit_array_write_index(self, write: ir.ArrayWriteIndex) -> ir.Value:
        self.modified = True
        element_encoding = write.array_encoding.element
        element_size = element_encoding.checked_num_bytes

        factory = OpFactory(self, write.source_location)
        bytes_index = factory.mul(write.index, element_size, "bytes_index")
        return factory.replace(write.array, bytes_index, write.value, "updated_array")

    @typing.override
    def visit_array_pop(self, pop: ir.ArrayPop) -> ir.ValueProvider:
        self.modified = True
        element_encoding = pop.array_encoding.element
        element_size = element_encoding.checked_num_bytes

        factory = OpFactory(self, pop.source_location)
        array_bytes_length = factory.len(pop.array, "array_bytes_length")
        array_bytes_new_length = factory.sub(
            array_bytes_length, element_size, "array_bytes_new_length"
        )
        array_new_length = factory.div_floor(
            array_bytes_new_length, element_size, "array_new_length"
        )
        array_contents = factory.extract3(
            pop.array,
            0,
            array_bytes_new_length,
            "array_contents",
        )
        item = self._read_item(pop.array, array_new_length, element_encoding, pop.source_location)
        return ir.ValueTuple(values=(array_contents, item), source_location=pop.source_location)

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

    @typing.override
    def visit_array_length(self, length: ir.ArrayLength) -> ir.Value:
        self.modified = True
        factory = OpFactory(self, length.source_location)
        array_encoding = length.array_encoding
        if isinstance(array_encoding, FixedArrayEncoding):
            return factory.constant(array_encoding.size)
        elif isinstance(array_encoding, DynamicArrayEncoding) and array_encoding.length_header:
            return factory.extract_uint16(length.array, 0, "array_length")
        assert isinstance(array_encoding, DynamicArrayEncoding), "expected dynamic array"
        bytes_len = factory.len(length.array, "bytes_len")
        return factory.div_floor(bytes_len, array_encoding.element.checked_num_bytes, "array_len")

    def _read_item(
        self,
        array: ir.Value,
        index: ir.Value,
        encoding: Encoding,
        loc: SourceLocation | None,
    ) -> ir.Value:
        factory = OpFactory(self, loc)
        element_size = encoding.checked_num_bytes
        bytes_index = factory.mul(index, element_size, "bytes_index")
        item_bytes = factory.extract3(array, bytes_index, element_size, "value")
        return item_bytes

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
