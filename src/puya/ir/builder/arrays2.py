import abc
import typing

from puya.awst import wtypes
from puya.errors import CodeError
from puya.ir import models as ir
from puya.ir.types_ import (
    ArrayEncoding,
    BoolEncoding,
    DynamicArrayEncoding,
    FixedArrayEncoding,
    IRType,
    wtype_to_ir_type_and_encoding,
)
from puya.parse import SourceLocation

# TODO: remove this
# ruff: noqa: ARG002


class ArrayBuilder(abc.ABC):
    # TODO: add slice abstraction here too?
    @abc.abstractmethod
    def read_at_index(self, array: ir.Value, index: ir.Value) -> ir.ValueProvider:
        """Reads the value from the specified index"""

    @abc.abstractmethod
    def write_at_index(self, array: ir.Value, index: ir.Value, value: ir.ValueProvider) -> None:
        """Writes value to the specified index"""

    @abc.abstractmethod
    def length(self, array: ir.Value) -> ir.Value:
        """Returns the number of elements in the aggregate"""


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
    def __init__(self, array_encoding: ArrayEncoding, element_ir_type: IRType) -> None:
        self.array_encoding = array_encoding
        self.element_ir_type = element_ir_type
        self.element_num_bytes = self.array_encoding.element.checked_num_bytes

    def read_at_index(self, array: ir.Value, index: ir.Value | int) -> ir.ValueProvider:
        _todo("fixed element array read", array.source_location)

    def write_at_index(
        self, array: ir.Value, index: ir.Value | int, value: ir.ValueProvider
    ) -> None:
        _todo("fixed element array write", array.source_location)

    def length(self, array: ir.Value) -> ir.Value:
        _todo("fixed element array length", array.source_location)


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
    array_type: wtypes.ARC4Array | wtypes.NativeArray, loc: SourceLocation
) -> ArrayBuilder | None:
    element_ir_type, _ = wtype_to_ir_type_and_encoding(array_type.element_type, loc)
    array_ir_type, array_encoding = wtype_to_ir_type_and_encoding(array_type, loc)
    assert isinstance(array_encoding, ArrayEncoding), "expected array encoding"
    match array_encoding:
        case DynamicArrayEncoding(element=BoolEncoding(packable=True), length_header=True):
            return BitPackedBoolArrayBuilder(None, element_ir_type)
        case FixedArrayEncoding(element=BoolEncoding(packable=True), size=array_size):
            return BitPackedBoolArrayBuilder(array_size, element_ir_type)
        case ArrayEncoding(element=BoolEncoding(packable=True)):
            # unsupported
            return None
        case ArrayEncoding(element=element) if element.is_dynamic:
            return DynamicElementArrayBuilder(array_encoding, element_ir_type)
        case ArrayEncoding(element=element) if not element.is_dynamic:
            return FixedElementArrayBuilder(array_encoding, element_ir_type)
        case _:
            return None


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


def get_dynamic_array_builder(
    array_type: wtypes.ARC4Array | wtypes.NativeArray, loc: SourceLocation
) -> DynamicArrayBuilder | None:
    element_ir_type, _ = wtype_to_ir_type_and_encoding(array_type.element_type, loc)
    array_ir_type, array_encoding = wtype_to_ir_type_and_encoding(array_type, loc)
    assert isinstance(array_encoding, DynamicArrayEncoding), "expected dynamic array encoding"
    match array_encoding:
        case DynamicArrayEncoding(
            element=BoolEncoding(packable=True), length_header=length_header
        ):
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


def _todo(msg: str, loc: SourceLocation | None) -> typing.Never:
    raise CodeError(msg, loc)
