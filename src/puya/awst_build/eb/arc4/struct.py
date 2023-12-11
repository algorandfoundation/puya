from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from puya.awst import wtypes
from puya.awst.nodes import (
    ARC4Encode,
    Expression,
    IndexExpression,
    Literal,
    TupleExpression,
    UInt64Constant,
)
from puya.awst_build.eb.arc4.base import get_bytes_expr_builder
from puya.awst_build.eb.base import ValueExpressionBuilder
from puya.awst_build.eb.bytes_backed import BytesBackedClassExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import expect_operand_wtype, get_arg_mapping
from puya.errors import CodeError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.awst_build.eb.base import (
        ExpressionBuilder,
    )
    from puya.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


class ARC4StructClassExpressionBuilder(BytesBackedClassExpressionBuilder):
    def produces(self) -> wtypes.WType:
        return self.wtype

    def __init__(
        self,
        wtype: wtypes.ARC4Struct,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.wtype = wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        ordered_field_names = self.wtype.names
        field_mapping = get_arg_mapping(
            positional_arg_names=ordered_field_names,
            args=zip(arg_names, args, strict=True),
            location=location,
        )

        args_positioned = list[Expression]()
        for field_name, field_type in self.wtype.fields.items():
            field_value = field_mapping.pop(field_name, None)
            if field_value is None:
                raise CodeError(f"Missing required argument {field_name}", location)
            args_positioned.append(expect_operand_wtype(field_value, field_type))
        if field_mapping:
            raise CodeError(f"Unexpected keyword arguments: {' '.join(field_mapping)}", location)

        tuple_expr = TupleExpression(
            items=args_positioned,
            source_location=location,
            wtype=wtypes.WTuple.from_types(types=self.wtype.types),
        )

        return var_expression(
            ARC4Encode(wtype=self.wtype, value=tuple_expr, source_location=location)
        )


class ARC4StructExpressionBuilder(ValueExpressionBuilder):
    def __init__(self, expr: Expression):
        assert isinstance(expr.wtype, wtypes.ARC4Struct)
        self.wtype: wtypes.ARC4Struct = expr.wtype
        super().__init__(expr)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        match name:
            case tuple_field if tuple_field in self.wtype.fields:
                index = self.wtype.names.index(tuple_field)
                return var_expression(
                    IndexExpression(
                        source_location=location,
                        base=self.expr,
                        index=UInt64Constant(value=index, source_location=location),
                        wtype=self.wtype.fields[tuple_field],
                    )
                )
            case "bytes":
                return get_bytes_expr_builder(self.expr)
            case _:
                return super().member_access(name, location)
