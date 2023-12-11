from collections.abc import Sequence

import mypy.nodes
import mypy.types
import structlog

from puya.awst.nodes import (
    BaseClassSubroutineTarget,
    CallArg,
    FreeSubroutineTarget,
    InstanceSubroutineTarget,
    Literal,
    SubroutineCallExpression,
)
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import require_expression_builder
from puya.errors import CodeError
from puya.parse import SourceLocation

logger: structlog.types.FilteringBoundLogger = structlog.get_logger(__name__)


class SubroutineInvokerExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        target: InstanceSubroutineTarget | BaseClassSubroutineTarget | FreeSubroutineTarget,
        location: SourceLocation,
        func_type: mypy.types.CallableType | None = None,
    ):
        super().__init__(location)
        self.context = context
        self.target = target
        self.func_type = func_type

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        call_args = list[CallArg]()
        for arg, arg_name, arg_kind in zip(args, arg_names, arg_kinds, strict=True):
            if arg_kind.is_star():
                raise CodeError(
                    "argument unpacking at call site not currently supported", arg.source_location
                )
            call_args.append(
                CallArg(name=arg_name, value=require_expression_builder(arg).rvalue())
            )

        if self.func_type is None:
            # func_type might be none if it's an instance method call, for example,
            # which doesn't get fully resolved until a specific contract is being compiled
            result_wtype = self.context.mypy_expr_node_type(original_expr)
        else:
            func_type = self.func_type
            # bit of a kludge, but it works for us for now
            if isinstance(self.target, FreeSubroutineTarget):
                expected_arg_types = func_type.arg_types
            else:
                expected_arg_types = func_type.arg_types[1:]
            # TODO: type check fully, not just num args... requires matching keyword positions
            if len(args) != len(expected_arg_types):
                logger.error("incorrect number of arguments to subroutine call", location=location)
            result_wtype = self.context.type_to_wtype(func_type.ret_type, source_location=location)

        call_expr = SubroutineCallExpression(
            source_location=location,
            target=self.target,
            args=call_args,
            wtype=result_wtype,
        )
        return var_expression(call_expr)
