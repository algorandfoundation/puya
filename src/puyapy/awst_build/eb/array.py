import typing
from collections.abc import Sequence

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import Expression
from puya.parse import SourceLocation
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb._base import GenericTypeBuilder
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder


class ArrayGenericTypeBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise NotImplementedError


class ArrayTypeBuilder(TypeBuilder[pytypes.ArrayType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == pytypes.GenericArrayType
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.WArray)
        self._wtype = wtype
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise NotImplementedError


def ArrayExpressionBuilder(expr: Expression, typ: pytypes.PyType) -> typing.Never:  # noqa: N802
    raise NotImplementedError
