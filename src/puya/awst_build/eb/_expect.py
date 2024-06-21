import typing
from collections.abc import Callable, Sequence
from itertools import zip_longest

from puya import log
from puya.awst_build import pytypes
from puya.awst_build.eb._utils import dummy_value
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puya.awst_build.utils import require_instance_builder
from puya.parse import SourceLocation

_T = typing.TypeVar("_T")

logger = log.get_logger(__name__)


def at_most_one_arg(
    args: Sequence[NodeBuilder], location: SourceLocation
) -> InstanceBuilder | None:
    if not args:
        return None
    eb, *extra = map(require_instance_builder, args)
    if extra:
        logger.error(f"expected at most 1 argument, got {len(args)}", location=location)
    return eb


def default_raise(msg: str, location: SourceLocation) -> typing.Never:
    from puya.errors import CodeError

    raise CodeError(msg, location)


def default_none(msg: str, location: SourceLocation) -> None:  # noqa: ARG001
    return None


def default_dummy_value(
    pytype: pytypes.PyType,
) -> Callable[[str, SourceLocation], InstanceBuilder]:
    assert not isinstance(pytype, pytypes.LiteralOnlyType)

    def defaulter(msg: str, location: SourceLocation) -> InstanceBuilder:  # noqa: ARG001
        return dummy_value(pytype, location)

    return defaulter


def at_least_one_arg(
    args: Sequence[NodeBuilder],
    location: SourceLocation,
    *,
    default: Callable[[str, SourceLocation], _T],
) -> tuple[InstanceBuilder | _T, Sequence[InstanceBuilder]]:
    if not args:
        msg = "expected at least 1 argument, got 0"
        result = default(msg, location)
        logger.error(msg, location=location)
        return result, []
    first, *rest = map(require_instance_builder, args)
    return first, rest


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
    eb, *extra = map(require_instance_builder, args)
    if extra:
        logger.error(f"expected 1 argument, got {len(args)}", location=location)
    return eb


def exactly_one_arg_of_type(
    args: Sequence[NodeBuilder],
    pytype: pytypes.PyType,
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
    if isinstance(first, InstanceBuilder) and first.pytype == pytype:
        return first
    msg = "unexpected argument type"
    result = default(msg, first.source_location)
    logger.error(msg, location=first.source_location)
    return result


def no_args(args: Sequence[NodeBuilder], location: SourceLocation) -> None:
    if args:
        logger.error(f"expected 0 arguments, got {len(args)}", location)


def exactly_n_args_of_type_else_dummy(
    args: Sequence[NodeBuilder], pytype: pytypes.PyType, location: SourceLocation, num_args: int
) -> Sequence[InstanceBuilder]:
    assert not isinstance(pytype, pytypes.LiteralOnlyType)

    if len(args) != num_args:
        logger.error(
            f"expected {num_args} argument{'' if num_args == 1 else 's'}, got {len(args)}",
            location=location,
        )
        dummy_args = [dummy_value(pytype, location)] * num_args
        args = [arg or default for arg, default in zip_longest(args, dummy_args)]
    arg_ebs = [argument_of_type_else_dummy(arg, pytype) for arg in args]
    return arg_ebs[:num_args]


def argument_of_type_else_dummy(
    builder: NodeBuilder, target_type: pytypes.PyType
) -> InstanceBuilder:
    assert not isinstance(target_type, pytypes.LiteralOnlyType)

    if isinstance(builder, InstanceBuilder) and builder.pytype == target_type:
        return builder
    logger.error("unexpected argument type", location=builder.source_location)
    return dummy_value(target_type, builder.source_location)


def argument_of_type_else_die(
    builder: NodeBuilder, target_type: pytypes.PyType
) -> InstanceBuilder:
    from puya.errors import CodeError

    if isinstance(builder, InstanceBuilder) and builder.pytype == target_type:
        return builder
    raise CodeError("unexpected argument type", builder.source_location)
