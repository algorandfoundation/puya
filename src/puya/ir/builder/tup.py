import abc
import typing

from puya import log
from puya.awst import wtypes
from puya.errors import InternalError
from puya.ir import models as ir
from puya.ir.builder import arc4
from puya.ir.builder._utils import OpFactory
from puya.ir.encodings import (
    TupleEncoding,
    wtype_to_encoding,
)
from puya.ir.models import ValueTuple
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import (
    TupleIRType,
    get_type_arity,
    sum_types_arity,
    type_has_encoding,
    wtype_to_ir_type,
)
from puya.parse import SourceLocation
from puya.utils import bits_to_bytes

logger = log.get_logger(__name__)


class TupleBuilder(abc.ABC):
    @abc.abstractmethod
    def read_at_index(self, tup: ir.MultiValue, index: int) -> ir.MultiValue:
        """Reads the value from the specified index and performs any decoding required"""

    @abc.abstractmethod
    def write_at_index(self, tup: ir.Value, index: int, value: ir.MultiValue) -> ir.Value:
        """Encodes the value and writes to the specified index"""


def get_builder(
    context: IRRegisterContext, tuple_wtype: wtypes.WType, loc: SourceLocation
) -> TupleBuilder:
    if isinstance(tuple_wtype, wtypes.WTuple):
        tuple_ir_type = wtype_to_ir_type(tuple_wtype, loc, allow_tuple=True)
        return StackTupleBuilder(context, tuple_ir_type, loc)
    elif isinstance(tuple_wtype, wtypes.ARC4Tuple | wtypes.ARC4Struct):
        tuple_encoding = wtype_to_encoding(tuple_wtype, loc)
        tuple_ir_type = TupleIRType(
            elements=[wtype_to_ir_type(t, loc, allow_tuple=True) for t in tuple_wtype.types]
        )
        return EncodedTupleBuilder(context, tuple_encoding, tuple_ir_type, loc)
    else:
        raise InternalError(f"unsupported tuple wtype: {tuple_wtype}", loc)


class StackTupleBuilder(TupleBuilder):
    def __init__(
        self, context: IRRegisterContext, tuple_ir_type: TupleIRType, loc: SourceLocation
    ) -> None:
        self.context = context
        self.tuple_ir_type = tuple_ir_type
        self.loc = loc

    @typing.override
    def read_at_index(self, tup: ir.Value | ir.ValueTuple, index: int) -> ir.MultiValue:
        tuple_values = [tup] if isinstance(tup, ir.Value) else tup.values
        skip_values = sum_types_arity(self.tuple_ir_type.elements[:index])
        target_arity = get_type_arity(self.tuple_ir_type.elements[index])
        values = tuple_values[skip_values : skip_values + target_arity]

        if len(values) == 1:
            return values[0]
        else:
            return ValueTuple(values=values, source_location=self.loc)

    @typing.override
    def write_at_index(self, tup: ir.Value, index: int, value: ir.MultiValue) -> ir.Value:
        logger.error("tuples are immutable", locations=self.loc)
        return tup


