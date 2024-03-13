import typing
from collections.abc import Sequence

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import AssignmentExpression, Expression, Literal, Lvalue, VarExpression
from puya.awst_build.eb.base import ExpressionBuilder
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation


class ThrowawayExpressionBuilder(ExpressionBuilder):
    wtype = wtypes.throwaway_type

    def __init__(self, expr: Expression):
        super().__init__(expr.source_location)
        match expr:
            case VarExpression() as target:
                pass
            case AssignmentExpression(target=target):
                # this is an odd use case...
                pass
            case _:
                raise InternalError("Expected a VarExpression", expr.source_location)
        self._expr = target

    def lvalue(self) -> Lvalue:
        return self._expr

    def rvalue(self) -> typing.Never:
        self._raise_error(self.source_location)

    def delete(self, location: SourceLocation) -> typing.Never:
        self._raise_error(location)

    def index(self, index: ExpressionBuilder | Literal, location: SourceLocation) -> typing.Never:
        self._raise_error(location)

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> typing.Never:
        self._raise_error(location)

    def member_access(self, name: str, location: SourceLocation) -> typing.Never:
        self._raise_error(location)

    def iterate(self) -> typing.Never:
        self._raise_error(self.source_location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> typing.Never:
        self._raise_error(location)

    def unary_plus(self, location: SourceLocation) -> typing.Never:
        self._raise_error(location)

    def unary_minus(self, location: SourceLocation) -> typing.Never:
        self._raise_error(location)

    def bitwise_invert(self, location: SourceLocation) -> typing.Never:
        self._raise_error(location)

    def contains(
        self, item: ExpressionBuilder | Literal, location: SourceLocation
    ) -> typing.Never:
        self._raise_error(location)

    def _raise_error(self, location: SourceLocation) -> typing.Never:
        raise CodeError("'_' variables can only be assigned to", location)
