import abc
import typing

import attrs

from puya import log
from puya.avm import AVMType
from puya.errors import InternalError
from puya.ir import (
    models as ir,
    types_ as types,
)
from puya.ir._puya_lib import PuyaLibIR
from puya.ir.builder import mem
from puya.ir.builder._utils import invoke_puya_lib_subroutine
from puya.ir.encodings import ArrayEncoding
from puya.ir.op_utils import OpFactory, assert_value
from puya.ir.register_context import IRRegisterContext
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def read_at_index(
    context: IRRegisterContext,
    array_encoding: ArrayEncoding,
    array: ir.Value,
    index: ir.Value,
    loc: SourceLocation | None,
    *,
    assert_bounds: bool | None = None,
) -> ir.Value:
    builder = _get_builder(context, array_encoding, loc, assert_bounds=assert_bounds)
    return builder.read_at_index(array, index)


def write_at_index(
    context: IRRegisterContext,
    array_encoding: ArrayEncoding,
    array: ir.Value,
    index: ir.Value,
    value: ir.Value,
    loc: SourceLocation | None,
    *,
    assert_bounds: bool | None = None,
) -> ir.Value:
    builder = _get_builder(context, array_encoding, loc, assert_bounds=assert_bounds)
    return builder.write_at_index(array, index, value)


def get_length(
    context: IRRegisterContext,
    array_encoding: ArrayEncoding,
    array_or_slot: ir.Value,
    loc: SourceLocation | None,
) -> ir.Value:
    if isinstance(array_or_slot.ir_type, types.SlotType):
        array = mem.read_slot(context, array_or_slot, loc)
    else:
        array = array_or_slot
    # how length is calculated depends on the array type, rather than the element type
    factory = OpFactory(context, loc)
    if array_encoding.size is not None:
        return factory.constant(array_encoding.size)
    elif array_encoding.length_header:
        return factory.extract_uint16(array, 0, "array_length")
    assert array_encoding.size is None, "expected dynamic array"
    bytes_len = factory.len(array, "bytes_len")
    return factory.div_floor(bytes_len, array_encoding.element.checked_num_bytes, "array_len")


class _SequenceBuilder(abc.ABC):
    """
    Builder interface for sequence operations for arrays, tuples and bytes
    """

    # TODO: add slice abstraction here too?

    @abc.abstractmethod
    def read_at_index(self, array: ir.Value, index: ir.Value) -> ir.Value:
        """Reads the value from the specified index and performs any decoding required"""

    @abc.abstractmethod
    def write_at_index(self, array: ir.Value, index: ir.Value, value: ir.Value) -> ir.Value:
        """Encodes the value and writes to the specified index and returns the updated result"""


def _get_builder(
    context: IRRegisterContext,
    array_encoding: ArrayEncoding,
    loc: SourceLocation | None,
    *,
    assert_bounds: bool | None,
) -> _SequenceBuilder:
    builder_typ: type[_ArrayBuilderImpl]

    if assert_bounds is None:
        # dynamic elements or bit-packed elements could access invalid indexes
        # fixed sized elements don't have this issue as the underling bytes won't be big enough
        # if an invalid index is used
        # note: this assumption may no longer hold if reading nested aggregates
        assert_bounds = array_encoding.element.is_dynamic or array_encoding.element.is_bit

    if array_encoding.element.is_bit:
        # BitPackedBool is a more specific match than FixedElement so do that first
        if array_encoding.size is None and not array_encoding.length_header:
            raise InternalError("unsupported scenario: bit packed bools in reference array", loc)
        builder_typ = _BitPackedBoolArrayBuilder
    elif array_encoding.element.is_dynamic:
        builder_typ = _DynamicElementArrayBuilder
    else:
        builder_typ = _FixedElementArrayBuilder
    return builder_typ(
        context,
        array_encoding=array_encoding,
        assert_bounds=assert_bounds,
        loc=loc,
    )


