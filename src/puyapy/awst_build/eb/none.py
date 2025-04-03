import typing
from collections.abc import Sequence

from puya.awst.nodes import Expression, VoidConstant
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import NotIterableInstanceExpressionBuilder
from puyapy.awst_build.eb._utils import constant_bool_and_error
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder


class NoneTypeBuilder(TypeBuilder):
    def __init__(self, location: SourceLocation):
        super().__init__(pytypes.NoneType, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        expect.no_args(args, location)
        return NoneExpressionBuilder(VoidConstant(location))


class NoneExpressionBuilder(NotIterableInstanceExpressionBuilder):
    def __init__(self, expr: Expression):
        super().__init__(pytypes.NoneType, expr)

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        raise CodeError("None is not usable as a value", location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(value=False, location=location, negate=negate)
