import abc

from puya.awst import wtypes
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

# TODO: have an abstraction for dynamically sized arrays to handle:
#       concat
#       extend/append
#       pop


class ArrayBuilder(abc.ABC):
    # TODO: add slice abstraction here too?
    @abc.abstractmethod
    def read_at_index(self, aggregate: ir.Value, index: ir.Value) -> ir.ValueProvider:
        """Reads the value from the specified index"""

    @abc.abstractmethod
    def write_at_index(
        self, aggregate: ir.Value, index: ir.Value, value: ir.ValueProvider
    ) -> None:
        """Writes value to the specified index"""

    @abc.abstractmethod
    def length(self, aggregate: ir.Value) -> ir.Value:
        """Returns the number of elements in the aggregate"""


class BitPackedBoolArrayBuilder(ArrayBuilder):
    def __init__(self, array_size: int | None, element_ir_type: IRType) -> None:
        self.array_size = array_size
        self.element_ir_type = element_ir_type
        self.bits_start_at = 16 if array_size is None else 0

    def read_at_index(self, aggregate: ir.Value, index: ir.Value | int) -> ir.ValueProvider:
        raise NotImplementedError

    def write_at_index(
        self, aggregate: ir.Value, index: ir.Value | int, value: ir.ValueProvider
    ) -> None:
        raise NotImplementedError

    def length(self, aggregate: ir.Value) -> ir.Value:
        raise NotImplementedError


class FixedElementArrayBuilder(ArrayBuilder):
    def __init__(self, array_encoding: ArrayEncoding, element_ir_type: IRType) -> None:
        self.array_encoding = array_encoding
        self.element_ir_type = element_ir_type
        self.element_num_bytes = self.array_encoding.element.checked_num_bytes

    def read_at_index(self, aggregate: ir.Value, index: ir.Value | int) -> ir.ValueProvider:
        raise NotImplementedError

    def write_at_index(
        self, aggregate: ir.Value, index: ir.Value | int, value: ir.ValueProvider
    ) -> None:
        raise NotImplementedError

    def length(self, aggregate: ir.Value) -> ir.Value:
        raise NotImplementedError


class DynamicElementArrayBuilder(ArrayBuilder):
    def __init__(self, array_encoding: ArrayEncoding, element_ir_type: IRType) -> None:
        self.array_encoding = array_encoding
        self.element_encoding = array_encoding.element
        self.element_ir_type = element_ir_type

    def read_at_index(self, aggregate: ir.Value, index: ir.Value | int) -> ir.ValueProvider:
        raise NotImplementedError

    def write_at_index(
        self, aggregate: ir.Value, index: ir.Value | int, value: ir.ValueProvider
    ) -> None:
        raise NotImplementedError

    def length(self, aggregate: ir.Value) -> ir.Value:
        raise NotImplementedError


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
