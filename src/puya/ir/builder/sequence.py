import abc
from functools import cached_property

from puya import log
from puya.awst import wtypes
from puya.errors import CodeError, InternalError
from puya.ir import models as ir
from puya.ir.avm_ops import AVMOp
from puya.ir.builder._utils import OpFactory, assert_value, invoke_puya_lib_subroutine
from puya.ir.builder.arrays import ArrayIterator
from puya.ir.encodings import (
    ArrayEncoding,
    BoolEncoding,
    DynamicArrayEncoding,
    Encoding,
    FixedArrayEncoding,
    wtype_to_encoding,
)
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import (
    EncodedType,
    IRType,
    PrimitiveIRType,
    SlotType,
    TupleIRType,
    type_has_encoding,
    wtype_to_ir_type,
)
from puya.parse import SourceLocation

logger = log.get_logger(__name__)
# TODO: remove this
# ruff: noqa: ARG002


class SequenceBuilder(abc.ABC):
    """
    Builder interface for sequence operations for arrays, tuples and bytes
    """

    # TODO: add slice abstraction here too?

    @abc.abstractmethod
    def read_at_index(self, array: ir.Value, index: ir.Value) -> ir.ValueProvider:
        """Reads the value from the specified index and performs any decoding required"""

    @abc.abstractmethod
    def write_at_index(
        self, array: ir.Value, index: ir.Value, value: ir.ValueProvider
    ) -> ir.ValueProvider:
        """Encodes the value and writes to the specified index and returns the updated result"""

    @abc.abstractmethod
    def length(self, array: ir.Value) -> ir.ValueProvider:
        """Returns the number of elements"""

    @abc.abstractmethod
    def iterator(self, array: ir.Value) -> ArrayIterator:
        """Returns an iterator for all the items"""


def get_builder(
    context: IRRegisterContext,
    wtype: wtypes.WType,
    loc: SourceLocation,
    *,
    assert_bounds: bool = True,
) -> SequenceBuilder:
    if isinstance(wtype, wtypes.BytesWType):
        return BytesIndexableBuilder(context, loc)
    elif isinstance(wtype, wtypes.NativeArray | wtypes.ARC4Array):
        array_ir_type = wtype_to_ir_type(wtype, source_location=loc)
        element_ir_type = wtype_to_ir_type(
            wtype.element_type, source_location=loc, allow_tuple=True
        )
        array_encoding = wtype_to_encoding(wtype, loc)
        builder_typ: type[_ArrayBuilderImpl] | None = None
        match array_encoding:
            # BitPackedBool is a more specific match than FixedElement so do that first
            case DynamicArrayEncoding(element=BoolEncoding(packed=True), length_header=True):
                builder_typ = BitPackedBoolArrayBuilder
            case FixedArrayEncoding(element=BoolEncoding(packed=True)):
                builder_typ = BitPackedBoolArrayBuilder
            case ArrayEncoding(element=Encoding(is_dynamic=False)):
                builder_typ = FixedElementArrayBuilder
            case ArrayEncoding(element=Encoding(is_dynamic=True)):
                builder_typ = DynamicElementArrayBuilder
                # TODO: maybe split DynamicElementArrayBuilder into two builders
                # TODO: maybe ByteLengthHeaderElementArrayBuilder
        if builder_typ is not None:
            return builder_typ(
                context,
                array_ir_type=array_ir_type,
                array_encoding=array_encoding,
                element_ir_type=element_ir_type,
                assert_bounds=assert_bounds,
                loc=loc,
            )
    raise InternalError(f"unsupported array type: {wtype!s}", loc)


# region implementations


