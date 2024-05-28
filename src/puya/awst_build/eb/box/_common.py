import abc
import typing
from collections.abc import Sequence

import mypy.nodes

from puya.awst.nodes import BoxValueExpression, Literal, StateGet, StateGetEx
from puya.awst_build import pytypes
from puya.awst_build.eb.base import ExpressionBuilder, FunctionBuilder
from puya.awst_build.eb.tuple import TupleExpressionBuilder
from puya.awst_build.eb.var_factory import builder_for_instance
from puya.awst_build.utils import expect_operand_type
from puya.errors import CodeError
from puya.parse import SourceLocation


class _BoxKeyExpressionIntermediateExpressionBuilder(FunctionBuilder, abc.ABC):
    def __init__(self, box: BoxValueExpression, content_type: pytypes.PyType) -> None:
        super().__init__(box.source_location)
        self.box = box
        self.content_type = content_type


class BoxGetExpressionBuilder(_BoxKeyExpressionIntermediateExpressionBuilder):
    @typing.override
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
        default_expr = expect_operand_type(default_arg, self.content_type)
        return builder_for_instance(
            self.content_type,
            StateGet(field=self.box, default=default_expr, source_location=location),
        )


class BoxMaybeExpressionBuilder(_BoxKeyExpressionIntermediateExpressionBuilder):
    @typing.override
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
                field=self.box,
                source_location=location,
            ),
            pytypes.GenericTupleType.parameterise([self.content_type, pytypes.BoolType], location),
        )