class EncodedTupleBuilder(TupleBuilder):
    def __init__(
        self,
        context: IRRegisterContext,
        tuple_encoding: TupleEncoding,
        tuple_ir_type: TupleIRType,
        loc: SourceLocation,
    ) -> None:
        self.context = context
        self.tuple_encoding = tuple_encoding
        self.tuple_ir_type = tuple_ir_type
        self.loc = loc
        self.factory = OpFactory(self.context, self.loc)

    @typing.override
    def read_at_index(self, tup: ir.MultiValue, index: int) -> ir.MultiValue:
        try:
            (tup,) = self.context.materialise_value_provider(tup, "tup")
        except ValueError:
            raise InternalError("expected single value", self.loc) from None

        tuple_item_types = self.tuple_encoding.elements
        item_encoding = tuple_item_types[index]
        head_up_to_item = self.tuple_encoding.get_head_bit_offset(index)
        if item_encoding.is_bit:
            encoded = self.factory.get_bit(tup, head_up_to_item)
        elif not item_encoding.is_dynamic:
            head_offset = bits_to_bytes(head_up_to_item)
            encoded = self.factory.extract3(tup, head_offset, item_encoding.checked_num_bytes)
        else:
            head_offset = bits_to_bytes(head_up_to_item)
            item_start_offset = self.factory.extract_uint16(tup, head_offset)

            next_index = index + 1
            for tuple_item_index, tuple_item_type in enumerate(
                tuple_item_types[next_index:], start=next_index
            ):
                if tuple_item_type.is_dynamic:
                    head_up_to_next_dynamic_item = self.tuple_encoding.get_head_bit_offset(
                        tuple_item_index
                    )
                    item_end_offset = self.factory.extract_uint16(
                        tup, bits_to_bytes(head_up_to_next_dynamic_item)
                    )
                    break
            else:
                item_end_offset = self.factory.len(tup)
            encoded = self.factory.substring3(tup, item_start_offset, item_end_offset)
        item_encoding = self.tuple_encoding.elements[index]
        item_ir_type = self.tuple_ir_type.elements[index]
        return arc4.maybe_decode_value(
            self.context,
            encoded_item=encoded,
            encoding=item_encoding,
            target_type=item_ir_type,
            loc=self.loc,
        )

    @typing.override
    def write_at_index(self, tup: ir.Value, index: int, value: ir.MultiValue) -> ir.Value:
        value_ir_type = self.tuple_ir_type.elements[index]
        value = self.factory.materialise_single(value, "assigned_value")
        element_encoding = self.tuple_encoding.elements[index]

        # TODO: use ValueEncode
        if not type_has_encoding(value_ir_type, element_encoding):
            value_vp = arc4.encode_value(
                self.context,
                value,
                value_ir_type,
                element_encoding,
                self.loc,
            )
            value = self.factory.materialise_single(value_vp, "encoded")
        if element_encoding.is_bit:
            # Use Set bit
            is_true = self.factory.get_bit(value, 0, "is_true")
            return self.factory.set_bit(
                value=tup,
                index=self.tuple_encoding.get_head_bit_offset(index),
                bit=is_true,
                temp_desc="updated_data",
            )
        header_up_to_item_bytes = bits_to_bytes(self.tuple_encoding.get_head_bit_offset(index))
        if not element_encoding.is_dynamic:
            return self.factory.replace(
                tup,
                header_up_to_item_bytes,
                value,
                "updated_data",
            )
        else:
            assert element_encoding.is_dynamic, "expected dynamic encoding"
            dynamic_indices = [
                index for index, t in enumerate(self.tuple_encoding.elements) if t.is_dynamic
            ]

            item_offset = self.factory.extract_uint16(tup, header_up_to_item_bytes, "item_offset")
            data_up_to_item = self.factory.extract3(tup, 0, item_offset, "data_up_to_item")
            dynamic_indices_after_item = [i for i in dynamic_indices if i > index]

            if not dynamic_indices_after_item:
                # This is the last dynamic type in the tuple
                # No need to update headers - just replace the data
                return self.factory.concat(data_up_to_item, value, "updated_data")
            header_up_to_next_dynamic_item = bits_to_bytes(
                self.tuple_encoding.get_head_bit_offset(dynamic_indices_after_item[0])
            )

            # update tail portion with new item
            next_item_offset = self.factory.extract_uint16(
                tup,
                header_up_to_next_dynamic_item,
                "next_item_offset",
            )
            total_data_length = self.factory.len(tup, "total_data_length")
            data_beyond_item = self.factory.substring3(
                tup,
                next_item_offset,
                total_data_length,
                "data_beyond_item",
            )
            updated_data = self.factory.concat(data_up_to_item, value, "updated_data")
            updated_data = self.factory.concat(updated_data, data_beyond_item, "updated_data")

            # loop through head and update any offsets after modified item
            item_length = self.factory.sub(next_item_offset, item_offset, "item_length")
            new_value_length = self.factory.len(value, "new_value_length")
            for dynamic_index in dynamic_indices_after_item:
                header_up_to_dynamic_item = bits_to_bytes(
                    self.tuple_encoding.get_head_bit_offset(dynamic_index)
                )

                tail_offset = self.factory.extract_uint16(
                    updated_data, header_up_to_dynamic_item, "tail_offset"
                )
                # have to add the new length and then subtract the original to avoid underflow
                tail_offset = self.factory.add(tail_offset, new_value_length, "tail_offset")
                tail_offset = self.factory.sub(tail_offset, item_length, "tail_offset")
                tail_offset_bytes = self.factory.as_u16_bytes(tail_offset, "tail_offset_bytes")

                updated_data = self.factory.replace(
                    updated_data, header_up_to_dynamic_item, tail_offset_bytes, "updated_data"
                )
            return updated_data
