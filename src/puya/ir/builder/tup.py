import abc
import typing
from collections.abc import Sequence
from itertools import zip_longest

from puya.awst import wtypes
from puya.errors import InternalError
from puya.ir import models as ir
from puya.ir.builder import arc4
from puya.ir.builder._utils import OpFactory
from puya.ir.encodings import (
    BoolEncoding,
    Encoding,
    TupleEncoding,
    wtype_to_encoding,
)
from puya.ir.models import ValueTuple
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import (
    TupleIRType,
    get_type_arity,
    sum_types_arity,
    wtype_to_ir_type,
)
from puya.parse import SourceLocation
from puya.utils import bits_to_bytes, round_bits_to_nearest_bytes


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

    def read_at_index(self, tup: ir.Value | ir.ValueTuple, index: int) -> ir.MultiValue:
        tuple_values = [tup] if isinstance(tup, ir.Value) else tup.values
        skip_values = sum_types_arity(self.tuple_ir_type.elements[:index])
        target_arity = get_type_arity(self.tuple_ir_type.elements[index])
        values = tuple_values[skip_values : skip_values + target_arity]

        if len(values) == 1:
            return values[0]
        else:
            return ValueTuple(values=values, source_location=self.loc)

    def write_at_index(self, tup: ir.Value, index: int, value: ir.MultiValue) -> ir.Value:
        raise NotImplementedError


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

    def read_at_index(self, tup: ir.MultiValue, index: int) -> ir.MultiValue:
        try:
            (tup,) = self.context.materialise_value_provider(tup, "tup")
        except ValueError:
            raise InternalError("expected single value", self.loc) from None

        tuple_item_types = self.tuple_encoding.elements
        item_encoding = tuple_item_types[index]
        head_up_to_item = _get_head_bit_offset(tuple_item_types[:index])
        if _bit_packed_bool(item_encoding):
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
                    head_up_to_next_dynamic_item = _get_head_bit_offset(
                        tuple_item_types[:tuple_item_index]
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

    def write_at_index(self, tup: ir.Value, index: int, value: ir.MultiValue) -> ir.Value:
        raise NotImplementedError

# TODO: can these be properties of Encoding / TupleEncoding?
def _bit_packed_bool(encoding: Encoding) -> typing.TypeGuard[BoolEncoding]:
    return isinstance(encoding, BoolEncoding) and encoding.packed


def _get_head_bit_offset(encodings: Sequence[Encoding]) -> int:
    bit_size = 0
    for encoding, next_encoding in zip_longest(encodings, encodings[1:]):
        encoding_is_bit_packed_bool = _bit_packed_bool(encoding)
        if encoding.is_dynamic:
            size = 16
        elif encoding_is_bit_packed_bool:
            size = 1
        else:
            size = encoding.checked_num_bytes * 8
        bit_size += size
        # move to the next byte if bit-packing has ended
        if encoding_is_bit_packed_bool and next_encoding != encoding and next_encoding:
            bit_size = round_bits_to_nearest_bytes(bit_size)
    return bit_size
