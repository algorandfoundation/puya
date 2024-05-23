import typing
from collections.abc import Sequence

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import Literal
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.errors import CodeError
from puya.parse import SourceLocation


class VoidTypeExpressionBuilder(TypeClassExpressionBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.NoneType, location)

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> typing.Never:
        # shouldn't even be able to get here really
        raise CodeError("None is not usable as a value", location)


class VoidExpressionBuilder(ValueExpressionBuilder):
    wtype = wtypes.void_wtype

    def lvalue(self) -> typing.Never:
        raise CodeError(
            "None indicates an empty return and cannot be assigned", self.source_location
        )