class _ArrayBuilderImpl(SequenceBuilder, abc.ABC):
    def __init__(
        self,
        context: IRRegisterContext,
        *,
        array_ir_type: IRType,
        array_encoding: ArrayEncoding,
        element_ir_type: IRType | TupleIRType,
        assert_bounds: bool,
        loc: SourceLocation,
    ) -> None:
        self.context = context
        self.array_ir_type = array_ir_type
        self.array_encoding = array_encoding
        self.element_ir_type = element_ir_type
        self.assert_bounds = assert_bounds
        self.loc = loc
        self.factory = OpFactory(context, loc)

    def iterator(self, array: ir.Value) -> ArrayIterator:
        length_vp = self.length(array)
        length = self.factory.materialise_single(length_vp, "array_length")
        return ArrayIterator(
            array_length=length, get_value_at_index=lambda index: self.read_at_index(array, index)
        )

    def length(self, array: ir.Value) -> ir.ValueProvider:
        return ir.ArrayLength(
            array=array,
            array_encoding=self.array_encoding,
            source_location=self.loc,
        )

    def _maybe_decode(self, encoded_item: ir.ValueProvider) -> ir.ValueProvider:
        if type_has_encoding(self.element_ir_type, self.array_encoding.element):
            return encoded_item
        else:
            encoded_item = self.factory.materialise_single(encoded_item, "encoded_item")
            return ir.ValueDecode(
                value=encoded_item,
                encoding=self.array_encoding.element,
                decoded_type=self.element_ir_type,
                source_location=self.loc,
            )

    def _maybe_encode(self, value: ir.ValueProvider) -> ir.ValueProvider:
        if type_has_encoding(self.element_ir_type, self.array_encoding.element):
            return value
        else:
            return ir.ValueEncode(
                values=self.factory.materialise_values(value),
                encoding=self.array_encoding.element,
                value_type=self.element_ir_type,
                source_location=self.loc,
            )

    def _maybe_bounds_check(self, array: ir.Value, index: ir.Value) -> None:
        if not self.assert_bounds:
            return
        # don't need to check bounds for slot-backed arrays since an invalid index will
        # be out of bounds of the underlying bytes, and any nested elements will be extracted
        # first and checked separately
        if isinstance(self.array_ir_type, SlotType):
            return
        if (
            isinstance(index, ir.UInt64Constant)
            and self.array_encoding.size is not None
            and index.value >= self.array_encoding.size
        ):
            logger.error("index access is out of bounds", location=self.loc)

        array_length = self.factory.materialise_single(self.length(array), "array_length")
        index_is_in_bounds = self.factory.lt(index, array_length)
        assert_value(
            self.context,
            index_is_in_bounds,
            error_message="index access is out of bounds",
            source_location=self.loc,
        )


class BitPackedBoolArrayBuilder(_ArrayBuilderImpl):
    def read_at_index(self, array: ir.Value, index: ir.Value) -> ir.ValueProvider:
        # this catches the edge case of bit arrays that are not a multiple of 8
        # e.g. reading index 6 & 7 of an array that has a length of 6
        self._maybe_bounds_check(array, index)

        if self.array_encoding.length_header:
            # TODO: consider incrementing index by 16 instead
            array = self.factory.extract_to_end(array, 2, "array_trimmed")
        # index is the bit position
        item = self.factory.materialise_single(
            ir.Intrinsic(
                op=AVMOp.getbit,
                args=[array, index],
                types=[PrimitiveIRType.bool],
                source_location=self.loc,
            ),
            "is_true",
        )
        # bit packed bools are unique in that the retrieved value is a bool
        # and depending on the element_ir_type may require encoding
        if isinstance(self.element_ir_type, EncodedType):
            return ir.ValueEncode(
                values=[item],
                value_type=item.ir_type,
                encoding=self.element_ir_type.encoding,
                source_location=self.loc,
            )
        else:
            return item

    def write_at_index(
        self, array: ir.Value, index: ir.Value, value: ir.ValueProvider
    ) -> ir.ValueProvider:
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
        if isinstance(self.element_ir_type, EncodedType):
            is_true = self.factory.get_bit(is_true, 0, "is_true")
        return self.factory.set_bit(
            value=array,
            index=write_offset,
            bit=is_true,
            temp_desc="updated_target",
        )


