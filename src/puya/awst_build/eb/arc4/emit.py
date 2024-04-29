from __future__ import annotations

from typing import TYPE_CHECKING

import mypy.nodes

from puya.arc4_util import wtype_to_arc4
from puya.awst import wtypes
from puya.awst.nodes import (
    Literal,
    MethodConstant,
)
from puya.awst_build import intrinsic_factory
from puya.awst_build.eb.arc4._utils import (
    arc4_tuple_from_items,
    get_arc4_args_and_signature,
)
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
)
from puya.awst_build.eb.void import VoidExpressionBuilder
from puya.errors import CodeError

if TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from puya.parse import SourceLocation


class EmitBuilder(IntermediateExpressionBuilder):
    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> ExpressionBuilder:
        match args:
            case [
                ExpressionBuilder(value_type=wtypes.ARC4Struct() as struct_type) as event_arg_eb
            ]:
                event_name = struct_type.stub_name.split(".")[-1]
                event_arg = event_arg_eb.rvalue()
            case [Literal(value=str(event_str)), *event_args]:
                arc4_args, signature = get_arc4_args_and_signature(event_str, event_args, location)
                if signature.return_type is not None:
                    after_args = wtype_to_arc4(signature.return_type)
                    raise CodeError(
                        f"Invalid event signature, type specified after args {after_args!r}",
                        location,
                    )
                event_name = signature.method_name
                event_arg = arc4_tuple_from_items(
                    arc4_args,
                    location,
                )
            case _:
                raise CodeError("Unexpected arguments", location)
        event_sig = f"{event_name}{wtype_to_arc4(event_arg.wtype)}"
        log_value = intrinsic_factory.concat(
            MethodConstant(value=event_sig, source_location=location), event_arg, location
        )
        return VoidExpressionBuilder(intrinsic_factory.log(log_value, location))
