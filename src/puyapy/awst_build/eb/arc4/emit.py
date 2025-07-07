import typing
from collections.abc import Sequence

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import Emit, NewStruct
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.arc4_utils import arc4_to_pytype, pytype_to_arc4
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb._utils import dummy_value
from puyapy.awst_build.eb.arc4._utils import (
    implicit_arc4_conversion,
    implicit_arc4_type_arg_conversion,
    split_arc4_signature,
)
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
                    return dummy_value(pytypes.NoneType, location)
                event_name = struct_type.name.split(".")[-1]
                event_arc4_name = pytype_to_arc4(
                    event_arg_eb.pytype, encode_resource_types=True, loc=location
                )
                event_expr = event_arg_eb.resolve()
            case _:
                method_sig = split_arc4_signature(first)
                if method_sig.maybe_returns is not None:
                    logger.error(
                        "event signatures cannot include return types",
                        location=first.source_location,
                    )
                event_name = method_sig.name
                if method_sig.maybe_args is None:
                    arc4_pytypes = [
                        implicit_arc4_type_arg_conversion(
                            expect.instance_builder(na, default=expect.default_raise).pytype,
                            location,
                        )
                        for na in rest
                    ]
                    arg_arc4_names = [
                        pytype_to_arc4(arc4_pt, encode_resource_types=True)
                        for arc4_pt in arc4_pytypes
                    ]
                else:
                    if (num_sig_args := len(method_sig.maybe_args)) != len(rest):
                        logger.error(
                            f"expected {num_sig_args} ABI "
                            f"argument{'' if num_sig_args == 1 else 's'},"
                            f" got {len(rest)}",
                            location=self.source_location,
                        )
                        return dummy_value(pytypes.NoneType, location)
                    arg_arc4_names = list(method_sig.maybe_args)
                    arc4_pytypes = [arc4_to_pytype(ts, location) for ts in method_sig.maybe_args]
                event_arc4_name = "(" + ",".join(arg_arc4_names) + ")"
                # emit requires a struct type, so generate one based on args
                values = {}
                fields = {}
                for idx, (arg, arc4_pt) in enumerate(
                    zip(rest, arc4_pytypes, strict=True), start=1
                ):
                    arc4_arg = implicit_arc4_conversion(arg, arc4_pt).resolve()
                    field_name = f"field{idx}"
                    values[field_name] = arc4_arg
                    fields[field_name] = arc4_arg.wtype
                struct_wtype = wtypes.ARC4Struct(
                    name=method_sig.name,
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
            signature=f"{event_name}{event_arc4_name}",
            value=event_expr,
            source_location=location,
        )
        return NoneExpressionBuilder(emit)