class FixedElementArrayBuilder(_ArrayBuilderImpl):
    def read_at_index(self, array: ir.Value, index: ir.Value) -> ir.ValueProvider:
        # TODO: is it safe to not bounds check on fixed element arrays?
        #       in some cases yes, e.g. after an extract of the whole array
        #       but in other cases no, e.g. txn arguments
        #       perhaps we could assert the array len once and then trust the size after that?
        # self._maybe_bounds_check(array, index)
        if self.array_encoding.length_header:
            # note: this could also be achieved by incrementing the offset by 2
            #       the current approach uses more space but less ops
            array = self.factory.extract_to_end(array, 2, "array_trimmed")
        element_num_bytes = self.array_encoding.element.checked_num_bytes
        offset = self.factory.mul(index, element_num_bytes, "bytes_offset")
        encoded_element = self.factory.extract3(
            array,
            offset,
            element_num_bytes,
            "encoded_element",
            error_message="index access is out of bounds",
        )
        return self._maybe_decode(encoded_element)

    def write_at_index(
        self, array: ir.Value, index: ir.Value, value: ir.ValueProvider
    ) -> ir.ValueProvider:
        encoded = self._maybe_encode(value)
        encoded = self.factory.materialise_single(encoded, "encoded_value")

        # TODO: is it safe to not bounds check on fixed element arrays?
        # self._maybe_bounds_check(array, index)

        element_encoding = self.array_encoding.element

        write_offset = self.factory.mul(index, element_encoding.checked_num_bytes, "write_offset")
        if self.array_encoding.length_header:
            write_offset = self.factory.add(write_offset, 2, "write_offset_with_length_header")

        array = self.factory.replace(array, write_offset, encoded, "updated_array")
        return array


