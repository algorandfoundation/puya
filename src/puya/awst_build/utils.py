import typing
from collections.abc import Iterable, Sequence
from typing import Iterator

import mypy.build
import mypy.nodes
import structlog
from mypy.types import get_proper_type, is_named_instance

from puya.awst import wtypes
from puya.awst.nodes import (
    AddressConstant,
    ARC4Encode,
    BoolConstant,
    BytesConstant,
    BytesEncoding,
    ConstantValue,
    ContractReference,
    Expression,
    IntegerConstant,
    Literal,
    ReinterpretCast,
    UInt64Constant,
)
from puya.awst_build import constants
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.eb.base import ExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.exceptions import UnsupportedASTError
from puya.errors import CodeError
from puya.parse import SourceLocation

logger = structlog.get_logger()


def extract_docstring(
    class_or_func_or_module: mypy.nodes.ClassDef | mypy.nodes.FuncDef | mypy.nodes.MypyFile,
) -> str | None:
    # extract docstring if specified
    docstring: str | None = None
    match class_or_func_or_module:
        case mypy.nodes.FuncDef() as func:
            mypy_body = func.body.body
        case mypy.nodes.ClassDef() as klass:
            mypy_body = klass.defs.body
        case mypy.nodes.MypyFile() as module:
            mypy_body = module.defs
        case _:
            raise TypeError(
                "Don't know how to extract docstring"
                f" from type {type(class_or_func_or_module).__name__}"
            )
    match mypy_body:
        case [mypy.nodes.ExpressionStmt(expr=mypy.nodes.StrExpr(value=docstring)), *_]:
            # TODO: maybe we actually want to pass here and just ignore/warn about any
            #       further ExpressionStmt(StrExpr())
            del mypy_body[0]
    return docstring


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


def fold_unary_expr(
    location: SourceLocation,
    op: str,
    expr: ConstantValue,
) -> ConstantValue:
    try:
        result = eval(
            f"{op} expr",
            {"expr": expr},
        )
    except Exception as ex:
        raise CodeError(str(ex), location) from ex
    if not isinstance(result, ConstantValue):  # type: ignore[arg-type,misc]
        raise UnsupportedASTError(
            location, details=f"unsupported result type of {type(result).__name__}"
        )
    assert isinstance(
        result, int | str | bytes | bool
    )  # TODO: why can't we use ConstantValue here?
    return result


def fold_binary_expr(
    location: SourceLocation,
    op: str,
    lhs: ConstantValue,
    rhs: ConstantValue,
) -> ConstantValue:
    try:
        result = eval(
            f"lhs {op} rhs",
            {"lhs": lhs, "rhs": rhs},
        )
    except Exception as ex:
        raise CodeError(str(ex), location) from ex
    if not isinstance(result, ConstantValue):  # type: ignore[arg-type,misc]
        raise UnsupportedASTError(
            location, details=f"unsupported result type of {type(result).__name__}"
        )
    assert isinstance(
        result, int | str | bytes | bool
    )  # TODO: why can't we use ConstantValue here?
    return result


def require_expression_builder(
    builder_or_expr_or_literal: ExpressionBuilder | Expression | Literal,
    *,
    msg: str = "A Python literal is not valid at this location",
) -> ExpressionBuilder:
    match builder_or_expr_or_literal:
        case Literal(value=bool(value), source_location=literal_location):
            return var_expression(BoolConstant(value=value, source_location=literal_location))
        case Literal(source_location=literal_location):
            raise CodeError(msg, literal_location)
        case Expression() as expr:
            return var_expression(expr)
    return builder_or_expr_or_literal


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
    literal_or_expr: Literal | Expression,
    target_wtype: wtypes.WType,
    loc: SourceLocation | None = None,
) -> Expression:
    ...


@typing.overload
def convert_literal(
    literal_or_expr: ExpressionBuilder,
    target_wtype: wtypes.WType,
    loc: SourceLocation | None = None,
) -> ExpressionBuilder:
    ...


def convert_literal(
    literal_or_expr: Literal | Expression | ExpressionBuilder,
    target_wtype: wtypes.WType,
    loc: SourceLocation | None = None,
) -> Expression | ExpressionBuilder:
    if not isinstance(literal_or_expr, Literal):
        return literal_or_expr

    literal_value: typing.Any = literal_or_expr.value
    loc = loc or literal_or_expr.source_location
    if not target_wtype.is_valid_literal(literal_value):
        raise CodeError(
            f"Cannot implicitly convert literal value {literal_value!r}"
            f" to target type {target_wtype}",
            loc,
        )
    match target_wtype:
        case wtypes.bool_wtype:
            return BoolConstant(value=literal_value, source_location=loc)
        case wtypes.uint64_wtype | wtypes.biguint_wtype | wtypes.ARC4UIntN():
            return IntegerConstant(value=literal_value, wtype=target_wtype, source_location=loc)
        case wtypes.bytes_wtype:
            try:
                literal_value.decode("utf8")
            except ValueError:
                encoding = BytesEncoding.unknown
            else:
                encoding = BytesEncoding.utf8
            return BytesConstant(value=literal_value, source_location=loc, encoding=encoding)
        case wtypes.account_wtype:
            return AddressConstant(value=literal_value, source_location=loc)
        case wtypes.arc4_dynamic_bytes:
            return ARC4Encode(
                value=BytesConstant(
                    value=literal_value,
                    source_location=loc,
                    encoding=BytesEncoding.utf8,
                ),
                source_location=loc,
                wtype=target_wtype,
            )
        case wtypes.arc4_string_wtype:
            if isinstance(literal_value, str):
                try:
                    literal_bytes = literal_value.encode("utf8")
                except ValueError:
                    pass
                else:
                    return ARC4Encode(
                        value=BytesConstant(
                            value=literal_bytes,
                            source_location=loc,
                            encoding=BytesEncoding.utf8,
                        ),
                        source_location=loc,
                        wtype=target_wtype,
                    )
        case wtypes.arc4_bool_wtype:
            return ARC4Encode(
                value=BoolConstant(
                    value=literal_value,
                    source_location=loc,
                ),
                source_location=loc,
                wtype=target_wtype,
            )
        case wtypes.ARC4UIntN():
            return ARC4Encode(
                value=UInt64Constant(
                    value=literal_value,
                    source_location=loc,
                ),
                source_location=loc,
                wtype=target_wtype,
            )
        case wtypes.asset_wtype | wtypes.application_wtype:
            return ReinterpretCast(
                expr=UInt64Constant(value=literal_value, source_location=loc),
                wtype=target_wtype,
                source_location=loc,
            )
        case wtypes.account_wtype:
            return ReinterpretCast(
                expr=BytesConstant(value=literal_value, source_location=loc),
                wtype=target_wtype,
                source_location=loc,
            )
    raise CodeError(f"Can't construct {target_wtype} from Python literal {literal_value}", loc)


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
    if isinstance(builder_or_literal, ExpressionBuilder):
        return builder_or_literal.bool_eval(location=loc, negate=negate)
    constant_value = bool(builder_or_literal.value)
    if negate:
        constant_value = not constant_value
    return var_expression(BoolConstant(value=constant_value, source_location=loc))


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
    for arg_idx, (supplied_arg_name, arg) in enumerate(args):
        if supplied_arg_name is not None:
            arg_name = supplied_arg_name
        else:
            try:
                arg_name = positional_arg_names[arg_idx]
            except IndexError as ex:
                raise CodeError("Too many positional arguments", location) from ex
        arg_mapping[arg_name] = arg
    return arg_mapping
