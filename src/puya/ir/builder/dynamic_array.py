import abc
import typing

from puya import log
from puya.awst import wtypes
from puya.errors import CodeError, InternalError
from puya.ir import models as ir
from puya.ir.builder._utils import OpFactory, invoke_puya_lib_subroutine
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
    PrimitiveIRType,
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
            case BoolEncoding(packed=True) if array_encoding.length_header:
                builder_typ = BitPackedBoolDynamicArrayBuilder
            case Encoding(is_dynamic=False):
                builder_typ = FixedElementDynamicArrayBuilder
            case ArrayEncoding(element=Encoding(num_bytes=1), length_header=True):
                builder_typ = DynamicByteLengthElementDynamicArrayBuilder
            case _ if array_encoding.length_header:
                assert element_encoding.is_dynamic, "expected dynamic element"
                builder_typ = DynamicElementDynamicArrayBuilder
            case _:
                raise CodeError(f"unsupported dynamic array type {wtype}", loc)
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

    def _get_iterable_length_and_head_tail(
        self,
        iterable: ir.ValueProvider,
        iterable_ir_type: IRType | TupleIRType,
        element_encoding: Encoding | None = None,
    ) -> tuple[ir.ValueProvider, ir.ValueProvider]:
        element_encoding = element_encoding or self.array_encoding.element
        # iterable is already encoded
        if isinstance(iterable_ir_type, EncodedType):
            iterable_encoding = iterable_ir_type.encoding
            # array of element
            if (
                isinstance(iterable_encoding, ArrayEncoding)
                and iterable_encoding.element == element_encoding
            ):
                materialised_iterable = self.factory.materialise_single(iterable)
                iterable_length: ir.ValueProvider = ir.ArrayLength(
                    array=materialised_iterable,
                    array_encoding=iterable_encoding,
                    source_location=self.loc,
                )
                if iterable_encoding.length_header:
                    iterable = self.factory.extract_to_end(materialised_iterable, 2)
            # homogenous tuple of element
            elif isinstance(iterable_encoding, TupleEncoding) and set(
                iterable_encoding.elements
            ) == {element_encoding}:
                iterable_length = ir.UInt64Constant(
                    value=len(iterable_encoding.elements), source_location=self.loc
                )
            elif iterable_encoding == element_encoding:
                iterable_length = ir.UInt64Constant(value=1, source_location=self.loc)
            else:
                iterable_length = ir.Undefined(
                    ir_type=PrimitiveIRType.uint64, source_location=self.loc
                )
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
            element_arity = get_type_arity(self.element_ir_type)
            iterable_arity = get_type_arity(iterable_ir_type)
            num_elements = iterable_arity // element_arity
            iterable_length = ir.UInt64Constant(value=num_elements, source_location=self.loc)

            # TODO: use ir.ValueEncode?
            # encoded_iterable = ir.ValueEncode(
            #    values=self.factory.materialise_values(iterable),
            #    value_type=TupleIRType(elements=[self.element_ir_type] * num_elements),
            #    encoding=DynamicArrayEncoding(element=element_encoding, length_header=False),
            #    source_location=self.loc,
            # )
            encoded_iterable = arc4.encode_value_provider(
                self.context,
                value_provider=iterable,
                value_type=TupleIRType(elements=[self.element_ir_type] * num_elements),
                encoding=DynamicArrayEncoding(element=element_encoding, length_header=False),
                loc=self.loc,
            )

        return iterable_length, encoded_iterable


