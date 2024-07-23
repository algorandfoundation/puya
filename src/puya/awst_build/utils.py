import contextlib
import operator
import re
import typing
import warnings
from collections.abc import Callable, Iterator, Mapping, Sequence
from itertools import zip_longest

import mypy.build
import mypy.nodes
import mypy.types
from mypy.types import get_proper_type, is_named_instance

from puya import log
from puya.awst.nodes import ConstantValue
from puya.awst_build import constants, pytypes
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.eb.factories import builder_for_type
from puya.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
    TypeBuilder,
)
from puya.awst_build.exceptions import TypeUnionError
from puya.errors import CodeError, InternalError
from puya.models import ContractReference
from puya.parse import SourceLocation
from puya.utils import unique

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


@contextlib.contextmanager
def _log_warnings(location: SourceLocation) -> Iterator[None]:
    folding_warnings = []
    try:
        with warnings.catch_warnings(record=True, action="always") as folding_warnings:
            yield
    finally:
        for warning in folding_warnings:
            logger.warning(warning.message, location=location)


def fold_unary_expr(location: SourceLocation, op: str, expr: ConstantValue) -> ConstantValue:
    if not (func := UNARY_OPS.get(op)):
        raise InternalError(f"Unhandled unary operator: {op}", location)
    if op == "~" and isinstance(expr, int):
        logger.warning(
            "due to Python ints being signed, bitwise inversion yield a negative number",
            location=location,
        )
    try:
        with _log_warnings(location):
            result = func(expr)
    except Exception as ex:
        raise CodeError(str(ex), location) from ex
    if not isinstance(result, ConstantValue):
        raise CodeError(f"unsupported result type of {type(result).__name__}", location)
    return result


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
        with _log_warnings(location):
            result = func(lhs, rhs)
    except Exception as ex:
        raise CodeError(str(ex), location) from ex
    if not isinstance(result, ConstantValue):
        raise CodeError(f"unsupported result type of {type(result).__name__}", location)
    return result


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


TBuilder = typing.TypeVar("TBuilder", bound=NodeBuilder)


def get_arg_mapping(
    *,
    required_positional_names: Sequence[str] | None = None,
    optional_positional_names: Sequence[str] | None = None,
    required_kw_only: Sequence[str] | None = None,
    optional_kw_only: Sequence[str] | None = None,
    args: Sequence[TBuilder],
    arg_names: Sequence[str | None],
    call_location: SourceLocation,
    raise_on_missing: bool,
) -> tuple[dict[str, TBuilder], bool]:
    required_positional_names = required_positional_names or []
    optional_positional_names = optional_positional_names or []
    required_kw_only = required_kw_only or []
    optional_kw_only = optional_kw_only or []
    all_names = [
        *required_positional_names,
        *optional_positional_names,
        *required_kw_only,
        *optional_kw_only,
    ]
    if len(all_names) != len(set(all_names)):
        raise InternalError("duplicate names", call_location)

    arg_mapping = dict[str, TBuilder]()
    num_positionals = arg_names.count(None)
    positional_names = [*required_positional_names, *optional_positional_names]
    for positional_name, positional_arg in zip_longest(positional_names, args[:num_positionals]):
        if positional_name is None:
            logger.error("unexpected positional argument", location=positional_arg.source_location)
        elif positional_arg is None:
            break  # positional arguments could be named
        else:
            arg_mapping[positional_name] = positional_arg
    for arg_name, kw_arg in zip(arg_names[num_positionals:], args[num_positionals:], strict=True):
        if arg_name is None:
            # shouldn't be possible, might happen with type ignore?
            logger.error(
                "non-keyword argument appears after keywords", location=kw_arg.source_location
            )
        elif arg_name in arg_mapping:
            # again, shouldn't be possible, but might happen with type ignore?
            logger.error("duplicate argument name", location=kw_arg.source_location)
        elif arg_name not in all_names:
            logger.error("unrecognised keyword argument", location=kw_arg.source_location)
        else:
            arg_mapping[arg_name] = kw_arg
    any_missing = False
    if missing_args := set(required_positional_names).difference(arg_mapping.keys()):
        msg = f"missing required positional argument(s): {', '.join(sorted(missing_args))}"
        if raise_on_missing:
            raise CodeError(msg, call_location)
        any_missing = True
        logger.error(msg, location=call_location)
    elif missing_kwargs := set(required_kw_only).difference(arg_mapping.keys()):
        msg = f"missing required keyword argument(s): {', '.join(sorted(missing_kwargs))}"
        if raise_on_missing:
            raise CodeError(msg, call_location)
        any_missing = True
        logger.error(msg, location=call_location)
    return arg_mapping, any_missing


