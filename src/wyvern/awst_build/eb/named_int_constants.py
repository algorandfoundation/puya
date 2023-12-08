import enum

from wyvern.awst import wtypes
from wyvern.awst.nodes import UInt64Constant
from wyvern.awst_build.eb.base import ExpressionBuilder, TypeClassExpressionBuilder
from wyvern.awst_build.eb.var_factory import var_expression
from wyvern.errors import CodeError
from wyvern.parse import SourceLocation


class NamedIntegerConstsTypeBuilder(TypeClassExpressionBuilder):
    def __init__(self, enum_name: str, data: dict[str, enum.IntEnum], location: SourceLocation):
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
        return var_expression(
            UInt64Constant(
                value=int_enum.value, source_location=location, teal_alias=int_enum.name
            )
        )
