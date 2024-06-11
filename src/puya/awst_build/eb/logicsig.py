import typing
from collections.abc import Sequence

import mypy.nodes

from puya.awst_build import pytypes
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder
from puya.errors import CodeError
from puya.parse import SourceLocation


class LogicSigExpressionBuilder(TypeBuilder):

    def __init__(self, fullname: str, location: SourceLocation):
        super().__init__(pytypes.LogicSigType, location)
        self.fullname = fullname

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("cannot instantiate logic signatures", location)