def snake_case(s: str) -> str:
    s = s.replace("-", " ")
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return re.sub(r"[-\s]", "_", s).lower()


def resolve_member_node(
    type_info: mypy.nodes.TypeInfo, name: str, location: SourceLocation
) -> mypy.nodes.SymbolNode | None:
    member = type_info.get(name)
    if member is None:
        return None
    if member.node is None:
        raise InternalError(
            "mypy cross reference remains unresolved:"
            f" member {name!r} of {type_info.fullname!r}",
            location,
        )
    return member.node


def symbol_node_is_function(
    node: mypy.nodes.SymbolNode,
) -> typing.TypeGuard[mypy.nodes.FuncBase | mypy.nodes.Decorator]:
    # matching types taken from mypy.nodes.TypeInfo.get_method
    return isinstance(node, mypy.nodes.FuncBase | mypy.nodes.Decorator)


def require_callable_type(
    node: mypy.nodes.FuncBase | mypy.nodes.Decorator, location: SourceLocation
) -> mypy.types.CallableType:
    if isinstance(node, mypy.nodes.Decorator):
        typ = node.var.type
    else:
        typ = node.type
    if typ is None:
        raise InternalError(f"unable to resolve type of {node.fullname}", location)
    if not isinstance(typ, mypy.types.CallableType):
        raise CodeError("expected a callable type", location)
    return typ


def maybe_resolve_literal(
    operand: TBuilder, target_type: pytypes.PyType
) -> TBuilder | InstanceBuilder:
    if not isinstance(operand, InstanceBuilder):
        return operand
    if operand.pytype != target_type:
        target_type_builder = builder_for_type(target_type, operand.source_location)
        if isinstance(target_type_builder, TypeBuilder):
            return operand.resolve_literal(target_type_builder)
    return operand


def resolve_literal(operand: InstanceBuilder, target_type: pytypes.PyType) -> InstanceBuilder:
    target_type_builder = builder_for_type(target_type, operand.source_location)
    assert isinstance(target_type_builder, TypeBuilder)
    return operand.resolve_literal(target_type_builder)


def determine_base_type(
    first: pytypes.PyType, *rest: pytypes.PyType, location: SourceLocation
) -> pytypes.PyType:
    operands = unique((first, *rest))
    if len(operands) == 1:
        return first
    for candidate in operands:
        if all(is_type_or_subtype(operand, of=candidate) for operand in operands):
            return candidate
    raise TypeUnionError(operands, location)


@typing.overload
def is_type_or_subtype(typ: pytypes.PyType | None, *, of: pytypes.PyType) -> bool: ...


@typing.overload
def is_type_or_subtype(
    typ: pytypes.PyType | None, *, of_any: Sequence[pytypes.PyType]
) -> bool: ...


def is_type_or_subtype(
    typ: pytypes.PyType | None,
    *,
    of: pytypes.PyType | None = None,
    of_any: Sequence[pytypes.PyType] | None = None,
) -> bool:
    if typ is None:
        return False
    if of is not None:
        target = of
        return typ == target or target in typ.mro
    else:
        assert of_any is not None
        targets = of_any
        return typ in targets or any(target in typ.mro for target in targets)
