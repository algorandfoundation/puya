import abc
import typing

from puya.awst import wtypes
from puya.errors import CodeError
from puya.ir import models as ir
from puya.ir.builder._utils import OpFactory
from puya.ir.encodings import (
    BoolEncoding,
    DynamicArrayEncoding,
)
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import (
    PrimitiveIRType,
    wtype_to_ir_type_and_encoding,
)
from puya.parse import SourceLocation

# TODO: remove this
# ruff: noqa: ARG002


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


class BytesIndexableBuilder(DynamicArrayBuilder):
    def __init__(self, context: IRRegisterContext, loc: SourceLocation) -> None:
        self.loc = loc
        self.factory = OpFactory(context, loc)

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


def _todo(msg: str, loc: SourceLocation | None) -> typing.Never:
    raise CodeError(msg, loc)
