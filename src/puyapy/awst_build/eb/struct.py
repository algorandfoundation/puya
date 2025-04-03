import typing
from collections.abc import Sequence

from puya.awst.nodes import Expression
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder


class StructSubclassExpressionBuilder(TypeBuilder[pytypes.StructType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.StructType)
        assert pytypes.StructBaseType < typ
        super().__init__(typ, location)

    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise NotImplementedError


def StructExpressionBuilder(expr: Expression, typ: pytypes.PyType) -> typing.Never:  # noqa: N802
    raise NotImplementedError
