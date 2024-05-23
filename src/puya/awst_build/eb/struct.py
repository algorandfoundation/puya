from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya.awst import wtypes
from puya.awst.nodes import Expression, FieldExpression, Literal
from puya.awst_build import pytypes
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.var_factory import builder_for_instance, var_expression
from puya.errors import CodeError
from puya.parse import SourceLocation


class StructSubclassExpressionBuilder(TypeClassExpressionBuilder[wtypes.WStructType]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.StructType)
        # assert pytypes.StructBaseType in typ.mro TODO?
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.WStructType)
        super().__init__(wtype, location)

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        raise NotImplementedError


class StructExpressionBuilder(ValueExpressionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType | None = None):  # TODO
        if typ is not None:
            assert isinstance(typ, pytypes.StructType)
        self.pytyp = typ
        assert isinstance(expr.wtype, wtypes.WStructType)
        self.wtype: wtypes.WStructType = expr.wtype
        super().__init__(expr)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        if self.pytyp is not None:
            try:
                field_type = self.pytyp.fields[name]
            except KeyError as ex:
                raise CodeError(f"Invalid struct field: {name}", location) from ex
            field_expr = FieldExpression(location, field_type.wtype, self.expr, name)
            return builder_for_instance(field_type, field_expr)
        else:
            try:
                field_wtype = self.wtype.fields[name]
            except KeyError as ex:
                raise CodeError(f"Invalid struct field: {name}", location) from ex
            field_expr = FieldExpression(location, field_wtype, self.expr, name)
            return var_expression(field_expr)  # TODO: yeet me
