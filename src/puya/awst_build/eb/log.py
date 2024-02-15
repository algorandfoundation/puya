from __future__ import annotations

from typing import TYPE_CHECKING

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import (
    BytesConstant,
    BytesEncoding,
    Expression,
    IntrinsicCall,
    Literal,
    ReinterpretCast,
    UInt64Constant,
)
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import expect_operand_wtype
from puya.errors import CodeError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from puya.parse import SourceLocation


class LogBuilder(IntermediateExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        args_ = list(args)
        try:
            sep_index = arg_names.index("sep")
        except ValueError:
            sep: Expression = BytesConstant(value=b"", source_location=location)
        else:
            sep_arg = args_.pop(sep_index)
            match sep_arg:
                case Literal(value=str() as str_sep):
                    sep = BytesConstant(
                        value=str_sep.encode("utf8"),
                        encoding=BytesEncoding.utf8,
                        source_location=sep_arg.source_location,
                    )
                case _:
                    sep = expect_operand_wtype(sep_arg, wtypes.bytes_wtype)

        log_value: Expression | None = None
        for arg in args_:
            match arg:
                case ExpressionBuilder(value_type=wtypes.uint64_wtype):
                    bytes_expr = _itob(arg.rvalue(), arg.source_location)
                case Literal(value=int(int_literal)):
                    bytes_expr = _itob(
                        UInt64Constant(value=int_literal, source_location=arg.source_location),
                        arg.source_location,
                    )
                case ExpressionBuilder(value_type=wtypes.bytes_wtype):
                    bytes_expr = arg.rvalue()
                case ExpressionBuilder(value_type=wtypes.biguint_wtype):
                    bytes_expr = ReinterpretCast(
                        expr=arg.rvalue(),
                        wtype=wtypes.bytes_wtype,
                        source_location=arg.source_location,
                    )
                case Literal(value=bytes(bytes_literal)):
                    bytes_expr = BytesConstant(
                        value=bytes_literal, source_location=arg.source_location
                    )
                case Literal(value=str(str_literal)):
                    bytes_expr = BytesConstant(
                        value=str_literal.encode("utf8"), source_location=arg.source_location
                    )
                case ExpressionBuilder() as eb:
                    raise CodeError(
                        f"Unexpected argument type: {eb.value_type}", arg.source_location
                    )
                case Literal() as lit:
                    raise CodeError(
                        f"Unexpected argument type: {type(lit.value).__name__}",
                        arg.source_location,
                    )
                case _:
                    raise CodeError("Unexpected argument", arg.source_location)
            if log_value is None:
                log_value = bytes_expr
            elif sep:
                log_value = _concat(
                    _concat(log_value, sep, arg.source_location),
                    bytes_expr,
                    arg.source_location,
                )
            else:
                log_value = _concat(log_value, bytes_expr, arg.source_location)
        if log_value is None:
            log_value = BytesConstant(value=b"", source_location=location)
        return var_expression(
            IntrinsicCall(
                op_code="log",
                wtype=wtypes.void_wtype,
                stack_args=[log_value],
                source_location=location,
            )
        )


def _itob(expr: Expression, loc: SourceLocation) -> Expression:
    return IntrinsicCall(
        op_code="itob",
        wtype=wtypes.bytes_wtype,
        stack_args=[expr],
        source_location=loc,
    )


def _concat(a: Expression, b: Expression, loc: SourceLocation) -> Expression:
    return IntrinsicCall(
        op_code="concat",
        wtype=wtypes.bytes_wtype,
        stack_args=[a, b],
        source_location=loc,
    )
