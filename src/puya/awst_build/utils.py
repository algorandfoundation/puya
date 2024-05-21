import operator
import re
import typing
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence

import mypy.build
import mypy.nodes
import mypy.types
from mypy.types import get_proper_type, is_named_instance

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    AddressConstant,
    BoolConstant,
    BytesConstant,
    BytesEncoding,
    ConstantValue,
    ContractReference,
    Expression,
    IntegerConstant,
    Literal,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
    SingleEvaluation,
    StringConstant,
    UInt64BinaryOperation,
    UInt64BinaryOperator,
    UInt64Constant,
)
from puya.awst_build import constants, intrinsic_factory
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.eb.base import ExpressionBuilder
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def refers_to_fullname(ref_expr: mypy.nodes.RefExpr, *fullnames: str) -> bool:
    """Is node a name or member expression with the given full name?"""
    if isinstance(ref_expr.node, mypy.nodes.TypeAlias):
        return is_named_instance(ref_expr.node.target, fullnames)
    else:
        return ref_expr.fullname in fullnames


def get_unaliased_fullname(ref_expr: mypy.nodes.RefExpr) -> str:
    alias = get_aliased_instance(ref_expr)
    if alias:
        return alias.type.fullname
    return ref_expr.fullname


def get_aliased_instance(ref_expr: mypy.nodes.RefExpr) -> mypy.types.Instance | None:
    if isinstance(ref_expr.node, mypy.nodes.TypeAlias):
        t = get_proper_type(ref_expr.node.target)
        if isinstance(t, mypy.types.Instance):
            return t
        if (
            isinstance(t, mypy.types.TupleType)
            and t.partial_fallback.type.fullname != "builtins.tuple"
        ):
            return t.partial_fallback
    return None


def get_decorators_by_fullname(
    ctx: ASTConversionModuleContext,
    decorator: mypy.nodes.Decorator,
) -> dict[str, mypy.nodes.Expression]:
    result = dict[str, mypy.nodes.Expression]()
    for d in decorator.decorators:
        if isinstance(d, mypy.nodes.RefExpr):
            full_name = get_unaliased_fullname(d)
            result[get_unaliased_fullname(d)] = d
        elif isinstance(d, mypy.nodes.CallExpr) and isinstance(d.callee, mypy.nodes.RefExpr):
            full_name = get_unaliased_fullname(d.callee)
        else:
            raise CodeError("Unsupported decorator usage", ctx.node_location(d))
        result[full_name] = d
    return result


UNARY_OPS: typing.Final[Mapping[str, Callable[[typing.Any], typing.Any]]] = {
    "~": operator.inv,
    "not": operator.not_,
    "+": operator.pos,
    "-": operator.neg,
}


def fold_unary_expr(location: SourceLocation, op: str, expr: ConstantValue) -> ConstantValue:
    if not (func := UNARY_OPS.get(op)):
        raise InternalError(f"Unhandled unary operator: {op}", location)
    try:
        result = func(expr)
    except Exception as ex:
        raise CodeError(str(ex), location) from ex
    # for some reason mypy doesn't support type-aliases to unions in isinstance checks,
    # so we have to suppress the error and do a typing.cast instead
    if not isinstance(result, ConstantValue):  # type: ignore[arg-type,misc]
        raise CodeError(f"unsupported result type of {type(result).__name__}", location)
    return typing.cast(ConstantValue, result)


BINARY_OPS: typing.Final[Mapping[str, Callable[[typing.Any, typing.Any], typing.Any]]] = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "@": operator.matmul,
    "/": operator.truediv,
    "%": operator.mod,
    "**": operator.pow,
    "<<": operator.lshift,
    ">>": operator.rshift,
    "|": operator.or_,
    "^": operator.xor,
    "&": operator.and_,
    "//": operator.floordiv,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    ">=": operator.ge,
    "<=": operator.le,
    "!=": operator.ne,
    "is": operator.is_,
    "is not": operator.is_not,
    "in": lambda a, b: a in b,
    "not in": lambda a, b: a not in b,
    "and": lambda a, b: a and b,
    "or": lambda a, b: a or b,
}


def fold_binary_expr(
    location: SourceLocation,
    op: str,
    lhs: ConstantValue,
    rhs: ConstantValue,
) -> ConstantValue:
    if not (func := BINARY_OPS.get(op)):
        raise InternalError(f"Unhandled binary operator: {op}", location)
    try:
        result = func(lhs, rhs)
    except Exception as ex:
        raise CodeError(str(ex), location) from ex
    # for some reason mypy doesn't support type-aliases to unions in isinstance checks,
    # so we have to suppress the error and do a typing.cast instead
    if not isinstance(result, ConstantValue):  # type: ignore[arg-type,misc]
        raise CodeError(f"unsupported result type of {type(result).__name__}", location)
    return typing.cast(ConstantValue, result)


