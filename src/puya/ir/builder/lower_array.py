import itertools
import typing
from collections import defaultdict
from collections.abc import Iterator, Sequence

import attrs

from puya import log
from puya.avm import AVMType
from puya.errors import CodeError
from puya.ir import models as ir
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import OpFactory, assign_intrinsic_op
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import ArrayType, EncodedTupleType, IRType
from puya.ir.visitor import IRTraverser
from puya.ir.visitor_mutator import IRMutator
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def lower_array_nodes(subroutine: ir.Subroutine) -> bool:
    existing_versions = VersionGatherer.gather(subroutine)
    replacer = ArrayNodeReplacer(versions=existing_versions)
    for block in subroutine.body:
        replacer.visit_block(block)
    return replacer.modified


@attrs.define
class VersionGatherer(IRTraverser):
    versions: dict[str, int] = attrs.field(factory=dict)

    @classmethod
    def gather(cls, sub: ir.Subroutine) -> dict[str, int]:
        visitor = cls()
        visitor.visit_all_blocks(sub.body)
        return visitor.versions

    def visit_register(self, reg: ir.Register) -> None:
        self.versions[reg.name] = max(self.versions.get(reg.name, 0), reg.version)


@attrs.define(kw_only=True)
class ArrayNodeReplacer(IRMutator, IRRegisterContext):
    _versions: dict[str, int]
    modified: bool = False
    _tmp_counters: defaultdict[str, Iterator[int]] = attrs.field(
        factory=lambda: defaultdict(itertools.count)
    )

    @typing.override
    def visit_array_read_index(self, read: ir.ArrayReadIndex) -> ir.ValueProvider:
        self.modified = True
        values = self._read_item(
            read.array, read.index, _get_element_type(read.array), read.source_location
        )
        value: ir.ValueProvider
        try:
            (value,) = values
        except ValueError:
            value = ir.ValueTuple(values=values, source_location=read.source_location)
        return value

    @typing.override
    def visit_array_write_index(self, write: ir.ArrayWriteIndex) -> ir.Value:
        self.modified = True
        element_type = _get_element_type(write.array)
        element_size = _get_element_size(element_type, write.source_location)

        factory = OpFactory(self, write.source_location)
        bytes_index = factory.mul(write.index, element_size, "bytes_index")
        item_bytes = encode_array_item(self, write.value, element_type, write.source_location)
        return factory.replace(write.array, bytes_index, item_bytes, "updated_array")

    @typing.override
    def visit_array_pop(self, pop: ir.ArrayPop) -> ir.ValueTuple:
        self.modified = True
        element_type = _get_element_type(pop.array)
        element_size = _get_element_size(element_type, pop.source_location)

        factory = OpFactory(self, pop.source_location)
        array_length = factory.len(pop.array, "array_length")
        new_length = factory.sub(array_length, element_size, "new_length")
        array_contents = factory.extract3(
            pop.array,
            0,
            new_length,
            "array_contents",
        )
        item = self._read_item(pop.array, new_length, element_type, pop.source_location)
        return ir.ValueTuple(values=(array_contents, *item), source_location=pop.source_location)

    @typing.override
    def visit_array_extend(self, append: ir.ArrayExtend) -> ir.Register:
        self.modified = True
        factory = OpFactory(self, append.source_location)
        array_contents = factory.concat(
            append.array,
            append.values,
            "array_contents",
            error_message="max array length exceeded",
        )
        return array_contents

    @typing.override
    def visit_array_length(self, length: ir.ArrayLength) -> ir.Register:
        self.modified = True
        bytes_len = assign_intrinsic_op(
            self,
            target="bytes_len",
            op=AVMOp.len_,
            args=[length.array],
            source_location=length.source_location,
        )
        element_type = _get_element_type(length.array)
        element_size = _get_element_size(element_type, length.source_location)
        array_len = assign_intrinsic_op(
            self,
            target="array_len",
            op=AVMOp.div_floor,
            args=[bytes_len, element_size],
            source_location=length.source_location,
        )
        return array_len

    def _read_item(
        self,
        array: ir.Value,
        index: ir.Value,
        element_type: IRType,
        loc: SourceLocation | None,
    ) -> Sequence[ir.Value]:
        factory = OpFactory(self, loc)
        element_size = _get_element_size(element_type, loc)
        bytes_index = factory.mul(index, element_size, "bytes_index")
        item_bytes = factory.extract3(array, bytes_index, element_size, "value")
        return decode_array_item(self, item_bytes, element_type, loc)

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


def _get_element_type(value: ir.Value) -> IRType:
    assert isinstance(value.ir_type, ArrayType), "expected array"
    return value.ir_type.element


def _get_element_size(element_type: IRType, loc: SourceLocation | None) -> int:
    if element_type.size is None:
        raise CodeError("only immutable fixed sized elements supported", loc)
    return element_type.size


def encode_array_item(
    context: IRRegisterContext,
    item: ir.Value | ir.ValueTuple,
    element_type: IRType,
    loc: SourceLocation | None,
) -> ir.Value:
    factory = OpFactory(context, loc)
    values = [item] if isinstance(item, ir.Value) else item.values
    # encoded items are essentially an array of size 1, so use that as the base type
    array_type = ArrayType(element=element_type)
    encoded = factory.constant(b"", ir_type=array_type)
    for value, sub_type in zip(values, EncodedTupleType.expand_types(element_type), strict=True):
        if sub_type.avm_type == AVMType.uint64:
            value = factory.itob(value, "sub_item")
            if sub_type.size != 8:
                assert sub_type.size is not None, "expected fixed type"
                value = factory.extract3(
                    value, 8 - sub_type.size, sub_type.size, "sub_item_truncated"
                )
        encoded = factory.concat(encoded, value, "encoded", ir_type=array_type)
    return encoded


def decode_array_item(
    context: IRRegisterContext,
    item_bytes: ir.Value,
    element_type: IRType,
    loc: SourceLocation | None,
) -> Sequence[ir.Value]:
    factory = OpFactory(context, loc)
    offset = 0
    values = []
    for sub_type in EncodedTupleType.expand_types(element_type):
        sub_type_size = _get_element_size(sub_type, loc)
        sub_item = factory.extract3(item_bytes, offset, sub_type_size, "sub_item")
        if sub_type.avm_type == AVMType.uint64:
            sub_item = factory.btoi(sub_item, "sub_item")
        values.append(sub_item)
        offset += sub_type_size
    return values
