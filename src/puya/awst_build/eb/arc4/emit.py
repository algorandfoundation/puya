from __future__ import annotations

import typing
from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya.awst.nodes import MethodConstant
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.arc4_utils import pytype_to_arc4
from puya.awst_build.eb._base import FunctionBuilder
from puya.awst_build.eb.arc4._utils import get_arc4_args_and_signature
from puya.awst_build.eb.arc4.tuple import ARC4TupleGenericTypeBuilder
from puya.awst_build.eb.interface import InstanceBuilder, LiteralBuilder, NodeBuilder
from puya.awst_build.eb.tuple import TupleLiteralBuilder
from puya.awst_build.eb.void import VoidExpressionBuilder
from puya.awst_build.utils import require_instance_builder
from puya.errors import CodeError
from puya.parse import SourceLocation


class EmitBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        inst_args = [require_instance_builder(a) for a in args]
        match inst_args:
            case [
                InstanceBuilder(pytype=pytypes.StructType() as struct_type) as event_arg_eb
            ] if pytypes.ARC4StructBaseType in struct_type.mro:
                event_name = struct_type.name.split(".")[-1]
            case [LiteralBuilder(value=str(event_str)), *event_args]:
                arc4_args, signature = get_arc4_args_and_signature(event_str, event_args, location)
                if signature.return_type is not None:
                    after_args = pytype_to_arc4(signature.return_type)
                    raise CodeError(
                        f"Invalid event signature, type specified after args {after_args!r}",
                        location,
                    )
                event_name = signature.method_name
                event_arg_eb = ARC4TupleGenericTypeBuilder(location).call(
                    args=[TupleLiteralBuilder(items=arc4_args, location=location)],
                    arg_names=[None],
                    arg_kinds=[mypy.nodes.ARG_POS],
                    location=location,
                )
            case _:
                raise CodeError("Unexpected arguments", location)
        event_sig = f"{event_name}{pytype_to_arc4(event_arg_eb.pytype, location)}"
        log_value = intrinsic_factory.concat(
            MethodConstant(value=event_sig, source_location=location),
            event_arg_eb.resolve(),
            location,
        )
        return VoidExpressionBuilder(intrinsic_factory.log(log_value, location))
