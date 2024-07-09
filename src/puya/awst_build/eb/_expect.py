import typing
from collections.abc import Callable, Sequence
from itertools import zip_longest

from puya import log
from puya.awst_build import pytypes
from puya.awst_build.eb._utils import dummy_value
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puya.awst_build.utils import is_type_or_subtype, maybe_resolve_literal
from puya.parse import SourceLocation

_T = typing.TypeVar("_T")
_TBuilder = typing.TypeVar("_TBuilder", bound=NodeBuilder)

logger = log.get_logger(__name__)


def at_most_one_arg(
    args: Sequence[NodeBuilder], location: SourceLocation
) -> InstanceBuilder | None:
    if not args:
        return None
    first, *rest = args
    if rest:
        logger.error(f"expected at most 1 argument, got {len(args)}", location=location)
    return instance_builder(first, default=default_none)


def at_most_one_arg_of_type(
    args: Sequence[NodeBuilder], valid_types: Sequence[pytypes.PyType], location: SourceLocation
) -> InstanceBuilder | None:
    if not args:
        return None
    first, *rest = args
    if rest:
        logger.error(f"expected at most 1 argument, got {len(args)}", location=location)
    if isinstance(first, InstanceBuilder) and is_type_or_subtype(first.pytype, of_any=valid_types):
        return first
    logger.error("unexpected argument type", location=first.source_location)
    return None


def default_raise(msg: str, location: SourceLocation) -> typing.Never:
    from puya.errors import CodeError

    raise CodeError(msg, location)


def default_fixed_value(value: _T) -> Callable[[str, SourceLocation], _T]:
    def defaulter(msg: str, location: SourceLocation) -> _T:  # noqa: ARG001
        return value

    return defaulter


default_none: typing.Final = default_fixed_value(None)


def default_dummy_value(
    pytype: pytypes.PyType,
) -> Callable[[str, SourceLocation], InstanceBuilder]:
    assert not isinstance(pytype, pytypes.LiteralOnlyType)

    def defaulter(msg: str, location: SourceLocation) -> InstanceBuilder:  # noqa: ARG001
        return dummy_value(pytype, location)

    return defaulter


def at_least_one_arg(
    args: Sequence[_TBuilder],
    location: SourceLocation,
    *,
    default: Callable[[str, SourceLocation], _T],
) -> tuple[InstanceBuilder | _T, Sequence[_TBuilder]]:
    if not args:
        msg = "expected at least 1 argument, got 0"
        result = default(msg, location)
        logger.error(msg, location=location)
        return result, []
    first, *rest = args
    return instance_builder(first, default=default), rest


def exactly_one_arg(
    args: Sequence[NodeBuilder],
    location: SourceLocation,
    *,
    default: Callable[[str, SourceLocation], _T],
) -> InstanceBuilder | _T:
    if not args:
        msg = "expected 1 argument, got 0"
        result = default(msg, location)
        logger.error(msg, location=location)
        return result
    first, *rest = args
    if rest:
        logger.error(f"expected 1 argument, got {len(args)}", location=location)
    return instance_builder(first, default=default)


def exactly_one_arg_of_type(
    args: Sequence[NodeBuilder],
    pytype: pytypes.PyType,
    location: SourceLocation,
    *,
    default: Callable[[str, SourceLocation], _T],
    resolve_literal: bool = False,
) -> InstanceBuilder | _T:
    if not args:
        msg = "expected 1 argument, got 0"
        result = default(msg, location)
        logger.error(msg, location=location)
        return result
    first, *rest = args
    if rest:
        logger.error(f"expected 1 argument, got {len(args)}", location=location)
    if resolve_literal:
        first = maybe_resolve_literal(first, pytype)
    if isinstance(first, InstanceBuilder) and is_type_or_subtype(first.pytype, of=pytype):
        return first
    msg = "unexpected argument type"
    result = default(msg, first.source_location)
    logger.error(msg, location=first.source_location)
    return result


def exactly_one_arg_of_type_else_dummy(
    args: Sequence[NodeBuilder],
    pytype: pytypes.PyType,
    location: SourceLocation,
    *,
    resolve_literal: bool = False,
) -> InstanceBuilder:
    assert not isinstance(pytype, pytypes.LiteralOnlyType)

    return exactly_one_arg_of_type(
        args,
        pytype,
        location,
        default=default_dummy_value(pytype),
        resolve_literal=resolve_literal,
    )


def no_args(args: Sequence[NodeBuilder], location: SourceLocation) -> None:
    if args:
        logger.error(f"expected 0 arguments, got {len(args)}", location=location)


def exactly_n_args_of_type_else_dummy(
    args: Sequence[NodeBuilder], pytype: pytypes.PyType, location: SourceLocation, num_args: int
) -> Sequence[InstanceBuilder]:
    assert not isinstance(pytype, pytypes.LiteralOnlyType)

    if not exactly_n_args(args, location, num_args):
        dummy_args = [dummy_value(pytype, location)] * num_args
        args = [arg or default for arg, default in zip_longest(args, dummy_args)]
    arg_ebs = [argument_of_type_else_dummy(arg, pytype) for arg in args]
    return arg_ebs[:num_args]


def exactly_n_args(args: Sequence[NodeBuilder], location: SourceLocation, num_args: int) -> bool:
    if len(args) == num_args:
        return True
    logger.error(
        f"expected {num_args} argument{'' if num_args == 1 else 's'}, got {len(args)}",
        location=location,
    )
    return False


def argument_of_type(
    builder: NodeBuilder,
    target_type: pytypes.PyType,
    *additional_types: pytypes.PyType,
    resolve_literal: bool = False,
    default: Callable[[str, SourceLocation], _T],
) -> InstanceBuilder | _T:
    if resolve_literal:
        builder = maybe_resolve_literal(builder, target_type)

    if isinstance(builder, InstanceBuilder) and is_type_or_subtype(
        builder.pytype, of_any=(target_type, *additional_types)
    ):
        return builder
    msg = "unexpected argument type"
    result = default(msg, builder.source_location)
    logger.error(msg, location=builder.source_location)
    return result


def argument_of_type_else_dummy(
    builder: NodeBuilder,
    target_type: pytypes.PyType,
    *additional_types: pytypes.PyType,
    resolve_literal: bool = False,
) -> InstanceBuilder:
    return argument_of_type(
        builder,
        target_type,
        *additional_types,
        resolve_literal=resolve_literal,
        default=default_dummy_value(target_type),
    )


def simple_string_literal(
    builder: NodeBuilder,
    *,
    default: Callable[[str, SourceLocation], _T],
) -> str | _T:
    from puya.awst_build.eb.interface import LiteralBuilder

    match builder:
        case LiteralBuilder(value=str(value)):
            return value
        case InstanceBuilder(pytype=pytypes.StrLiteralType):
            msg = "argument must be a simple str literal"
        case _:
            msg = "unexpected argument type"
    result = default(msg, builder.source_location)
    logger.error(msg, location=builder.source_location)
    return result


def instance_builder(
    builder: NodeBuilder, *, default: Callable[[str, SourceLocation], _T]
) -> InstanceBuilder | _T:
    if isinstance(builder, InstanceBuilder):
        return builder
    msg = "expression is not a value"
    result = default(msg, builder.source_location)
    logger.error(msg, location=builder.source_location)
    return result
