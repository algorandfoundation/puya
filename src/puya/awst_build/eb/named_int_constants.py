import enum

from puya.awst import wtypes
from puya.awst.nodes import UInt64Constant
from puya.awst_build.eb.base import ExpressionBuilder, TypeClassExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.errors import CodeError
from puya.parse import SourceLocation


class NamedIntegerConstsTypeBuilder(TypeClassExpressionBuilder):
    def __init__(self, location: SourceLocation, *, enum_name: str, data: dict[str, enum.IntEnum]):
        super().__init__(location=location)
        self.enum_name = enum_name
        self.data = data

    def produces(self) -> wtypes.WType:
        return wtypes.uint64_wtype

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        try:
            int_enum = self.data[name]
        except KeyError as ex:
            raise CodeError(
                f"Unable to resolve constant value for {self.enum_name}.{name}", location
            ) from ex
        return UInt64ExpressionBuilder(
            UInt64Constant(
                value=int_enum.value, source_location=location, teal_alias=int_enum.name
            )
        )
