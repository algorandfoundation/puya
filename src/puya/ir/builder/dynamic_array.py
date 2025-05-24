import abc
import typing

from puya.awst import wtypes
from puya.errors import CodeError, InternalError
from puya.ir import models as ir
from puya.ir.builder._utils import OpFactory
from puya.ir.encodings import (
    BoolEncoding,
    DynamicArrayEncoding,
    Encoding,
    wtype_to_encoding,
)
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import (
    IRType,
    PrimitiveIRType,
    wtype_to_ir_type,
)
from puya.parse import SourceLocation

# TODO: remove this
# ruff: noqa: ARG002


# region Dynamic arrays
class DynamicArrayBuilder(abc.ABC):
    # TODO: allow insert?

    @abc.abstractmethod
    def concat(self, array: ir.Value, iterable: ir.ValueProvider) -> ir.Value:
        """Returns the concatenation of an array and iterable"""

    # TODO: allow pop by index?
    @abc.abstractmethod
    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.ValueProvider]:
        """
        Removes the last item of an array

        Returns the updated array and the removed item
        """


def get_builder(
    context: IRRegisterContext,
    wtype: wtypes.WType,
    loc: SourceLocation,
) -> DynamicArrayBuilder:
    if isinstance(wtype, wtypes.ReferenceArray | wtypes.ARC4DynamicArray):
        array_ir_type = wtype_to_ir_type(wtype, source_location=loc)
        element_ir_type = wtype_to_ir_type(
            wtype.element_type, source_location=loc, allow_aggregate=True
        )
        array_encoding = wtype_to_encoding(wtype, loc)
        element_encoding = array_encoding.element
        builder_typ: type[_DynamicArrayBuilderImpl]
        match element_encoding:
            # BitPackedBool is a more specific match than FixedElement so do that first
            case BoolEncoding(packed=True):
                builder_typ = BitPackedBoolDynamicArrayBuilder
            case Encoding(is_dynamic=False):
                builder_typ = FixedElementDynamicArrayBuilder
            case _:
                assert element_encoding.is_dynamic, "expected dynamic element"
                builder_typ = DynamicElementDynamicArrayBuilder
        return builder_typ(
            context,
            array_encoding=array_encoding,
            array_ir_type=array_ir_type,
            element_ir_type=element_ir_type,
            loc=loc,
        )

    raise InternalError(f"unsupported array type: {wtype!s}", loc)


class _DynamicArrayBuilderImpl(DynamicArrayBuilder):
    def __init__(
        self,
        context: IRRegisterContext,
        *,
        array_encoding: DynamicArrayEncoding,
        array_ir_type: IRType,
        element_ir_type: IRType,
        loc: SourceLocation,
    ) -> None:
        self.context = context
        self.array_encoding = array_encoding
        self.array_ir_type = array_ir_type
        self.element_ir_type = element_ir_type
        self.loc = loc


class FixedElementDynamicArrayBuilder(_DynamicArrayBuilderImpl):
    def concat(self, array: ir.Value, iterable: ir.ValueProvider) -> ir.Value:
        _todo("fixed element array concat", array.source_location)

    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.ValueProvider]:
        _todo("fixed element array pop", array.source_location)


class DynamicElementDynamicArrayBuilder(_DynamicArrayBuilderImpl):
    def concat(self, array: ir.Value, iterable: ir.ValueProvider) -> ir.Value:
        _todo("dynamic element array concat", array.source_location)

    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.ValueProvider]:
        _todo("dynamic element array pop", array.source_location)


class BitPackedBoolDynamicArrayBuilder(_DynamicArrayBuilderImpl):
    def concat(self, array: ir.Value, iterable: ir.ValueProvider) -> ir.Value:
        _todo("bit packed bool array concat", array.source_location)

    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.ValueProvider]:
        _todo("bit packed bool array pop", array.source_location)


class BytesIndexableBuilder(DynamicArrayBuilder):
    def __init__(self, context: IRRegisterContext, loc: SourceLocation) -> None:
        self.loc = loc
        self.factory = OpFactory(context, loc)

    def concat(self, array: ir.Value, iterable: ir.ValueProvider) -> ir.Value:
        other = self.factory.materialise_single(iterable, "other")
        return self.factory.concat(array, other, "bytes_concat")

    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.ValueProvider]:
        self._immutable()
        return array, ir.Undefined(ir_type=PrimitiveIRType.bytes, source_location=None)

    def _immutable(self) -> None:
        raise CodeError("bytes array is immutable", location=self.loc)


def _todo(msg: str, loc: SourceLocation | None) -> typing.Never:
    raise CodeError(msg, loc)
