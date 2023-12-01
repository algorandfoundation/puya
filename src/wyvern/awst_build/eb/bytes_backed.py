import abc
from collections.abc import Sequence

import mypy.nodes

from wyvern.awst import wtypes
from wyvern.awst.nodes import Literal, ReinterpretCast
from wyvern.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
)
from wyvern.awst_build.eb.var_factory import var_expression
from wyvern.awst_build.utils import expect_operand_wtype
from wyvern.errors import CodeError
from wyvern.parse import SourceLocation


class FromBytesBuilder(IntermediateExpressionBuilder):
    def __init__(self, result_wtype: wtypes.WType, location: SourceLocation):
        super().__init__(location)
        self.result_wtype = result_wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [ExpressionBuilder() as eb]:
                arg = expect_operand_wtype(eb, wtypes.bytes_wtype)
                return var_expression(
                    ReinterpretCast(source_location=location, wtype=self.result_wtype, expr=arg)
                )
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


class BytesBackedClassExpressionBuilder(TypeClassExpressionBuilder, abc.ABC):
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
