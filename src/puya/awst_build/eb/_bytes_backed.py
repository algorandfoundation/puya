import abc
import typing
from collections.abc import Sequence

import mypy.nodes
import typing_extensions

from puya.awst import wtypes
from puya.awst.nodes import (
    BytesConstant,
    BytesEncoding,
    Expression,
    ReinterpretCast,
)
from puya.awst_build import pytypes
from puya.awst_build.eb._base import FunctionBuilder, InstanceExpressionBuilder, TypeBuilder
from puya.awst_build.eb.bytes import BytesExpressionBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import InstanceBuilder, LiteralBuilder, NodeBuilder
from puya.errors import CodeError
from puya.parse import SourceLocation

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
                raise CodeError(
                    f"{name} is not a valid class or static method on {typ}",
                    location,
                )


class _FromBytes(FunctionBuilder):
    def __init__(self, result_type: pytypes.PyType, location: SourceLocation):
        super().__init__(location)
        self.result_type = result_type

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case [LiteralBuilder(value=bytes(bytes_val), source_location=literal_loc)]:
                arg: Expression = BytesConstant(
                    value=bytes_val, encoding=BytesEncoding.unknown, source_location=literal_loc
                )
            case [InstanceBuilder(pytype=pytypes.BytesType) as eb]:
                arg = eb.resolve()
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        result_expr = ReinterpretCast(
            source_location=location, wtype=self.result_type.wtype, expr=arg
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
            return BytesExpressionBuilder(self.serialize_bytes(location))
        else:
            return super().member_access(name, location)

    @typing.override
    def serialize_bytes(self, location: SourceLocation) -> Expression:
        return ReinterpretCast(
            source_location=location, wtype=wtypes.bytes_wtype, expr=self.resolve()
        )
