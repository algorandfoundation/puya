import itertools
import typing
from collections import defaultdict
from collections.abc import Iterator, Sequence

import attrs

from puya import log
from puya.avm import AVMType
from puya.errors import CodeError, InternalError
from puya.ir import models as ir
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import OpFactory, assign_intrinsic_op
from puya.ir.builder.arc4 import ARC4_FALSE, ARC4_TRUE
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import (
    ArrayType,
    IRType,
    PrimitiveIRType,
    encoded_ir_type_to_ir_types,
    expand_encoded_type_and_group,
)
from puya.ir.visitor import IRTraverser
from puya.ir.visitor_mutator import IRMutator
from puya.parse import SourceLocation, sequential_source_locations_merge

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
    def visit_array_read_index(self, read: ir.ArrayReadIndex) -> ir.ValueProvider:
        self.modified = True
        values = self._read_item(
            read.array, read.index, read.array_type.element, read.source_location
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
        element_type = write.array_type.element
        element_size = _get_element_size(element_type, write.source_location)

        factory = OpFactory(self, write.source_location)
        bytes_index = factory.mul(write.index, element_size, "bytes_index")
        item_bytes = _encode_array_item(self, write.value, element_type, write.source_location)
        return factory.replace(write.array, bytes_index, item_bytes, "updated_array")

    @typing.override
    def visit_array_pop(self, pop: ir.ArrayPop) -> ir.ValueTuple:
        self.modified = True
        element_type = pop.array_type.element
        element_size = _get_element_size(element_type, pop.source_location)

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
        item = self._read_item(pop.array, array_new_length, element_type, pop.source_location)
        return ir.ValueTuple(values=(array_contents, *item), source_location=pop.source_location)

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
    def visit_array_encode(self, encode: ir.ArrayEncode) -> ir.ArrayEncode | ir.ValueProvider:
        self.modified = True
        return _encode_array_items(self, encode)

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
        element_type = length.array_type.element
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
        return _decode_array_item(self, item_bytes, element_type, loc)

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


def _get_element_size(element_type: IRType, loc: SourceLocation | None) -> int:
    if element_type.num_bytes is None:
        raise CodeError("only immutable, static sized elements supported", loc)
    return element_type.num_bytes


def _encode_array_items(context: IRRegisterContext, encode: ir.ArrayEncode) -> ir.Value:
    factory = OpFactory(context, source_location=encode.source_location)
    values = encode.values
    array_type = encode.array_type
    data = factory.constant(b"", ir_type=array_type)
    element_type = array_type.element
    num_reg_per_element = len(encoded_ir_type_to_ir_types(element_type))
    while len(values) >= num_reg_per_element:
        item_values = values[:num_reg_per_element]
        values = values[num_reg_per_element:]
        item: ir.Value | ir.ValueTuple
        try:
            (item,) = item_values
        except ValueError:
            item = ir.ValueTuple(
                values=item_values,
                source_location=sequential_source_locations_merge(
                    [i.source_location for i in item_values]
                ),
            )
        item_bytes = _encode_array_item(context, item, element_type, item.source_location)
        data = factory.concat(data, item_bytes, "data", ir_type=array_type)
    if values:
        raise InternalError("unexpected number of elements", encode.source_location)
    return data


def _encode_array_item(
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
    last_type_and_group = None
    bit_packed_index = 0
    encoded_length = 0
    for value, (sub_type, tuple_group) in zip(
        values, expand_encoded_type_and_group(element_type), strict=True
    ):
        if sub_type.num_bytes is None:
            raise InternalError("expected fixed size element", loc)
        value_type = value.ir_type
        # bool values are encoded as a single ARC-4 Bool value, i.e. consecutive values are not
        # bit-packed. This allows easier conversion from ReferenceArray encoding to ARC-4 encoding
        # and also means the standard way of calculating array length
        # len(array_bytes) / sizeof(EncodedElementType) continues to work
        if value_type == PrimitiveIRType.bool:
            # sequential bits in the same tuple are bit-packed
            if last_type_and_group == (sub_type, tuple_group):
                bit_packed_index += 1
                bit_index = bit_packed_index % 8
                if bit_index:
                    bit_index += (encoded_length - 1) * 8
                bytes_to_set = encoded if bit_index else ARC4_FALSE
                value = factory.set_bit(
                    value=bytes_to_set, index=bit_index, bit=value, temp_desc="sub_item"
                )
                # if bit_index is not 0, then just update encoded and continue
                # as there is nothing to concat
                if bit_index:
                    encoded = value
                    continue
            else:
                value = factory.select(
                    false=ARC4_FALSE,
                    true=ARC4_TRUE,
                    condition=value,
                    ir_type=PrimitiveIRType.bytes,
                    temp_desc="encoded_bit",
                )
                bit_packed_index = 0
        # uint64 values are encoded to their equivalent bytes
        elif value_type.avm_type == AVMType.uint64:
            value = factory.itob(value, "sub_item")
            if sub_type.num_bytes != 8:
                value = factory.extract3(
                    value, 8 - sub_type.num_bytes, sub_type.num_bytes, "sub_item_truncated"
                )
        # biguint values are first padded to 64 bytes
        elif value_type == PrimitiveIRType.biguint:
            value = factory.to_fixed_size(value, num_bytes=64, temp_desc="sub_item")
        # all other byte values should be the correct size already due to earlier check
        elif value_type.avm_type == AVMType.bytes:
            pass
        else:
            raise InternalError(f"unexpected element type for array encoding: {value_type}", loc)
        encoded_length += sub_type.num_bytes
        last_type_and_group = sub_type, tuple_group
        encoded = factory.concat(encoded, value, "encoded", ir_type=array_type)
    return encoded


def _decode_array_item(
    context: IRRegisterContext,
    item_bytes: ir.Value,
    element_type: IRType,
    loc: SourceLocation | None,
) -> Sequence[ir.Value]:
    factory = OpFactory(context, loc)
    bit_offset = offset = 0
    values = []
    last_sub_typ = None
    for encoded_sub_type, group_id in expand_encoded_type_and_group(element_type):
        # special handling for bit-packed bools in aggregate types
        (sub_type,) = encoded_ir_type_to_ir_types(encoded_sub_type)
        if sub_type == PrimitiveIRType.bool and element_type != PrimitiveIRType.bool:
            if last_sub_typ == (sub_type, group_id):
                bit_offset += 1
            sub_item = factory.get_bit(item_bytes, offset * 8 + bit_offset, "sub_item")
        else:
            sub_type_size = _get_element_size(encoded_sub_type, loc)
            bit_offset = 0
            sub_item = factory.extract3(item_bytes, offset, sub_type_size, "sub_item")
            if sub_type.avm_type == AVMType.uint64:
                sub_item = factory.btoi(sub_item, "sub_item")
            offset += sub_type_size
        # also increment offset if we reach the end of a bit-packed byte
        if bit_offset % 8 == 7:
            bit_offset = 0
            offset += 1
        last_sub_typ = sub_type, group_id
        values.append(sub_item)
    return values
