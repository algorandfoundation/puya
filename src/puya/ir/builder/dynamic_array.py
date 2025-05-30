import abc
import typing

from puya import log
from puya.awst import wtypes
from puya.errors import CodeError, InternalError
from puya.ir import models as ir
from puya.ir._puya_lib import PuyaLibIR
from puya.ir.builder._utils import (
    OpFactory,
    invoke_puya_lib_subroutine,
)
from puya.ir.builder.sequence import get_length, requires_conversion
from puya.ir.encodings import (
    ArrayEncoding,
    BoolEncoding,
    DynamicArrayEncoding,
    Encoding,
    TupleEncoding,
    UTF8Encoding,
)
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import (
    EncodedType,
    IRType,
    PrimitiveIRType,
    SlotType,
    TupleIRType,
    wtype_to_ir_type,
)
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


# region Dynamic arrays
class DynamicArrayBuilder(abc.ABC):
    # TODO: allow insert?

    @abc.abstractmethod
    def concat(
        self, array: ir.Value, iterable: ir.MultiValue, iterable_ir_type: IRType | TupleIRType
    ) -> ir.Value:
        """Returns the concatenation of an array and iterable"""

    # TODO: allow pop by index?
    @abc.abstractmethod
    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.MultiValue]:
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
        # TODO: find a better way to handle these cases
        if array_encoding.element in (UTF8Encoding(), BoolEncoding(packed=True)):
            element_ir_type: IRType | TupleIRType = EncodedType(encoding=array_encoding.element)
        else:
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
                iterable_length: ir.ValueProvider = get_length(
                    self.context, iterable_encoding, materialised_iterable, self.loc
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
            if not isinstance(iterable_ir_type, TupleIRType):
                raise InternalError("expected tuple type for concatenation", self.loc)
            # the iterable could be either
            # a tuple of compatible native elements
            # a tuple of compatible encoded elements
            if len(set(iterable_ir_type.elements)) != 1:
                raise InternalError("expected homogenous tuple for concatenation", self.loc)
            # all of which can be encoded as a dynamic array of the element
            iterable_length = ir.UInt64Constant(
                value=len(iterable_ir_type.elements), source_location=self.loc
            )

            encoded_iterable = ir.ValueEncode(
                values=self.factory.materialise_values(iterable),
                value_type=iterable_ir_type,
                encoding=DynamicArrayEncoding(element=element_encoding, length_header=False),
                source_location=self.loc,
            )

        return iterable_length, encoded_iterable

    def _as_array_type(self, value: ir.ValueProvider) -> ir.Value:
        return self.factory.as_ir_type(value, self.array_ir_type)

    def _maybe_decode(self, encoded_item: ir.Value) -> ir.MultiValue:
        if not requires_conversion(self.element_ir_type, self.array_encoding.element, "decode"):
            return self.factory.materialise_single(encoded_item)
        else:
            encoded_item = self.factory.materialise_single(encoded_item, "encoded_item")
            return self.factory.materialise_multi_value(
                ir.ValueDecode(
                    value=encoded_item,
                    encoding=self.array_encoding.element,
                    decoded_type=self.element_ir_type,
                    source_location=self.loc,
                )
            )


class FixedElementDynamicArrayBuilder(_DynamicArrayBuilderImpl):
    @typing.override
    def concat(
        self, array: ir.Value, iterable: ir.ValueProvider, iterable_ir_type: IRType | TupleIRType
    ) -> ir.Value:
        _, iter_head_and_tail = self._get_iterable_length_and_head_tail(iterable, iterable_ir_type)
        iter_head_and_tail = self.factory.materialise_single(iter_head_and_tail)
        updated_array = self.factory.concat(
            array,
            iter_head_and_tail,
            ir_type=array.ir_type,
            error_message="max array length exceeded",
        )
        if self.array_encoding.length_header:
            if isinstance(iterable_ir_type, TupleIRType):
                existing_len = self.factory.extract_uint16(array, 0)
                array_len = self.factory.add(existing_len, len(iterable_ir_type.elements))
            else:
                array_head_and_tail = self.factory.extract_to_end(updated_array, 2)
                array_bytes_len = self.factory.len(array_head_and_tail)
                array_len = self.factory.div_floor(
                    array_bytes_len, self.array_encoding.element.checked_num_bytes
                )
            array_len_u16 = self.factory.as_u16_bytes(array_len)
            updated_array = self.factory.replace(updated_array, 0, array_len_u16)
        return self._as_array_type(updated_array)

    @typing.override
    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.MultiValue]:
        element_encoding = self.array_encoding.element
        if self.array_encoding.length_header:
            invoke = invoke_puya_lib_subroutine(
                self.context,
                full_name=PuyaLibIR.dynamic_array_pop_fixed_size,
                args=[array, element_encoding.checked_num_bytes],
                source_location=self.loc,
            )
            popped, data = self.factory.materialise_values(invoke)
        else:
            array_bytes_len = self.factory.len(array)
            start_offset = self.factory.sub(array_bytes_len, element_encoding.checked_num_bytes)
            popped = self.factory.extract_to_end(array, start_offset)
            data = self.factory.extract3(array, 0, start_offset)
        return data, self._maybe_decode(popped)


