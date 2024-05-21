from collections.abc import Sequence

import mypy.nodes

from puya.awst.nodes import (
    BoxValueExpression,
    Literal,
    StateGet,
    StateGetEx,
)
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
)
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import (
    expect_operand_wtype,
)
from puya.errors import CodeError
from puya.parse import SourceLocation


class BoxKeyExpressionIntermediateExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(self, box_key_expression: BoxValueExpression) -> None:
        super().__init__(box_key_expression.source_location)
        self.box_key = box_key_expression


class BoxGetExpressionBuilder(BoxKeyExpressionIntermediateExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        if len(args) != 1:
            raise CodeError(f"Expected 1 argument, got {len(args)}", location)
        (default_arg,) = args
        default_expr = expect_operand_wtype(default_arg, target_wtype=self.box_key.wtype)
        # TODO: use pytype
        return var_expression(
            StateGet(field=self.box_key, default=default_expr, source_location=location)
        )


class BoxMaybeExpressionBuilder(BoxKeyExpressionIntermediateExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        if args:
            raise CodeError("Invalid/unexpected args", location)

        return TupleExpressionBuilder(
            StateGetEx(
                field=self.box_key,
                source_location=location,
            )
        )
