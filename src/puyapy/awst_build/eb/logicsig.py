import typing
from collections.abc import Sequence

from puya.errors import CodeError
from puya.parse import SourceLocation
from puya.program_refs import LogicSigReference
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder


class LogicSigExpressionBuilder(TypeBuilder):
    def __init__(self, ref: LogicSigReference, location: SourceLocation):
        super().__init__(pytypes.LogicSigType, location)
        self.ref = ref

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("cannot instantiate logic signatures", location)