def require_expression_builder(
    builder_or_literal: ExpressionBuilder | Literal,
    *,
    msg: str = "A Python literal is not valid at this location",
) -> ExpressionBuilder:
    from puya.awst_build.eb.bool import BoolExpressionBuilder

    match builder_or_literal:
        case Literal(value=bool(value), source_location=literal_location):
            return BoolExpressionBuilder(
                BoolConstant(value=value, source_location=literal_location)
            )
        case Literal(source_location=literal_location):
            raise CodeError(msg, literal_location)
        case ExpressionBuilder() as builder:
            return builder
        case _:
            typing.assert_never(builder_or_literal)


def expect_operand_wtype(
    literal_or_expr: Literal | Expression | ExpressionBuilder, target_wtype: wtypes.WType
) -> Expression:
    if isinstance(literal_or_expr, ExpressionBuilder):
        literal_or_expr = literal_or_expr.rvalue()

    if isinstance(literal_or_expr, Expression):
        if literal_or_expr.wtype != target_wtype:
            raise CodeError(
                f"Expected type {target_wtype}, got type {literal_or_expr.wtype}",
                literal_or_expr.source_location,
            )
        return literal_or_expr
    else:
        return convert_literal(literal_or_expr, target_wtype)


@typing.overload
def convert_literal(
    literal_or_expr: Literal | Expression, target_wtype: wtypes.WType
) -> Expression: ...


@typing.overload
def convert_literal(
    literal_or_expr: ExpressionBuilder, target_wtype: wtypes.WType
) -> ExpressionBuilder: ...


def convert_literal(
    literal_or_expr: Literal | Expression | ExpressionBuilder, target_wtype: wtypes.WType
) -> Expression | ExpressionBuilder:
    if not isinstance(literal_or_expr, Literal):
        return literal_or_expr

    loc = literal_or_expr.source_location
    match literal_or_expr.value, target_wtype:
        case bool(bool_value), wtypes.bool_wtype:
            return BoolConstant(value=bool_value, source_location=loc)
        case int(int_value), wtypes.uint64_wtype | wtypes.biguint_wtype:
            return IntegerConstant(value=int_value, wtype=target_wtype, source_location=loc)
        case bytes(bytes_value), wtypes.bytes_wtype:
            try:
                # TODO: YEET ME
                bytes_value.decode("utf8")
            except ValueError:
                encoding = BytesEncoding.unknown
            else:
                encoding = BytesEncoding.utf8
            return BytesConstant(value=bytes_value, encoding=encoding, source_location=loc)
        case str(str_value), wtypes.bytes_wtype:
            return BytesConstant(
                value=str_value.encode("utf8"), encoding=BytesEncoding.utf8, source_location=loc
            )
        case str(str_value), wtypes.string_wtype:
            return StringConstant(value=str_value, source_location=loc)
        case str(str_value), wtypes.account_wtype:
            return AddressConstant(value=str_value, source_location=loc)
        case int(int_value), wtypes.asset_wtype | wtypes.application_wtype:
            return ReinterpretCast(
                expr=UInt64Constant(value=int_value, source_location=loc),
                wtype=target_wtype,
                source_location=loc,
            )
    raise CodeError(
        f"Can't construct {target_wtype} from Python literal {literal_or_expr.value!r}", loc
    )


def convert_literal_to_expr(
    literal_or_expr: Literal | Expression | ExpressionBuilder, target_wtype: wtypes.WType
) -> Expression:
    expr_or_builder = convert_literal(literal_or_expr, target_wtype)
    if isinstance(expr_or_builder, ExpressionBuilder):
        return expr_or_builder.rvalue()  # TODO: move away from rvalue/lvaue in utility functions
    return expr_or_builder


def bool_eval(
    builder_or_literal: ExpressionBuilder | Literal, loc: SourceLocation, *, negate: bool = False
) -> ExpressionBuilder:
    from puya.awst_build.eb.bool import BoolExpressionBuilder

    if isinstance(builder_or_literal, ExpressionBuilder):
        return builder_or_literal.bool_eval(location=loc, negate=negate)
    constant_value = bool(builder_or_literal.value)
    if negate:
        constant_value = not constant_value
    # TODO: PyType known as bool
    return BoolExpressionBuilder(BoolConstant(value=constant_value, source_location=loc))


