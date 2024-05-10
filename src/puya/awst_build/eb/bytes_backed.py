import abc
import typing
from collections.abc import Sequence

import mypy.nodes
import typing_extensions

from puya.awst import wtypes
from puya.awst.nodes import BytesConstant, BytesEncoding, Expression, Literal, ReinterpretCast
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.errors import CodeError
from puya.parse import SourceLocation


class FromBytesBuilder(IntermediateExpressionBuilder):
    def __init__(self, result_wtype: wtypes.WType, location: SourceLocation):
        super().__init__(location)
        self.result_wtype = result_wtype

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case [Literal(value=bytes(bytes_val), source_location=literal_loc)]:
                arg: Expression = BytesConstant(
                    value=bytes_val, encoding=BytesEncoding.unknown, source_location=literal_loc
                )
            case [ExpressionBuilder(value_type=wtypes.bytes_wtype) as eb]:
                arg = eb.rvalue()
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        return var_expression(
            ReinterpretCast(source_location=location, wtype=self.result_wtype, expr=arg)
        )


_TWType_co = typing_extensions.TypeVar(
    "_TWType_co", bound=wtypes.WType, default=wtypes.WType, covariant=True
)


class BytesBackedClassExpressionBuilder(TypeClassExpressionBuilder[_TWType_co], abc.ABC):
    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        wtype = self.produces()
        match name:
            case "from_bytes":
                return FromBytesBuilder(wtype, location)
            case _:
                raise CodeError(
                    f"{name} is not a valid class or static method on {wtype}",
                    location,
                )
