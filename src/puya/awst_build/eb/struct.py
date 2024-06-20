import typing
from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya.awst.nodes import Expression, FieldExpression
from puya.awst_build import pytypes
from puya.awst_build.eb._base import NotIterableInstanceExpressionBuilder
from puya.awst_build.eb._utils import bool_eval_to_constant
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder
from puya.errors import CodeError
from puya.parse import SourceLocation


class StructSubclassExpressionBuilder(TypeBuilder[pytypes.StructType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.StructType)
        assert pytypes.StructBaseType in typ.mro
        super().__init__(typ, location)

    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise NotImplementedError


class StructExpressionBuilder(NotIterableInstanceExpressionBuilder[pytypes.StructType]):
    def __init__(self, expr: Expression, typ: pytypes.PyType):
        assert isinstance(typ, pytypes.StructType)
        super().__init__(typ, expr)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        try:
            field_type = self.pytype.fields[name]
        except KeyError as ex:
            raise CodeError(f"Invalid struct field: {name}", location) from ex
        field_expr = FieldExpression(location, field_type.wtype, self.resolve(), name)
        return builder_for_instance(field_type, field_expr)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return bool_eval_to_constant(value=True, location=location, negate=negate)
