import abc

from puya.awst import wtypes
from puya.errors import InternalError
from puya.ir import models as ir
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
    wtype_to_ir_type,
)
from puya.parse import SourceLocation


class TupleBuilder(abc.ABC):
    @abc.abstractmethod
    def read_at_index(self, tup: ir.MultiValue, index: int) -> ir.ValueProvider:
        """Reads the value from the specified index and performs any decoding required"""

    @abc.abstractmethod
    def write_at_index(
        self, tup: ir.Value, index: int, value: ir.ValueProvider
    ) -> ir.ValueProvider:
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

    def read_at_index(self, tup: ir.Value | ir.ValueTuple, index: int) -> ir.ValueProvider:
        tuple_values = [tup] if isinstance(tup, ir.Value) else tup.values
        skip_values = sum_types_arity(self.tuple_ir_type.elements[:index])
        target_arity = get_type_arity(self.tuple_ir_type.elements[index])
        values = tuple_values[skip_values : skip_values + target_arity]

        if len(values) == 1:
            return values[0]
        else:
            return ValueTuple(values=values, source_location=self.loc)

    def write_at_index(
        self, tup: ir.ValueProvider, index: int, value: ir.ValueProvider
    ) -> ir.ValueProvider:
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

    def read_at_index(self, tup: ir.MultiValue, index: int) -> ir.ValueProvider:
        from puya.ir.builder import arc4

        try:
            (tup,) = self.context.materialise_value_provider(tup, "tup")
        except ValueError:
            raise InternalError("expected single value", self.loc) from None

        # TODO: refactor arc4_tuple_index
        return arc4.arc4_tuple_index(
            self.context,
            base=tup,
            index=index,
            tuple_encoding=self.tuple_encoding,
            item_ir_type=self.tuple_ir_type.elements[index],
            source_location=self.loc,
        )

    def write_at_index(
        self, tup: ir.ValueProvider, index: int, value: ir.ValueProvider
    ) -> ir.ValueProvider:
        raise NotImplementedError