def iterate_user_bases(type_info: mypy.nodes.TypeInfo) -> Iterator[mypy.nodes.TypeInfo]:
    assert type_info.mro[0].defn is type_info.defn, "first MRO entry should always be class itself"
    for base_type in type_info.mro[1:]:
        base_class_fullname = base_type.fullname
        if base_class_fullname in (
            *constants.CONTRACT_STUB_TYPES,
            "builtins.object",
            "abc.ABC",
        ):
            continue  # OK, ignore, just stubs
        else:
            yield base_type


def qualified_class_name(info: mypy.nodes.TypeInfo) -> ContractReference:
    # we don't support nested classes just yet, but this is easy enough to do now
    module_name = info.module_name
    qual_name = info.fullname.removeprefix(module_name + ".")
    return ContractReference(module_name=module_name, class_name=qual_name)


def extract_bytes_literal_from_mypy(expr: mypy.nodes.BytesExpr) -> bytes:
    import ast

    bytes_str = expr.value
    # mypy doesn't preserve the value of the quotes, need to reverse it
    if '"' in bytes_str:
        bytes_literal = "b'" + bytes_str + "'"
    else:
        bytes_literal = 'b"' + bytes_str + '"'
    bytes_const: bytes = ast.literal_eval(bytes_literal)
    return bytes_const


T = typing.TypeVar("T")


def get_arg_mapping(
    positional_arg_names: Sequence[str],
    args: Iterable[tuple[str | None, T]],
    location: SourceLocation,
) -> dict[str, T]:
    arg_mapping = dict[str, T]()
    has_too_many_error = False
    for arg_idx, (supplied_arg_name, arg) in enumerate(args):
        if supplied_arg_name is not None:
            arg_name = supplied_arg_name
        else:
            try:
                arg_name = positional_arg_names[arg_idx]
            except IndexError:
                if not has_too_many_error:
                    logger.error(  # noqa: TRY400
                        "Too many positional arguments", location=location
                    )
                    has_too_many_error = True
                continue
        arg_mapping[arg_name] = arg
    return arg_mapping


def snake_case(s: str) -> str:
    s = s.replace("-", " ")
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return re.sub(r"[-\s]", "_", s).lower()


def eval_slice_component(
    len_expr: Expression, val: ExpressionBuilder | Literal | None, location: SourceLocation
) -> Expression | None:
    if val is None:
        return None

    if isinstance(val, ExpressionBuilder):
        # no negatives to deal with here, easy
        index_expr = expect_operand_wtype(val, wtypes.uint64_wtype)
        temp_index = SingleEvaluation(index_expr)
        return intrinsic_factory.select(
            false=len_expr,
            true=temp_index,
            condition=NumericComparisonExpression(
                lhs=temp_index,
                operator=NumericComparison.lt,
                rhs=len_expr,
                source_location=location,
            ),
            loc=location,
        )

    int_lit = val.value
    if not isinstance(int_lit, int):
        raise CodeError(f"Invalid literal for slicing: {int_lit!r}", val.source_location)
    # take the min of abs(int_lit) and len(self.expr)
    abs_lit_expr = UInt64Constant(value=abs(int_lit), source_location=val.source_location)
    trunc_value_expr = intrinsic_factory.select(
        false=len_expr,
        true=abs_lit_expr,
        condition=NumericComparisonExpression(
            lhs=abs_lit_expr,
            operator=NumericComparison.lt,
            rhs=len_expr,
            source_location=location,
        ),
        loc=location,
    )
    return (
        trunc_value_expr
        if int_lit >= 0
        else UInt64BinaryOperation(
            left=len_expr,
            op=UInt64BinaryOperator.sub,
            right=trunc_value_expr,
            source_location=location,
        )
    )


def resolve_method_from_type_info(
    type_info: mypy.nodes.TypeInfo, name: str, location: SourceLocation
) -> mypy.nodes.FuncBase | mypy.nodes.Decorator | None:
    """Get a function member from TypeInfo, or return None.

    Differs from TypeInfo.get_method() if there are conflicting definitions of name,
    one being a method and another being an attribute.
    This is important for semantic compatibility.

    If the found member is not a function, an exception is raised.
    Also raises if the SymbolTableNode is unresolved (it shouldn't be once we can see it).
    """
    member = type_info.get(name)
    if member is None:
        return None
    match member.node:
        case None:
            raise InternalError(
                "mypy cross reference remains unresolved:"
                f" member {name!r} of {type_info.fullname!r}",
                location,
            )
        # matching types taken from mypy.nodes.TypeInfo.get_method
        case mypy.nodes.FuncBase() | mypy.nodes.Decorator() as func_or_dec:
            return func_or_dec
        case other_node:
            logger.debug(
                f"Non-function member: type={type(other_node).__name__!r}, value={other_node}",
                location=location,
            )
            raise CodeError(f"unsupported reference to non-function member {name!r}", location)
