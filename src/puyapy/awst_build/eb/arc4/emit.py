import re
import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import Emit, NewStruct
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
            case InstanceBuilder(pytype=pytypes.StructType() as struct_type) as event_arg_eb:
                if rest:
                    logger.error(
                        "unexpected additional arguments", location=rest[0].source_location
                    )
                    return dummy_value(pytypes.NoneType, location)
                event_name = struct_type.name.split(".")[-1]
                event_expr = event_arg_eb.resolve()
            case _:
                first_string = expect.simple_string_literal(first, default=expect.default_raise)
                event_name = first_string

                # emit requires a struct type, so generate one based on args
                values = {}
                fields = {}
                for idx, arg in enumerate(rest, start=1):
                    arg_instance_builder = expect.instance_builder(
                        arg, default=expect.default_raise
                    )
                    expr = maybe_resolve_literal(
                        arg_instance_builder, allow_literal=True
                    ).resolve()

                    field_name = f"field{idx}"
                    values[field_name] = expr
                    fields[field_name] = expr.wtype
                struct_name = re.sub(r"\(.*", "", event_name)
                struct_wtype = wtypes.ARC4Struct(
                    name=struct_name,
                    fields=fields,
                    frozen=True,
                    source_location=location,
                )
                event_expr = NewStruct(
                    values=values,
                    wtype=struct_wtype,
                    source_location=location,
                )
        emit = Emit(
            signature=event_name,
            value=event_expr,
            source_location=location,
        )
        return NoneExpressionBuilder(emit)
