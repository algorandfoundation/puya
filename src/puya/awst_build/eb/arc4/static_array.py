import typing
from collections.abc import Sequence

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import Expression, NewArray, UInt64Constant
from puya.awst_build import pytypes
from puya.awst_build.eb._base import GenericTypeBuilder
from puya.awst_build.eb._bytes_backed import BytesBackedTypeBuilder
from puya.awst_build.eb._utils import bool_eval_to_constant, expect_exactly_n_args
from puya.awst_build.eb.arc4._base import _ARC4ArrayExpressionBuilder
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puya.awst_build.eb.uint64 import UInt64ExpressionBuilder
from puya.awst_build.utils import require_instance_builder, require_instance_builder_of_type
from puya.errors import CodeError
from puya.parse import SourceLocation

__all__ = [
    "StaticArrayGenericTypeBuilder",
    "StaticArrayTypeBuilder",
    "StaticArrayExpressionBuilder",
]

logger = log.get_logger(__name__)


class StaticArrayGenericTypeBuilder(GenericTypeBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        if not args:
            raise CodeError("empty arrays require a type annotation to be instantiated", location)
        element_type = require_instance_builder(args[0]).pytype
        values = tuple(require_instance_builder_of_type(a, element_type).resolve() for a in args)
        array_size = len(values)
        typ = pytypes.GenericARC4StaticArrayType.parameterise(
            [element_type, pytypes.TypingLiteralType(value=array_size, source_location=None)],
            location,
        )
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4StaticArray)
        return StaticArrayExpressionBuilder(
            NewArray(values=values, wtype=wtype, source_location=location), typ
        )


class StaticArrayTypeBuilder(BytesBackedTypeBuilder[pytypes.ArrayType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.ArrayType)
        assert typ.generic == pytypes.GenericARC4StaticArrayType
        assert typ.size is not None
        self._size = typ.size
        super().__init__(typ, location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        typ = self.produces()
        n_args = expect_exactly_n_args(args, location, self._size)
        values = tuple(require_instance_builder_of_type(a, typ.items).resolve() for a in n_args)
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4StaticArray)
        return StaticArrayExpressionBuilder(
            NewArray(values=values, wtype=wtype, source_location=location), self.produces()
        )


class StaticArrayExpressionBuilder(_ARC4ArrayExpressionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.ArrayType)
        size = typ.size
        assert size is not None
        self._size = size
        super().__init__(typ, expr)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        match name:
            case "length":
                return UInt64ExpressionBuilder(
                    UInt64Constant(value=self._size, source_location=location)
                )
            case _:
                return super().member_access(name, location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return bool_eval_to_constant(value=self._size > 0, location=location, negate=negate)