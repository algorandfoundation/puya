import abc
import typing

from puya import log
from puya.awst import wtypes
from puya.errors import CodeError, InternalError
from puya.ir import models as ir
from puya.ir.builder import mem
from puya.ir.builder._utils import OpFactory
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import (
    ArrayEncoding,
    BoolEncoding,
    DynamicArrayEncoding,
    Encoding,
    FixedArrayEncoding,
    IRType,
    PrimitiveIRType,
    SlotType,
    type_has_encoding,
    wtype_to_encoding,
    wtype_to_ir_type,
    wtype_to_ir_type_and_encoding,
)
from puya.parse import SourceLocation

logger = log.get_logger(__name__)
# TODO: remove this
# ruff: noqa: ARG002


class ArrayBuilder(abc.ABC):
    # TODO: add slice abstraction here too?

    @abc.abstractmethod
    def read_at_index(self, array: ir.Value, index: ir.Value) -> ir.ValueProvider:
        """Reads the value from the specified index and performs any decoding required"""

    @abc.abstractmethod
    def write_at_index(self, array: ir.Value, index: ir.Value, value: ir.ValueProvider) -> None:
        """Encodes the value and writes to the specified index"""

    @abc.abstractmethod
    def length(self, array: ir.Value) -> ir.Value:
        """Returns the number of elements in the array"""


class _ARC4ShimArrayBuilder(ArrayBuilder):
    def __init__(
        self,
        context: IRRegisterContext,
        array_ir_type: IRType,
        array_encoding: ArrayEncoding,
        element_ir_type: IRType,
        loc: SourceLocation,
    ) -> None:
        self.context = context
        self.array_ir_type = array_ir_type
        self.array_encoding = array_encoding
        self.element_ir_type = element_ir_type
        self.loc = loc

    def read_at_index(self, array: ir.Value, index: ir.Value) -> ir.ValueProvider:
        from puya.ir.builder import arc4

        return arc4.arc4_array_index(
            self.context,
            array_encoding=self.array_encoding,
            item_type=self.element_ir_type,
            array=array,
            index=index,
            source_location=self.loc,
        )

    def write_at_index(self, array: ir.Value, index: ir.Value, value: ir.ValueProvider) -> None:
        _todo("ARC-4 shim array read", array.source_location)

    def length(self, array: ir.Value) -> ir.Value:
        _todo("ARC-4 shim array read", array.source_location)


class BitPackedBoolArrayBuilder(ArrayBuilder):
    def __init__(self, array_size: int | None, element_ir_type: IRType) -> None:
        self.array_size = array_size
        self.element_ir_type = element_ir_type
        self.bits_start_at = 16 if array_size is None else 0

    def read_at_index(self, array: ir.Value, index: ir.Value | int) -> ir.ValueProvider:
        _todo("bit packed bool array read", array.source_location)

    def write_at_index(
        self, array: ir.Value, index: ir.Value | int, value: ir.ValueProvider
    ) -> None:
        _todo("bit packed bool array write", array.source_location)

    def length(self, array: ir.Value) -> ir.Value:
        _todo("bit packed bool array length", array.source_location)


