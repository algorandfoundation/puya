import abc
import typing
from collections.abc import Sequence

import typing_extensions

from puya.awst.nodes import Expression, ReinterpretCast
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder, InstanceExpressionBuilder
from puyapy.awst_build.eb._utils import cast_to_bytes
from puyapy.awst_build.eb.bytes import BytesExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder

_TPyType_co = typing_extensions.TypeVar(
    "_TPyType_co", bound=pytypes.PyType, default=pytypes.PyType, covariant=True
)


class BytesBackedTypeBuilder(TypeBuilder[_TPyType_co], abc.ABC):
    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        typ = self.produces()
        match name:
            case "from_bytes":
                return _FromBytes(typ, location)
            case _:
                return super().member_access(name, location)


class _FromBytes(FunctionBuilder):
    def __init__(self, result_type: pytypes.PyType, location: SourceLocation):
        super().__init__(location)
        self.result_type = result_type

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg = expect.exactly_one_arg_of_type_else_dummy(
            args, pytypes.BytesType, location, resolve_literal=True
        )
        result_expr = ReinterpretCast(
            expr=arg.resolve(),
            wtype=self.result_type.checked_wtype(location),
            source_location=location,
        )
        return builder_for_instance(self.result_type, result_expr)


class BytesBackedInstanceExpressionBuilder(InstanceExpressionBuilder[_TPyType_co], abc.ABC):
    _bytes_member: typing.ClassVar[str]

    def __init_subclass__(cls, *, bytes_member: str = "bytes", **kwargs: object):
        super().__init_subclass__(**kwargs)
        cls._bytes_member = bytes_member

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name == self._bytes_member:
            return self.bytes(location)
        else:
            return super().member_access(name, location)

    def bytes(self, location: SourceLocation) -> BytesExpressionBuilder:
        return BytesExpressionBuilder(self.to_bytes(location))

    @typing.override
    def to_bytes(self, location: SourceLocation) -> Expression:
        return cast_to_bytes(self.resolve(), location)
