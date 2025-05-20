import abc

from puya.awst import wtypes
from puya.ir import models as ir
from puya.ir.types_ import (
    AggregateIRType,
    IRType,
    TupleEncoding,
    wtype_to_ir_type_and_encoding,
)
from puya.parse import SourceLocation


class TupleBuilder(abc.ABC):
    @abc.abstractmethod
    def read_at_index(self, tup: ir.ValueProvider, index: int) -> ir.ValueProvider:
        """Reads the value from the specified index"""

    @abc.abstractmethod
    def write_at_index(self, tup: ir.ValueProvider, index: int, value: ir.ValueProvider) -> None:
        """Writes value to the specified index"""


class StackTupleBuilder(TupleBuilder):
    def __init__(self, tuple_ir_type: IRType) -> None:
        self.tuple_ir_type = tuple_ir_type

    def read_at_index(self, tup: ir.ValueProvider, index: int) -> ir.ValueProvider:
        raise NotImplementedError

    def write_at_index(self, tup: ir.ValueProvider, index: int, value: ir.ValueProvider) -> None:
        raise NotImplementedError


class DynamicEncodedTupleBuilder(TupleBuilder):
    def __init__(self, tuple_encoding: TupleEncoding, tuple_ir_type: IRType) -> None:
        self.tuple_encoding = tuple_encoding
        self.tuple_ir_type = tuple_ir_type

    def read_at_index(self, tup: ir.ValueProvider, index: int) -> ir.ValueProvider:
        raise NotImplementedError

    def write_at_index(self, tup: ir.ValueProvider, index: int, value: ir.ValueProvider) -> None:
        raise NotImplementedError


class FixedEncodedTupleBuilder(TupleBuilder):
    def __init__(self, tuple_encoding: TupleEncoding, tuple_ir_type: IRType) -> None:
        self.tuple_encoding = tuple_encoding
        self.tuple_ir_type = tuple_ir_type

    def read_at_index(self, tup: ir.ValueProvider, index: int) -> ir.ValueProvider:
        raise NotImplementedError

    def write_at_index(self, tup: ir.ValueProvider, index: int, value: ir.ValueProvider) -> None:
        raise NotImplementedError


def get_tuple_builder(tuple_type: wtypes.WType, loc: SourceLocation) -> TupleBuilder | None:
    tuple_ir_type, tuple_encoding = wtype_to_ir_type_and_encoding(tuple_type, loc)
    if isinstance(tuple_ir_type, AggregateIRType):
        return StackTupleBuilder(tuple_ir_type)
    match tuple_encoding:
        case TupleEncoding() as tup if tup.is_dynamic:
            return DynamicEncodedTupleBuilder(tuple_encoding, tuple_ir_type)
        case TupleEncoding() as tup if not tup.is_dynamic:
            return FixedEncodedTupleBuilder(tuple_encoding, tuple_ir_type)
        case _:
            return None