class FixedElementArrayBuilder(ArrayBuilder):
    def __init__(
        self,
        context: IRRegisterContext,
        array_ir_type: IRType,
        array_encoding: ArrayEncoding,
        element_ir_type: IRType,
        loc: SourceLocation,
    ) -> None:
        self.factory = OpFactory(context, loc)
        self.loc = loc
        self.array_ir_type = array_ir_type
        self.array_encoding = array_encoding
        self.has_length_header = (
            isinstance(array_encoding, DynamicArrayEncoding) and array_encoding.length_header
        )
        self.element_ir_type = element_ir_type
        self.element_num_bytes = self.array_encoding.element.checked_num_bytes
        # note: at present, slot-backed arrays can only contain fixed elements
        self.array_is_slot_backed = isinstance(array_ir_type, SlotType)
        self.requires_conversion = not type_has_encoding(
            self.element_ir_type, array_encoding.element
        )

    def read_at_index(self, array: ir.Value, index: ir.Value) -> ir.ValueProvider:
        if self.array_is_slot_backed:
            array = mem.read_slot(self.factory.context, array, self.loc)
        if self.has_length_header:
            # note: this could also be achieved by incrementing the offset by 2
            #       the current approach uses more space but less ops
            array = self.factory.extract_to_end(array, 2, "array_trimmed")
        offset = self.factory.mul(index, self.element_num_bytes, "bytes_offset")
        encoded_element = self.factory.extract3(
            array,
            offset,
            self.element_num_bytes,
            "encoded_element",
            error_message="Index access is out of bounds",
        )
        if not self.requires_conversion:
            return encoded_element
        else:
            return ir.ValueDecode(
                value=encoded_element,
                encoding=self.array_encoding.element,
                decoded_type=self.element_ir_type,
                source_location=self.loc,
            )

    def write_at_index(self, array: ir.Value, index: ir.Value, value: ir.ValueProvider) -> None:
        _todo("fixed element array write", self.loc)

    def length(self, array: ir.Value) -> ir.Value:
        _todo("fixed element array length", self.loc)


class DynamicElementArrayBuilder(ArrayBuilder):
    def __init__(self, array_encoding: ArrayEncoding, element_ir_type: IRType) -> None:
        self.array_encoding = array_encoding
        self.element_encoding = array_encoding.element
        self.element_ir_type = element_ir_type

    def read_at_index(self, array: ir.Value, index: ir.Value | int) -> ir.ValueProvider:
        _todo("dynamic element array read", array.source_location)

    def write_at_index(
        self, array: ir.Value, index: ir.Value | int, value: ir.ValueProvider
    ) -> None:
        _todo("dynamic element array write", array.source_location)

    def length(self, array: ir.Value) -> ir.Value:
        _todo("dynamic element array length", array.source_location)


def get_array_builder(
    context: IRRegisterContext, wtype: wtypes.WType, loc: SourceLocation
) -> ArrayBuilder:
    if isinstance(wtype, wtypes.BytesWType):
        return BytesArrayBuilder(context, loc)
    elif isinstance(wtype, wtypes.NativeArray | wtypes.ARC4Array):
        array_ir_type = wtype_to_ir_type(wtype, source_location=loc)
        element_ir_type = wtype_to_ir_type(
            wtype.element_type, source_location=loc, allow_aggregate=True
        )
        array_encoding = wtype_to_encoding(wtype, loc)
        match array_encoding:
            case ArrayEncoding(element=element) if _is_fixed_element(element):
                return FixedElementArrayBuilder(
                    context,
                    array_encoding=array_encoding,
                    element_ir_type=element_ir_type,
                    loc=loc,
                    array_ir_type=array_ir_type,
                )
            case ArrayEncoding():
                return _ARC4ShimArrayBuilder(
                    context,
                    array_encoding=array_encoding,
                    element_ir_type=element_ir_type,
                    loc=loc,
                    array_ir_type=array_ir_type,
                )
            case DynamicArrayEncoding(element=BoolEncoding(packed=True), length_header=True):
                return BitPackedBoolArrayBuilder(None, element_ir_type)
            case FixedArrayEncoding(element=BoolEncoding(packed=True), size=array_size):
                return BitPackedBoolArrayBuilder(array_size, element_ir_type)
            # TODO: maybe ByteLengthHeaderElementArrayBuilder
            case ArrayEncoding(element=element) if element.is_dynamic:
                return DynamicElementArrayBuilder(array_encoding, element_ir_type)
    raise InternalError(f"unsupported array type: {wtype!s}", loc)


# region Dynamic arrays
class DynamicArrayBuilder(abc.ABC):
    @abc.abstractmethod
    def concat(self, array: ir.Value, iterable: ir.ValueProvider) -> ir.Value:
        """Returns the concatenation of an array and iterable"""

    @abc.abstractmethod
    def append(self, array: ir.Value, value: ir.ValueProvider) -> ir.Value:
        """Appends value to the end of the array"""

    @abc.abstractmethod
    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.ValueProvider]:
        """
        Removes the last item of an array

        Returns the updated array and the removed item
        """


