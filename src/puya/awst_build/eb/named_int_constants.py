import enum
import typing
from collections.abc import Sequence

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import Literal, UInt64Constant
from puya.awst_build import pytypes
from puya.awst_build.eb.base import ExpressionBuilder, TypeClassExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.errors import CodeError
from puya.parse import SourceLocation


class NamedIntegerConstsTypeBuilder(TypeClassExpressionBuilder):

    def __init__(self, location: SourceLocation, *, enum_name: str, data: dict[str, enum.IntEnum]):
        super().__init__(wtypes.uint64_wtype, location)
        self.enum_name = enum_name
        self.data = data

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        raise CodeError("Cannot instantiate enumeration type", location)

    @typing.override
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
