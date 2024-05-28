from __future__ import annotations

import typing

import mypy.nodes

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import BoolConstant, Expression, Literal, ReinterpretCast
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb.base import ExpressionBuilder
from puya.awst_build.eb.bool import BoolExpressionBuilder
from puya.awst_build.eb.bytes import BytesExpressionBuilder
from puya.awst_build.eb.var_factory import builder_for_type
from puya.awst_build.utils import expect_operand_wtype
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def bool_eval_to_constant(
    *, value: bool, location: SourceLocation, negate: bool = False
) -> ExpressionBuilder:
    if negate:
        value = not value
    logger.warning(f"expression is always {value}", location=location)
    const = BoolConstant(value=value, source_location=location)
    return BoolExpressionBuilder(const)


def uint64_to_biguint(arg_in: ExpressionBuilder | Literal, location: SourceLocation) -> Expression:
    arg = expect_operand_wtype(arg_in, wtypes.uint64_wtype)

    return intrinsic_factory.itob_as(
        arg,
        wtypes.biguint_wtype,
        location,
    )


def get_bytes_expr(expr: Expression) -> ReinterpretCast:
    return ReinterpretCast(
        expr=expr, wtype=wtypes.bytes_wtype, source_location=expr.source_location
    )


def get_bytes_expr_builder(expr: Expression) -> ExpressionBuilder:
    return BytesExpressionBuilder(get_bytes_expr(expr))


def construct_from_builder_or_literal(
    literal_or_builder: Literal | ExpressionBuilder,
    target_type: pytypes.PyType,
    loc: SourceLocation | None = None,
) -> ExpressionBuilder:
    loc = loc or literal_or_builder.source_location
    if (
        isinstance(literal_or_builder, ExpressionBuilder)
        and literal_or_builder.pytype == target_type
    ):
        return literal_or_builder
    return _construct_instance(target_type, literal_or_builder, loc)


def construct_from_literal(
    literal: Literal, target_type: pytypes.PyType, loc: SourceLocation | None = None
) -> ExpressionBuilder:
    loc = loc or literal.source_location
    return _construct_instance(target_type, literal, loc)


def _construct_instance(
    target_type: pytypes.PyType, arg: ExpressionBuilder | Literal, location: SourceLocation
) -> ExpressionBuilder:
    builder = builder_for_type(target_type, location)
    if isinstance(arg, ExpressionBuilder):
        arg_type = arg.pytype
        if arg_type is None:  # TODO: remove once EB heirarchy is fixed
            raise CodeError("bad expression type", arg.source_location)
    else:
        arg_type = _get_literal_type(arg)
    return builder.call(
        args=[arg],
        arg_typs=[arg_type],
        arg_kinds=[mypy.nodes.ARG_POS],
        arg_names=[None],
        location=location,
    )


def _get_literal_type(literal: Literal) -> pytypes.PyType:
    match literal.value:
        case int():
            arg_type = pytypes.IntLiteralType
        case str():
            arg_type = pytypes.StrLiteralType
        case bytes():
            arg_type = pytypes.BytesLiteralType
        case bool():
            arg_type = pytypes.BoolType
        case _:
            typing.assert_never(literal.value)
    return arg_type
