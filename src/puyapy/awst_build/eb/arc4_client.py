import typing
from collections.abc import Sequence

from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import constants, pytypes
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
    TypeBuilder,
)
from puyapy.models import (
    ContractFragmentBase,
    ContractFragmentMethod,
)


class ARC4ClientTypeBuilder(TypeBuilder):
    def __init__(
        self, typ: pytypes.PyType, source_location: SourceLocation, fragment: ContractFragmentBase
    ):
        assert pytypes.ARC4ClientBaseType in typ.bases
        super().__init__(typ, source_location)
        self.fragment: typing.Final = fragment

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("ARC4Client subclasses cannot be instantiated", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        method = self.fragment.resolve_method(name)
        if method is None:
            return super().member_access(name, location)
        return ARC4ClientMethodExpressionBuilder(method, location)


class ARC4ClientMethodExpressionBuilder(FunctionBuilder):
    def __init__(
        self,
        method: ContractFragmentMethod,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.method: typing.Final = method

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError(
            f"can't invoke client methods directly, use {constants.CLS_ARC4_ABI_CALL}", location
        )
