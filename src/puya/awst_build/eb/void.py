import typing
from collections.abc import Sequence

import mypy.nodes

from puya.awst.nodes import Expression, Literal
from puya.awst_build import pytypes
from puya.awst_build.eb._utils import bool_eval_to_constant
from puya.awst_build.eb.base import (
    NotIterableInstanceExpressionBuilder,
    TypeBuilder,
)
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puya.errors import CodeError
from puya.parse import SourceLocation


class VoidTypeExpressionBuilder(TypeBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.NoneType, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> typing.Never:
        # shouldn't even be able to get here really
        raise CodeError("None is not usable as a value", location)


class VoidExpressionBuilder(NotIterableInstanceExpressionBuilder):
    def __init__(self, expr: Expression):
        super().__init__(pytypes.NoneType, expr)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return bool_eval_to_constant(value=False, location=location, negate=negate)