@attrs.define
class _ArrayBuilderImpl(_SequenceBuilder, abc.ABC):
    context: IRRegisterContext
    array_encoding: ArrayEncoding
    assert_bounds: bool
    loc: SourceLocation | None
    factory: OpFactory = attrs.field(init=False)

    @factory.default
    def _factory_factory(self) -> OpFactory:
        return OpFactory(self.context, self.loc)

    @typing.final
    def _maybe_bounds_check(self, array: ir.Value, index: ir.Value) -> None:
        if not self.assert_bounds:
            return
        if (
            isinstance(index, ir.UInt64Constant)
            and self.array_encoding.size is not None
            and index.value >= self.array_encoding.size
        ):
            logger.error("index access is out of bounds", location=self.loc)

        array_length = self._length(array)
        index_is_in_bounds = self.factory.lt(index, array_length)
        assert_value(
            self.context,
            index_is_in_bounds,
            error_message="index access is out of bounds",
            source_location=self.loc,
        )

    @typing.final
    def _length(self, array: ir.Value) -> ir.Value:
        return get_length(self.context, self.array_encoding, array, self.loc)


class _BitPackedBoolArrayBuilder(_ArrayBuilderImpl):
    @typing.override
    def read_at_index(self, array: ir.Value, index: ir.Value) -> ir.Value:
        # this catches the edge case of bit arrays that are not a multiple of 8
        # e.g. reading index 6 & 7 of an array that has a length of 6
        self._maybe_bounds_check(array, index)

        # index is the bit position
        if self.array_encoding.length_header:
            index = self.factory.add(index, 16)
        return self.factory.get_bit(array, index)

    @typing.override
    def write_at_index(self, array: ir.Value, index: ir.Value, value: ir.Value) -> ir.Value:
        # this catches the edge case of bit arrays that are not a multiple of 8
        # e.g. reading index 6 & 7 of an array that has a length of 6
        self._maybe_bounds_check(array, index)

        element_encoding = self.array_encoding.element
        assert element_encoding.num_bits == 1, "expected bit packed bool"

        if not self.array_encoding.length_header:
            write_offset = index
        else:
            write_offset = self.factory.add(index, 16, "write_offset_with_length_header")

        is_true = self.factory.materialise_single(value, "is_true")
        assert is_true.atype == AVMType.uint64, "expected bool value"
        return self.factory.set_bit(
            value=array,
            index=write_offset,
            bit=is_true,
            temp_desc="updated_target",
        )


class _FixedElementArrayBuilder(_ArrayBuilderImpl):
    @typing.override
    def read_at_index(self, array: ir.Value, index: ir.Value) -> ir.Value:
        if self.array_encoding.length_header:
            # note: this could also be achieved by incrementing the offset by 2
            #       the current approach uses more space but less ops
            array = self.factory.extract_to_end(array, 2, "array_trimmed")
        element_num_bytes = self.array_encoding.element.checked_num_bytes
        offset = self.factory.mul(index, element_num_bytes, "bytes_offset")
        return self.factory.extract3(
            array,
            offset,
            element_num_bytes,
            "encoded_element",
            error_message="index access is out of bounds",
        )

    @typing.override
    def write_at_index(self, array: ir.Value, index: ir.Value, value: ir.Value) -> ir.Value:
        element_encoding = self.array_encoding.element

        write_offset = self.factory.mul(index, element_encoding.checked_num_bytes, "write_offset")
        if self.array_encoding.length_header:
            write_offset = self.factory.add(write_offset, 2, "write_offset_with_length_header")

        array = self.factory.replace(
            array,
            write_offset,
            value,
            "updated_array",
            error_message="index access is out of bounds",
        )
        return array