class DynamicElementArrayBuilder(_ArrayBuilderImpl):
    @cached_property
    def inner_element_size(self) -> int | None:
        element_encoding = self.array_encoding.element
        if not isinstance(element_encoding, ArrayEncoding) or element_encoding.element.is_dynamic:
            return None
        else:
            return element_encoding.element.checked_num_bytes

    def read_at_index(self, array: ir.Value, index: ir.Value) -> ir.ValueProvider:
        array_head_and_tail = array
        if self.array_encoding.length_header:
            array_head_and_tail = self.factory.extract_to_end(array, 2, "array_head_and_tail")
        if self.inner_element_size is not None:
            self._maybe_bounds_check(array, index)
            item = self._read_item_from_array_length_and_fixed_size(array_head_and_tail, index)
        else:
            # no _assert_index_in_bounds here as end offset calculation implicitly checks
            item = self._read_item_using_next_offset(
                array_length_vp=self.length(array),
                array_head_and_tail=array_head_and_tail,
                index=index,
            )
        return self._maybe_decode(item)

    def _read_item_from_array_length_and_fixed_size(
        self, array_head_and_tail: ir.Value, index: ir.Value
    ) -> ir.ValueProvider:
        """ "
        Reads an item that has a dynamic size computable from a length and known inner element size
        e.g. len+<inner_element_size>[]
        """
        assert self.inner_element_size is not None
        item_offset_offset = self.factory.mul(index, 2, "item_offset_offset")
        item_start_offset = self.factory.extract_uint16(
            array_head_and_tail, item_offset_offset, "item_offset"
        )
        item_length = self.factory.extract_uint16(
            array_head_and_tail, item_start_offset, "item_length"
        )
        item_length_in_bytes = self.factory.mul(
            item_length, self.inner_element_size, "item_length_in_bytes"
        )
        item_total_length = self.factory.add(item_length_in_bytes, 2, "item_head_tail_length")
        return self.factory.extract3(
            array_head_and_tail, item_start_offset, item_total_length, "item"
        )

    def _read_item_using_next_offset(
        self,
        array_head_and_tail: ir.Value,
        array_length_vp: ir.ValueProvider,
        index: ir.Value,
    ) -> ir.ValueProvider:
        """ "
        Reads an item by using its offset and the next items offset
        """
        item_offset_offset = self.factory.mul(index, 2, "item_offset_offset")
        item_start_offset = self.factory.extract_uint16(
            array_head_and_tail, item_offset_offset, "item_offset"
        )

        array_length = self.factory.materialise_single(array_length_vp, "array_length")
        next_item_index = self.factory.add(index, 1, "next_index")
        # three possible outcomes of this op will determine the end offset
        # next_item_index < array_length -> has_next is true, use next_item_offset
        # next_item_index == array_length -> has_next is false, use array_length
        # next_item_index > array_length -> op will fail, comment provides context to error
        has_next = self.factory.materialise_single(
            ir.Intrinsic(
                op=AVMOp.sub,
                args=[array_length, next_item_index],
                source_location=self.factory.source_location,
                error_message="index access is out of bounds",
            ),
            "has_next",
        )
        end_of_array = self.factory.len(array_head_and_tail, "end_of_array")
        next_item_offset_offset = self.factory.mul(next_item_index, 2, "next_item_offset_offset")
        # next_item_offset_offset will be past the array head when has_next is false,
        # but this is ok as the value will not be used.
        # Additionally, next_item_offset_offset will always be a valid offset of the overall array
        # This is because there will be at least 1 element (see has_next comments)
        # and this element will have at least one u16 due to being dynamically sized
        # e.g. reading here...   has at least one u16 ........
        #                    v                               v
        # ArrayHead(u16, u16) ArrayTail(DynamicItemHead(... u16, ...), ..., DynamicItemTail, ...)
        next_item_offset = self.factory.extract_uint16(
            array_head_and_tail, next_item_offset_offset, "next_item_offset"
        )

        item_end_offset = self.factory.select(
            false=end_of_array,
            true=next_item_offset,
            condition=has_next,
            temp_desc="end_offset",
            ir_type=PrimitiveIRType.uint64,
        )
        return self.factory.substring3(array_head_and_tail, item_start_offset, item_end_offset)

    def write_at_index(
        self, array: ir.Value, index: ir.Value, value: ir.ValueProvider
    ) -> ir.ValueProvider:
        self._maybe_bounds_check(array, index)

        value = self._maybe_encode(value)
        value = self.factory.materialise_single(value, "encoded_value")

        element_encoding = self.array_encoding.element
        assert element_encoding.is_dynamic

        if self.array_encoding.size is not None:
            array_type = "static"
            args: list[ir.Value | int] = [array, value, index, self.array_encoding.size]
        else:
            array_type = "dynamic"
            args = [array, value, index]
        if (
            isinstance(element_encoding, ArrayEncoding)
            and element_encoding.length_header
            and element_encoding.element.num_bytes == 1
        ):
            # elements where their length header is also their size in bytes
            # e.g. string, byte[], uint8[]
            element_type = "byte_length_head"
        else:
            element_type = "dynamic_element"
        full_name = f"_puya_lib.arc4.{array_type}_array_replace_{element_type}"
        invoke = invoke_puya_lib_subroutine(
            self.context,
            full_name=full_name,
            args=args,
            source_location=self.loc,
        )
        return self.factory.materialise_single(invoke, "updated_array")


class BytesIndexableBuilder(SequenceBuilder):
    def __init__(self, context: IRRegisterContext, loc: SourceLocation) -> None:
        self.loc = loc
        self.factory = OpFactory(context, loc)

    def read_at_index(self, array: ir.Value, index: ir.Value | int) -> ir.ValueProvider:
        return self.factory.extract3(
            array, index, 1, "read_bytes", error_message="Index access is out of bounds"
        )

    def write_at_index(
        self, array: ir.Value, index: ir.Value | int, value: ir.ValueProvider
    ) -> ir.ValueProvider:
        self._immutable()
        return ir.Undefined(ir_type=array.ir_type, source_location=self.loc)

    def iterator(self, array: ir.Value) -> ArrayIterator:
        return ArrayIterator(
            array_length=self.length(array),
            get_value_at_index=lambda index: self.factory.extract3(array, index, 1),
        )

    def length(self, array: ir.Value) -> ir.Value:
        return self.factory.len(array, "bytes_length")

    def _immutable(self) -> None:
        raise CodeError("bytes array is immutable", location=self.loc)


# end region


def _is_fixed_element(encoding: Encoding) -> bool:
    return not encoding.is_dynamic and (
        not isinstance(encoding, BoolEncoding) or not encoding.packed
    )


def _todo(msg: str, loc: SourceLocation | None) -> None:
    logger.warning(msg, location=loc)
