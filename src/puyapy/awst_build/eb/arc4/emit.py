import typing
from collections.abc import Sequence

from puya import log
from puya.awst.nodes import Emit, EmitFields
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb._utils import dummy_value
from puyapy.awst_build.eb.abi_call._utils import maybe_resolve_literal
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puyapy.awst_build.eb.none import NoneExpressionBuilder

logger = log.get_logger(__name__)


class EmitBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        first, rest = expect.at_least_one_arg(args, location, default=expect.default_raise)
        match first:
            case InstanceBuilder(pytype=pytypes.StructType()) as event_arg_eb:
                if rest:
                    logger.error(
                        "unexpected additional arguments", location=rest[0].source_location
                    )
                    return dummy_value(pytypes.NoneType, location)
                event_expr = event_arg_eb.resolve()
                return NoneExpressionBuilder(Emit(value=event_expr, source_location=location))
            case _:
                first_string = expect.simple_string_literal(first, default=expect.default_raise)
                event_name = first_string
                allow_literal = "(" in event_name

                values = []
                for arg in rest:
                    arg_instance_builder = expect.instance_builder(
                        arg, default=expect.default_raise
                    )
                    expr = maybe_resolve_literal(
                        arg_instance_builder, allow_literal=allow_literal
                    ).resolve()

                    values.append(expr)
                return NoneExpressionBuilder(
                    EmitFields(
                        signature=event_name,
                        values=values,
                        source_location=location,
                    )
                )
