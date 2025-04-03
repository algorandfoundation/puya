import typing
from collections.abc import Sequence

from puya import log
from puya.awst.nodes import Emit
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.arc4_utils import pytype_to_arc4
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb.arc4._utils import get_arc4_signature
from puyapy.awst_build.eb.arc4.struct import ARC4StructTypeBuilder
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
            case (
                InstanceBuilder(pytype=pytypes.StructType() as struct_type) as event_arg_eb
            ) if pytypes.ARC4StructBaseType < struct_type:
                if rest:
                    logger.error(
                        "unexpected additional arguments", location=rest[0].source_location
                    )
            case _:
                method_sig, signature = get_arc4_signature(first, rest, location)
                if signature.return_type != pytypes.NoneType or method_sig.endswith(")void"):
                    logger.error(
                        "event signatures cannot include return types",
                        location=first.source_location,
                    )
                arc4_args = signature.convert_args(rest)
                # emit requires a struct type, so generate one based on args
                struct_type = pytypes.StructType(
                    base=pytypes.ARC4StructBaseType,
                    name=signature.method_name,
                    desc=None,
                    fields={
                        f"field{idx}": arg.pytype for idx, arg in enumerate(arc4_args, start=1)
                    },
                    frozen=True,
                    source_location=location,
                )
                event_arg_eb = ARC4StructTypeBuilder(struct_type, location).call(
                    args=arc4_args,
                    arg_names=[None] * len(arc4_args),
                    arg_kinds=[models.ArgKind.ARG_POS] * len(arc4_args),
                    location=location,
                )
        event_name = struct_type.name.split(".")[-1]
        event_arc4_name = pytype_to_arc4(
            event_arg_eb.pytype, encode_resource_types=True, loc=location
        )
        event_sig = f"{event_name}{event_arc4_name}"
        emit = Emit(
            signature=event_sig,
            value=event_arg_eb.resolve(),
            source_location=location,
        )
        return NoneExpressionBuilder(emit)