@attrs.define
class _DynamicElementArrayBuilder(_ArrayBuilderImpl):
    inner_element_size: int | None = attrs.field(init=False)

    @inner_element_size.default
    def _inner_element_size_factory(self) -> int | None:
        element_encoding = self.array_encoding.element
        assert element_encoding.is_dynamic
        if isinstance(element_encoding, ArrayEncoding):
            return element_encoding.element.num_bytes
        else:
            return None

    @typing.override
    def read_at_index(self, array: ir.Value, index: ir.Value) -> ir.Value:
        array_head_and_tail = array
        if self.array_encoding.length_header:
            array_head_and_tail = self.factory.extract_to_end(array, 2, "array_head_and_tail")
        # TODO: maybe split DynamicElementArrayBuilder into two builders
        if self.inner_element_size is not None:
            self._maybe_bounds_check(array, index)
            item = self._read_item_from_array_length_and_fixed_size(
                self.factory, self.inner_element_size, array_head_and_tail, index
            )
        else:
            # no _assert_index_in_bounds here as end offset calculation implicitly checks
            length = self._length(array)
            item = self._read_item_using_next_offset(
                self.factory,
                array_length=length,
                array_head_and_tail=array_head_and_tail,
                index=index,
            )
        return self.factory.materialise_single(item)

    @staticmethod
    def _read_item_from_array_length_and_fixed_size(
        factory: OpFactory, inner_element_size: int, array_head_and_tail: ir.Value, index: ir.Value
    ) -> ir.ValueProvider:
        """ "
        Reads an item that has a dynamic size computable from a length and known inner element size
        e.g. len+<inner_element_size>[]
        """
        item_offset_offset = factory.mul(index, 2, "item_offset_offset")
        item_start_offset = factory.extract_uint16(
            array_head_and_tail, item_offset_offset, "item_offset"
        )
        item_length = factory.extract_uint16(array_head_and_tail, item_start_offset, "item_length")
        item_length_in_bytes = factory.mul(item_length, inner_element_size, "item_length_in_bytes")
        item_total_length = factory.add(item_length_in_bytes, 2, "item_head_tail_length")
        return factory.extract3(array_head_and_tail, item_start_offset, item_total_length, "item")

    @staticmethod
    def _read_item_using_next_offset(
        factory: OpFactory,
        array_head_and_tail: ir.Value,
        array_length: ir.Value,
        index: ir.Value,
    ) -> ir.ValueProvider:
        """ "
        Reads an item by using its offset and the next items offset
        """
        item_offset_offset = factory.mul(index, 2, "item_offset_offset")
        item_start_offset = factory.extract_uint16(
            array_head_and_tail, item_offset_offset, "item_offset"
        )

        next_item_index = factory.add(index, 1, "next_index")
        # three possible outcomes of this op will determine the end offset
        # next_item_index < array_length -> has_next is true, use next_item_offset
        # next_item_index == array_length -> has_next is false, use array_length
        # next_item_index > array_length -> op will fail, comment provides context to error
        has_next = factory.sub(
            array_length,
            next_item_index,
            "has_next",
            error_message="index access is out of bounds",
        )
        end_of_array = factory.len(array_head_and_tail, "end_of_array")
        next_item_offset_offset = factory.mul(next_item_index, 2, "next_item_offset_offset")
        # next_item_offset_offset will be past the array head when has_next is false,
        # but this is ok as the value will not be used.
        # Additionally, next_item_offset_offset will always be a valid offset of the overall array
        # This is because there will be at least 1 element (see has_next comments)
        # and this element will have at least one u16 due to being dynamically sized
        # e.g. reading here...   has at least one u16 ........
        #                    v                               v
        # ArrayHead(u16, u16) ArrayTail(DynamicItemHead(... u16, ...), ..., DynamicItemTail, ...)
        next_item_offset = factory.extract_uint16(
            array_head_and_tail, next_item_offset_offset, "next_item_offset"
        )

        item_end_offset = factory.select(
            false=end_of_array,
            true=next_item_offset,
            condition=has_next,
            temp_desc="end_offset",
            ir_type=types.uint64,
        )
        return factory.substring3(array_head_and_tail, item_start_offset, item_end_offset)

    @typing.override
    def write_at_index(self, array: ir.Value, index: ir.Value, value: ir.Value) -> ir.Value:
        self._maybe_bounds_check(array, index)

        if self.array_encoding.size is None:
            array_type = "dynamic"
            args: list[ir.Value | int] = [array, value, index]
        else:
            array_type = "static"
            args = [array, value, index, self.array_encoding.size]

        match self.array_encoding.element:
            case ArrayEncoding(length_header=True, element=element) if element.num_bytes == 1:
                # elements where their length header is also their size in bytes
                # e.g. string, byte[], uint8[]
                element_type = "byte_length_head"
            case _:
                element_type = "dynamic_element"

        target = PuyaLibIR[f"{array_type}_array_replace_{element_type}"]
        invoke = invoke_puya_lib_subroutine(
            self.context, full_name=target, args=args, source_location=self.loc
        )
        return self.factory.materialise_single(invoke, "updated_array")
