import abc
import typing

from puya import log
from puya.awst import wtypes
from puya.errors import CodeError, InternalError
from puya.ir import models as ir
from puya.ir.builder._utils import OpFactory
from puya.ir.encodings import (
    ArrayEncoding,
    BoolEncoding,
    DynamicArrayEncoding,
    Encoding,
    TupleEncoding,
)
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import (
    EncodedType,
    IRType,
    SlotType,
    TupleIRType,
    get_type_arity,
    wtype_to_ir_type,
)
from puya.parse import SourceLocation

logger = log.get_logger(__name__)
# TODO: remove this
# ruff: noqa: ARG002


# region Dynamic arrays
class DynamicArrayBuilder(abc.ABC):
    # TODO: allow insert?

    @abc.abstractmethod
    def concat(
        self, array: ir.Value, iterable: ir.ValueProvider, iterable_ir_type: IRType | TupleIRType
    ) -> ir.Value:
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
    if isinstance(wtype, wtypes.NativeArray | wtypes.ARC4DynamicArray):
        array_ir_type = wtype_to_ir_type(wtype, source_location=loc)
        # only concerned with actual encoded of arrays, not where they are stored
        if isinstance(array_ir_type, SlotType):
            array_ir_type = array_ir_type.contents
        assert isinstance(array_ir_type, EncodedType), "expected EncodedType"
        array_encoding = array_ir_type.encoding
        assert isinstance(array_encoding, DynamicArrayEncoding), "expected DynamicArray encoding"
        element_ir_type = wtype_to_ir_type(
            wtype.element_type, source_location=loc, allow_tuple=True
        )
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
        array_ir_type: EncodedType,
        element_ir_type: IRType | TupleIRType,
        loc: SourceLocation,
    ) -> None:
        self.context = context
        self.array_ir_type = array_ir_type
        assert isinstance(
            array_ir_type.encoding, DynamicArrayEncoding
        ), "expected dynamic array encoding"
        self.array_encoding = array_ir_type.encoding
        self.element_ir_type = element_ir_type
        self.loc = loc
        self.factory = OpFactory(context, loc)


class FixedElementDynamicArrayBuilder(_DynamicArrayBuilderImpl):
    @typing.override
    def concat(
        self, array: ir.Value, iterable: ir.ValueProvider, iterable_ir_type: IRType | TupleIRType
    ) -> ir.Value:
        element_encoding = self.array_encoding.element
        # iterable is already encoded
        if isinstance(iterable_ir_type, EncodedType):
            iterable_encoding = iterable_ir_type.encoding
            # array of element
            if (
                isinstance(iterable_encoding, ArrayEncoding)
                and iterable_encoding.element == element_encoding
            ):
                if iterable_encoding.length_header:
                    iterable = self.factory.extract_to_end(
                        self.factory.materialise_single(iterable), 2
                    )
            # homogenous tuple of element
            elif (
                isinstance(iterable_encoding, TupleEncoding)
                and set(iterable_encoding.elements) == {element_encoding}
                or iterable_encoding == element_encoding
            ):
                pass
            else:
                logger.error(
                    f"cannot concat {self.array_encoding} and {iterable_encoding}",
                    location=self.loc,
                )

            encoded_iterable = iterable
        # iterable is an unencoded or tuple type
        else:
            from puya.ir.builder import arc4

            # the iterable could be either
            # a tuple of compatible native elements
            # a tuple of compatible encoded elements
            # a value of compatible native elements
            # all of which can be encoded as a dynamic array of the element
            # encoded_iterable = ir.ValueEncode(
            #    values=iterable_values,
            #    value_type=self.element_ir_type,
            #    encoding=DynamicArrayEncoding(element=element_encoding, length_header=False),
            #    source_location=self.loc,
            # )
            element_arity = get_type_arity(self.element_ir_type)
            iterable_arity = get_type_arity(iterable_ir_type)
            num_elements = iterable_arity // element_arity

            encoded_iterable = arc4.encode_value_provider(
                self.context,
                value_provider=iterable,
                value_type=TupleIRType(elements=[self.element_ir_type] * num_elements),
                encoding=DynamicArrayEncoding(element=element_encoding, length_header=False),
                loc=self.loc,
            )

        encoded_iterable = self.factory.materialise_single(encoded_iterable)
        array = self.factory.concat(array, encoded_iterable)
        if self.array_encoding.length_header:
            array_without_header = self.factory.extract_to_end(array, 2)
            array_bytes = self.factory.len(array_without_header)
            array_len = self.factory.div_floor(
                array_bytes, self.array_encoding.element.checked_num_bytes
            )
            array_len_u16 = self.factory.as_u16_bytes(array_len)
            array = self.factory.replace(array, 0, array_len_u16)
        return array

    @typing.override
    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.ValueProvider]:
        _todo("fixed element array pop", array.source_location)


class DynamicElementDynamicArrayBuilder(_DynamicArrayBuilderImpl):
    @typing.override
    def concat(
        self, array: ir.Value, iterable: ir.ValueProvider, iterable_ir_type: IRType | TupleIRType
    ) -> ir.Value:
        _todo("dynamic element array concat", array.source_location)

    @typing.override
    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.ValueProvider]:
        _todo("dynamic element array pop", array.source_location)


class BitPackedBoolDynamicArrayBuilder(_DynamicArrayBuilderImpl):
    @typing.override
    def concat(
        self, array: ir.Value, iterable: ir.ValueProvider, iterable_ir_type: IRType | TupleIRType
    ) -> ir.Value:
        _todo("bit packed bool array concat", array.source_location)

    @typing.override
    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.ValueProvider]:
        _todo("bit packed bool array pop", array.source_location)


def _todo(msg: str, loc: SourceLocation | None) -> typing.Never:
    raise CodeError(f"TODO: {msg}", loc)