class FixedElementDynamicArrayBuilder(_DynamicArrayBuilderImpl):
    @typing.override
    def concat(
        self, array: ir.Value, iterable: ir.ValueProvider, iterable_ir_type: IRType | TupleIRType
    ) -> ir.Value:
        _, head_and_tail = self._get_iterable_length_and_head_tail(iterable, iterable_ir_type)
        head_and_tail = self.factory.materialise_single(head_and_tail)
        updated_array = self.factory.concat(array, head_and_tail)
        if self.array_encoding.length_header:
            # TODO: if iterable is a tuple, would it be more efficient to just
            #       increment the length header by a constant?
            array_without_header = self.factory.extract_to_end(updated_array, 2)
            array_bytes = self.factory.len(array_without_header)
            array_len = self.factory.div_floor(
                array_bytes, self.array_encoding.element.checked_num_bytes
            )
            array_len_u16 = self.factory.as_u16_bytes(array_len)
            updated_array = self.factory.replace(updated_array, 0, array_len_u16)
        return updated_array

    @typing.override
    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.ValueProvider]:
        _todo("fixed element array pop", self.loc)


class DynamicByteLengthElementDynamicArrayBuilder(_DynamicArrayBuilderImpl):
    @typing.override
    def concat(
        self, array: ir.Value, iterable: ir.ValueProvider, iterable_ir_type: IRType | TupleIRType
    ) -> ir.Value:
        _todo("dynamic element byte length array concat", self.loc)

    @typing.override
    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.ValueProvider]:
        _todo("dynamic element byte length array pop", self.loc)


class DynamicElementDynamicArrayBuilder(_DynamicArrayBuilderImpl):
    @typing.override
    def concat(
        self, array: ir.Value, iterable: ir.ValueProvider, iterable_ir_type: IRType | TupleIRType
    ) -> ir.Value:
        assert self.array_encoding.length_header, "expected array to have a length header"
        l_count = self.factory.extract_uint16(array, 0)
        l_head_and_tail = self.factory.extract_to_end(array, 2)
        r_count, r_head_and_tail = self._get_iterable_length_and_head_tail(
            iterable, iterable_ir_type
        )
        r_count = self.factory.materialise_single(r_count)
        r_head_and_tail = self.factory.materialise_single(r_head_and_tail)
        invoke = invoke_puya_lib_subroutine(
            self.context,
            full_name="_puya_lib.arc4.dynamic_array_concat_dynamic_element",
            args=[l_count, l_head_and_tail, r_count, r_head_and_tail],
            source_location=self.loc,
        )
        return self.factory.materialise_single(invoke, "concat_result")

    @typing.override
    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.ValueProvider]:
        _todo("dynamic element array pop", self.loc)


class BitPackedBoolDynamicArrayBuilder(_DynamicArrayBuilderImpl):
    @typing.override
    def concat(
        self, array: ir.Value, iterable: ir.ValueProvider, iterable_ir_type: IRType | TupleIRType
    ) -> ir.Value:
        assert self.array_encoding.length_header, "expected array to have a length header"
        # iterable may not be packed
        match iterable_ir_type:
            case EncodedType(
                encoding=ArrayEncoding(element=BoolEncoding(packed=True) as iter_element_encoding)
            ):
                pass
            case EncodedType(
                encoding=TupleEncoding(
                    elements=[BoolEncoding(packed=True) as iter_element_encoding, *_]
                )
            ):
                pass
            case _:
                # each bit is in its own byte
                iter_element_encoding = BoolEncoding(packed=False)
        r_count, r_head_and_tail = self._get_iterable_length_and_head_tail(
            iterable, iterable_ir_type, element_encoding=iter_element_encoding
        )
        r_count = self.factory.materialise_single(r_count)
        r_head_and_tail = self.factory.materialise_single(r_head_and_tail)
        invoke = invoke_puya_lib_subroutine(
            self.context,
            full_name="_puya_lib.arc4.dynamic_array_concat_bits",
            args=[array, r_head_and_tail, r_count, 1 if iter_element_encoding.packed else 8],
            source_location=self.loc,
        )
        return self.factory.materialise_single(invoke, "concat_result")

    @typing.override
    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.ValueProvider]:
        _todo("bit packed bool array pop", self.loc)


def _todo(msg: str, loc: SourceLocation | None) -> typing.Never:
    raise CodeError(f"TODO: {msg}", loc)