class FixedElementDynamicArrayBuilder(DynamicArrayBuilder):
    def concat(self, array: ir.Value, iterable: ir.ValueProvider) -> ir.Value:
        _todo("fixed element array concat", array.source_location)

    def append(self, array: ir.Value, value: ir.ValueProvider) -> ir.Value:
        _todo("fixed element array append", array.source_location)

    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.ValueProvider]:
        _todo("fixed element array pop", array.source_location)


class DynamicElementDynamicArrayBuilder(DynamicArrayBuilder):
    def concat(self, array: ir.Value, iterable: ir.ValueProvider) -> ir.Value:
        _todo("dynamic element array concat", array.source_location)

    def append(self, array: ir.Value, value: ir.ValueProvider) -> ir.Value:
        _todo("dynamic element array append", array.source_location)

    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.ValueProvider]:
        _todo("dynamic element array pop", array.source_location)


class BitPackedBoolDynamicArrayBuilder(DynamicArrayBuilder):
    def concat(self, array: ir.Value, iterable: ir.ValueProvider) -> ir.Value:
        _todo("bit packed bool array concat", array.source_location)

    def append(self, array: ir.Value, value: ir.ValueProvider) -> ir.Value:
        _todo("bit packed bool array append", array.source_location)

    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.ValueProvider]:
        _todo("bit packed bool array pop", array.source_location)


class BytesArrayBuilder(ArrayBuilder, DynamicArrayBuilder):
    def __init__(self, context: IRRegisterContext, loc: SourceLocation) -> None:
        self.loc = loc
        self.factory = OpFactory(context, loc)

    def read_at_index(self, array: ir.Value, index: ir.Value | int) -> ir.ValueProvider:
        return self.factory.extract3(
            array, index, 1, "read_bytes", error_message="Index access is out of bounds"
        )

    def write_at_index(
        self, array: ir.Value, index: ir.Value | int, value: ir.ValueProvider
    ) -> None:
        self._immutable()

    def length(self, array: ir.Value) -> ir.Value:
        return self.factory.len(array, "bytes_length")

    def concat(self, array: ir.Value, iterable: ir.ValueProvider) -> ir.Value:
        other = self.factory.materialise_single(iterable, "other")
        return self.factory.concat(array, other, "bytes_concat")

    def append(self, array: ir.Value, value: ir.ValueProvider) -> ir.Value:
        self._immutable()
        return array

    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.ValueProvider]:
        self._immutable()
        return array, ir.Undefined(ir_type=PrimitiveIRType.bytes, source_location=None)

    def _immutable(self) -> None:
        raise CodeError("bytes array is immutable", location=self.loc)


def get_dynamic_array_builder(
    _context: IRRegisterContext,
    array_type: wtypes.ARC4Array | wtypes.NativeArray,
    loc: SourceLocation,
) -> DynamicArrayBuilder | None:
    element_ir_type, _ = wtype_to_ir_type_and_encoding(array_type.element_type, loc)
    array_ir_type, array_encoding = wtype_to_ir_type_and_encoding(array_type, loc)
    assert isinstance(array_encoding, DynamicArrayEncoding), "expected dynamic array encoding"
    match array_encoding:
        case DynamicArrayEncoding(element=BoolEncoding(packed=True), length_header=length_header):
            if length_header:
                return BitPackedBoolDynamicArrayBuilder()
            else:
                return None  # not supported
        case DynamicArrayEncoding(element=element) if element.is_dynamic:
            return DynamicElementDynamicArrayBuilder()
        case DynamicArrayEncoding(element=element) if not element.is_dynamic:
            return FixedElementDynamicArrayBuilder()
        case _:
            return None


# endregion


def _is_fixed_element(encoding: Encoding) -> bool:
    return not encoding.is_dynamic and (
        not isinstance(encoding, BoolEncoding) or not encoding.packed
    )


def _todo(msg: str, loc: SourceLocation | None) -> typing.Never:
    raise CodeError(msg, loc)
