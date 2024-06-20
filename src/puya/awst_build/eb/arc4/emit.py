import typing
from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya import log
from puya.awst.nodes import MethodConstant
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.arc4_utils import pytype_to_arc4
from puya.awst_build.eb._base import FunctionBuilder
from puya.awst_build.eb._utils import expect_at_least_one_arg
from puya.awst_build.eb.arc4._utils import get_arc4_args_and_signature
from puya.awst_build.eb.arc4.tuple import ARC4TupleGenericTypeBuilder
from puya.awst_build.eb.interface import InstanceBuilder, LiteralBuilder, NodeBuilder
from puya.awst_build.eb.tuple import TupleLiteralBuilder
from puya.awst_build.eb.void import VoidExpressionBuilder
from puya.errors import CodeError
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class EmitBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        first, rest = expect_at_least_one_arg(args, location)
        match first:
            case InstanceBuilder(
                pytype=pytypes.StructType() as struct_type
            ) as event_arg_eb if pytypes.ARC4StructBaseType in struct_type.mro:
                event_name = struct_type.name.split(".")[-1]
                if rest:
                    logger.error(
                        "unexpected additional arguments", location=rest[0].source_location
                    )
            case LiteralBuilder(value=str(event_str), source_location=sig_loc):
                arc4_args, signature = get_arc4_args_and_signature(event_str, rest, location)
                if signature.return_type is not None:
                    raise CodeError("event signatures cannot include return types", sig_loc)
                event_name = signature.method_name
                event_arg_eb = ARC4TupleGenericTypeBuilder(location).call(
                    args=[TupleLiteralBuilder(items=arc4_args, location=location)],
                    arg_names=[None],
                    arg_kinds=[mypy.nodes.ARG_POS],
                    location=location,
                )
            case _:
                raise CodeError("unexpected argument type", first.source_location)
        event_sig = f"{event_name}{pytype_to_arc4(event_arg_eb.pytype, location)}"
        log_value = intrinsic_factory.concat(
            MethodConstant(value=event_sig, source_location=location),
            event_arg_eb.resolve(),
            location,
        )
        return VoidExpressionBuilder(intrinsic_factory.log(log_value, location))
