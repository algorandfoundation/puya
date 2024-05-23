from __future__ import annotations

import typing

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import Expression, FieldExpression, Literal, NewStruct
from puya.awst_build import pytypes
from puya.awst_build.eb._utils import bool_eval_to_constant, get_bytes_expr_builder
from puya.awst_build.eb.arc4.base import CopyBuilder, arc4_compare_bytes
from puya.awst_build.eb.base import BuilderComparisonOp, ExpressionBuilder, ValueExpressionBuilder
from puya.awst_build.eb.bytes_backed import BytesBackedClassExpressionBuilder
from puya.awst_build.eb.var_factory import builder_for_instance, var_expression
from puya.awst_build.utils import get_arg_mapping, require_expression_builder
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation


logger = log.get_logger(__name__)


class ARC4StructClassExpressionBuilder(BytesBackedClassExpressionBuilder[wtypes.ARC4Struct]):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.StructType)
        # assert pytypes.ARC4StructBaseType in typ.mro TODO?
        wtype = typ.wtype
        assert isinstance(wtype, wtypes.ARC4Struct)
        super().__init__(wtype, location)

    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        wtype = self.produces()
        ordered_field_names = wtype.names
        field_mapping = get_arg_mapping(
            positional_arg_names=ordered_field_names,
            args=zip(arg_names, args, strict=True),
            location=location,
        )

        values = dict[str, Expression]()
        for field_name, field_type in wtype.fields.items():
            field_value = field_mapping.pop(field_name, None)
            if field_value is None:
                raise CodeError(f"Missing required argument {field_name}", location)
            field_expr = require_expression_builder(field_value).rvalue()
            if field_expr.wtype != field_type:
                raise CodeError("Invalid type for field", field_expr.source_location)
            values[field_name] = field_expr
        if field_mapping:
            raise CodeError(f"Unexpected keyword arguments: {' '.join(field_mapping)}", location)

        return ARC4StructExpressionBuilder(
            NewStruct(wtype=wtype, values=values, source_location=location)
        )


class ARC4StructExpressionBuilder(ValueExpressionBuilder):
    def __init__(self, expr: Expression, typ: pytypes.PyType | None = None):  # TODO
        if typ is not None:
            assert isinstance(typ, pytypes.StructType)
        self.pytyp = typ
        assert isinstance(expr.wtype, wtypes.ARC4Struct)
        self.wtype: wtypes.ARC4Struct = expr.wtype
        super().__init__(expr)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case field_name if self.pytyp and (field := self.pytyp.fields.get(field_name)):
                result_expr = FieldExpression(
                    base=self.expr,
                    name=field_name,
                    wtype=field.wtype,
                    source_location=location,
                )
                return builder_for_instance(field, result_expr)
            case field_name if field_name in self.wtype.fields:
                return var_expression(  # TODO: yeet me
                    FieldExpression(
                        source_location=location,
                        base=self.expr,
                        name=field_name,
                        wtype=self.wtype.fields[field_name],
                    )
                )
            case "bytes":
                return get_bytes_expr_builder(self.expr)
            case "copy":
                return CopyBuilder(self.expr, location, self.pytyp)
            case _:
                return super().member_access(name, location)

    def compare(
        self, other: ExpressionBuilder | Literal, op: BuilderComparisonOp, location: SourceLocation
    ) -> ExpressionBuilder:
        return arc4_compare_bytes(self, op, other, location)

    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> ExpressionBuilder:
        return bool_eval_to_constant(value=True, location=location, negate=negate)
