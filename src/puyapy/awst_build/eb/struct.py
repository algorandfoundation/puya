import typing
from collections.abc import Sequence

import mypy.nodes
from puya.awst.nodes import Expression
from puya.parse import SourceLocation

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
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise NotImplementedError


def StructExpressionBuilder(  # noqa: N802
    expr: Expression, typ: pytypes.PyType  # noqa: ARG001
) -> typing.Never:
    raise NotImplementedError