class DynamicByteLengthElementDynamicArrayBuilder(_DynamicArrayBuilderImpl):
    @typing.override
    def concat(
        self, array: ir.Value, iterable: ir.MultiValue, iterable_ir_type: IRType | TupleIRType
    ) -> ir.Value:
        if isinstance(iterable_ir_type, TupleIRType):
            tuple_size = len(iterable_ir_type.elements)
            r_count: ir.Value = self.factory.constant(tuple_size)
            # only need to construct the tail, so iterate and concat
            r_tail: ir.Value = self.factory.constant(b"")
            values = self.factory.materialise_values(iterable)
            (element_ir_type,) = set(iterable_ir_type.elements)
            element_encoding = self.array_encoding.element
            for _ in range(tuple_size):
                encoded_element_vp = ir.ValueEncode(
                    values=values[: element_ir_type.arity],
                    encoding=element_encoding,
                    value_type=element_ir_type,
                    source_location=self.loc,
                )
                encoded_element = self.factory.materialise_single(encoded_element_vp)
                r_tail = self.factory.concat(r_tail, encoded_element)
                values = values[element_ir_type.arity :]
            assert not values, "too many values to encode"
        else:
            # existing iterable, get head and tail and remove head
            r_count_vp, r_head_and_tail = self._get_iterable_length_and_head_tail(
                iterable, iterable_ir_type
            )
            r_count = self.factory.materialise_single(r_count_vp)
            r_head_and_tail = self.factory.materialise_single(r_head_and_tail)
            start_of_tail = self.factory.mul(r_count, 2, "start_of_tail")
            r_tail = self.factory.extract_to_end(r_head_and_tail, start_of_tail, "data")

        invoke = invoke_puya_lib_subroutine(
            self.context,
            full_name=PuyaLibIR.dynamic_array_concat_byte_length_head,
            args=[array, r_tail, r_count],
            source_location=self.loc,
        )
        return self._as_array_type(invoke)

    @typing.override
    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.MultiValue]:
        invoke = invoke_puya_lib_subroutine(
            self.context,
            full_name=PuyaLibIR.dynamic_array_pop_byte_length_head,
            args=[array],
            source_location=self.loc,
        )
        popped, data = self.factory.materialise_values(invoke)
        return data, self._maybe_decode(popped)


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
            full_name=PuyaLibIR.dynamic_array_concat_dynamic_element,
            args=[l_count, l_head_and_tail, r_count, r_head_and_tail],
            source_location=self.loc,
        )
        return self._as_array_type(invoke)

    @typing.override
    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.MultiValue]:
        invoke = invoke_puya_lib_subroutine(
            self.context,
            full_name=PuyaLibIR.dynamic_array_pop_dynamic_element,
            args=[array],
            source_location=self.loc,
        )
        popped, data = self.factory.materialise_values(invoke)
        return data, self._maybe_decode(popped)


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
                pass  # TODO: test case coverage
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
            full_name=PuyaLibIR.dynamic_array_concat_bits,
            args=[array, r_head_and_tail, r_count, 1 if iter_element_encoding.packed else 8],
            source_location=self.loc,
        )
        return self._as_array_type(invoke)

    @typing.override
    def pop(self, array: ir.Value) -> tuple[ir.Value, ir.MultiValue]:
        invoke = invoke_puya_lib_subroutine(
            self.context,
            full_name=PuyaLibIR.dynamic_array_pop_bit,
            args=[array],
            source_location=self.loc,
        )
        popped, data = self.factory.materialise_values(invoke)
        return data, self._maybe_decode(popped)
