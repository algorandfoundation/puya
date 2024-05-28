from __future__ import annotations

import typing

import mypy.nodes

from puya.awst import wtypes
from puya.awst.nodes import (
    BytesConstant,
    BytesEncoding,
    Expression,
    Literal,
    ReinterpretCast,
    UInt64Constant,
)
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb.base import ExpressionBuilder, FunctionBuilder
from puya.awst_build.eb.void import VoidExpressionBuilder
from puya.awst_build.utils import expect_operand_type
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from puya.parse import SourceLocation


class LogBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        args_ = list(args)
        try:
            sep_index = arg_names.index("sep")
        except ValueError:
            sep: Expression = BytesConstant(
                value=b"", encoding=BytesEncoding.utf8, source_location=location
            )
        else:
            sep_arg = args_.pop(sep_index)
            match sep_arg:
                case Literal(value=str() as str_sep):
                    sep = BytesConstant(
                        value=str_sep.encode("utf8"),
                        encoding=BytesEncoding.utf8,
                        source_location=sep_arg.source_location,
                    )
                case ExpressionBuilder(pytype=pytypes.StringType) as eb:
                    sep = ReinterpretCast(
                        expr=eb.rvalue(),
                        wtype=wtypes.bytes_wtype,
                        source_location=eb.source_location,
                    )
                case _:
                    sep = expect_operand_type(sep_arg, pytypes.BytesType).rvalue()

        log_value: Expression | None = None
        for arg in args_:
            match arg:
                case ExpressionBuilder(pytype=pytypes.UInt64Type):
                    bytes_expr: Expression = intrinsic_factory.itob(
                        arg.rvalue(), arg.source_location
                    )
                case ExpressionBuilder() as eb:
                    bytes_expr = eb.rvalue()
                case Literal(value=int(int_literal)):
                    bytes_expr = intrinsic_factory.itob(
                        UInt64Constant(value=int_literal, source_location=arg.source_location),
                        arg.source_location,
                    )
                case Literal(value=bytes(bytes_literal)):
                    bytes_expr = BytesConstant(
                        value=bytes_literal,
                        encoding=BytesEncoding.unknown,
                        source_location=arg.source_location,
                    )
                case Literal(value=str(str_literal)):
                    bytes_expr = BytesConstant(
                        value=str_literal.encode("utf8"),
                        encoding=BytesEncoding.utf8,
                        source_location=arg.source_location,
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
            else:
                log_value = intrinsic_factory.concat(
                    intrinsic_factory.concat(log_value, sep, arg.source_location),
                    bytes_expr,
                    arg.source_location,
                )
        if log_value is None:
            log_value = BytesConstant(
                value=b"", encoding=BytesEncoding.utf8, source_location=location
            )
        return VoidExpressionBuilder(intrinsic_factory.log(log_value, location))
