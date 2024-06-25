import typing
from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya import log
from puya.awst.nodes import BytesConstant, BytesEncoding, Expression
from puya.awst_build import intrinsic_factory, pytypes
from puya.awst_build.eb._base import FunctionBuilder
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puya.awst_build.eb.none import NoneExpressionBuilder
from puya.awst_build.eb.uint64 import UInt64TypeBuilder
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class LogBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        empty_utf8: Expression = BytesConstant(
            value=b"", encoding=BytesEncoding.utf8, source_location=location
        )
        args = list(args)
        try:
            sep_index = arg_names.index("sep")
        except ValueError:
            sep = empty_utf8
        else:
            sep_arg = args.pop(sep_index)
            if isinstance(sep_arg, InstanceBuilder) and sep_arg.pytype in (
                pytypes.StringType,
                pytypes.StrLiteralType,
                pytypes.BytesType,
                pytypes.BytesLiteralType,
            ):
                sep = sep_arg.to_bytes(sep_arg.source_location)
            else:
                logger.error("unexpected argument type", location=sep_arg.source_location)
                sep = empty_utf8

        bytes_args = []
        for arg in args:
            if not isinstance(arg, InstanceBuilder):
                logger.error("unexpected argument type", location=arg.source_location)
            else:
                if arg.pytype == pytypes.IntLiteralType:
                    arg = arg.resolve_literal(UInt64TypeBuilder(arg.source_location))
                # TODO: make to_bytes non-throwing
                bytes_expr = arg.to_bytes(arg.source_location)
                bytes_args.append(bytes_expr)

        if not bytes_args:
            log_value = empty_utf8
        else:
            log_value = bytes_args[0]
            for bytes_expr in bytes_args[1:]:
                arg_plus_sep = intrinsic_factory.concat(log_value, sep, bytes_expr.source_location)
                log_value = intrinsic_factory.concat(
                    arg_plus_sep, bytes_expr, bytes_expr.source_location
                )
        log_expr = intrinsic_factory.log(log_value, location)
        return NoneExpressionBuilder(log_expr)
