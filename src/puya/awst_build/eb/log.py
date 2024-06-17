from __future__ import annotations

import typing

import mypy.nodes

from puya.awst.nodes import BytesConstant, BytesEncoding, Expression
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb._base import FunctionBuilder
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puya.awst_build.eb.uint64 import UInt64TypeBuilder
from puya.awst_build.eb.void import VoidExpressionBuilder
from puya.awst_build.utils import require_instance_builder
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.types

    from puya.parse import SourceLocation


class LogBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        args_ = [require_instance_builder(a) for a in args]
        try:
            sep_index = arg_names.index("sep")
        except ValueError:
            sep: Expression = BytesConstant(
                value=b"", encoding=BytesEncoding.utf8, source_location=location
            )
        else:
            sep_arg = args_.pop(sep_index)
            if sep_arg.pytype not in (
                pytypes.StringType,
                pytypes.StrLiteralType,
                pytypes.BytesType,
                pytypes.BytesLiteralType,
            ):
                raise CodeError(
                    "invalid argument type for 'sep' parameter", sep_arg.source_location
                )
            sep = sep_arg.to_bytes(sep_arg.source_location)

        bytes_args = []
        for arg in args_:
            if arg.pytype == pytypes.IntLiteralType:
                arg = arg.resolve_literal(UInt64TypeBuilder(arg.source_location))
            bytes_expr = arg.to_bytes(arg.source_location)
            bytes_args.append(bytes_expr)

        if not bytes_args:
            log_value: Expression = BytesConstant(
                value=b"", encoding=BytesEncoding.utf8, source_location=location
            )
        else:
            log_value = bytes_args[0]
            for bytes_expr in bytes_args[1:]:
                arg_plus_sep = intrinsic_factory.concat(log_value, sep, bytes_expr.source_location)
                log_value = intrinsic_factory.concat(
                    arg_plus_sep, bytes_expr, bytes_expr.source_location
                )
        return VoidExpressionBuilder(intrinsic_factory.log(log_value, location))
