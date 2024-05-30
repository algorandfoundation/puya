import abc
import typing
from collections.abc import Sequence

import mypy.nodes
import typing_extensions

from puya.awst.nodes import BytesConstant, BytesEncoding, Expression, Literal, ReinterpretCast
from puya.awst_build import pytypes
from puya.awst_build.eb._base import FunctionBuilder, TypeBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puya.errors import CodeError
from puya.parse import SourceLocation

_TPyType_co = typing_extensions.TypeVar(
    "_TPyType_co", bound=pytypes.PyType, default=pytypes.PyType, covariant=True
)


class BytesBackedClassExpressionBuilder(TypeBuilder[_TPyType_co], abc.ABC):
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
        args: Sequence[NodeBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        match args:
            case [Literal(value=bytes(bytes_val), source_location=literal_loc)]:
                arg: Expression = BytesConstant(
                    value=bytes_val, encoding=BytesEncoding.unknown, source_location=literal_loc
                )
            case [InstanceBuilder(pytype=pytypes.BytesType) as eb]:
                arg = eb.rvalue()
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        result_expr = ReinterpretCast(
            source_location=location, wtype=self.result_type.wtype, expr=arg
        )
        return builder_for_instance(self.result_type, result_expr)
