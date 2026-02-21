import typing
from collections.abc import Sequence

from puya import log
from puya.awst.nodes import AssertExpression
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puyapy.awst_build.utils import get_arg_mapping

logger = log.get_logger(__name__)

_VALID_PREFIXES = frozenset(("AER", "ERR"))


class LoggedAssertFunctionBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg_mapping, _ = get_arg_mapping(
            required_positional_names=["condition", "error_code"],
            optional_positional_names=["error_message", "prefix"],
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )

        condition_arg = arg_mapping.get("condition")
        if condition_arg is not None:
            condition_eb = expect.instance_builder(condition_arg, default=expect.default_none)
            condition_expr = condition_eb.bool_eval(location).resolve() if condition_eb else None
        else:
            condition_expr = None

        error_message = _resolve_error_message(arg_mapping, location)
        return builder_for_instance(
            pytypes.NoneType,
            AssertExpression(
                condition=condition_expr,
                error_message=error_message,
                source_location=location,
                log_error=True,
            ),
        )


class LoggedErrFunctionBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        arg_mapping, _ = get_arg_mapping(
            required_positional_names=["error_code"],
            optional_positional_names=["error_message", "prefix"],
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )

        error_message = _resolve_error_message(arg_mapping, location)
        return builder_for_instance(
            pytypes.NoneType,
            AssertExpression(
                condition=None,
                error_message=error_message,
                source_location=location,
                log_error=True,
            ),
        )


def _resolve_error_message(
    arg_mapping: dict[str, NodeBuilder], location: SourceLocation
) -> str | None:
    code = (
        expect.simple_string_literal(arg_mapping["error_code"], default=expect.default_none)
        if "error_code" in arg_mapping
        else None
    )
    message = (
        expect.simple_string_literal(arg_mapping["error_message"], default=expect.default_none)
        if "error_message" in arg_mapping
        else None
    )
    prefix = (
        expect.simple_string_literal(arg_mapping["prefix"], default=expect.default_none)
        if "prefix" in arg_mapping
        else "ERR"
    )

    # code strict properties validation
    if code is None:
        # should never get here because of type checking and expect.simple_string_literal(.)
        logger.error("error code is mandatory in logged errors", location=location)
        return None
    elif ":" in code:
        logger.error("error code must not contain domain separator ':'", location=location)
        return None

    # message strict properties validation
    if message is not None and ":" in message:
        logger.error("error message must not contain domain separator ':'", location=location)
        return None

    # prefix strict properties validation
    # (note: prefix should already be validated by mypy typing check)
    if prefix not in _VALID_PREFIXES:
        logger.error(
            "error prefix must be one of AER, ERR",
            location=location,
        )
        return None

    arc65_msg = f"{prefix}:{code}:{message}" if message else f"{prefix}:{code}"
    return arc65_msg
