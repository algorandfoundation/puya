import typing
from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya import log
from puya.awst.nodes import (
    BaseClassSubroutineTarget,
    CallArg,
    FreeSubroutineTarget,
    InstanceSubroutineTarget,
    SubroutineCallExpression,
)
from puya.awst_build import pytypes
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.eb._base import FunctionBuilder
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puya.awst_build.utils import require_instance_builder
from puya.errors import CodeError
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class SubroutineInvokerExpressionBuilder(FunctionBuilder):
    def __init__(
        self,
        target: InstanceSubroutineTarget | BaseClassSubroutineTarget | FreeSubroutineTarget,
        func_type: pytypes.FuncType,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.target = target
        self.func_type = func_type

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        call_args = list[CallArg]()
        for arg, arg_name, arg_kind in zip(args, arg_names, arg_kinds, strict=True):
            if arg_kind.is_star():
                raise CodeError(
                    "argument unpacking at call site not currently supported", arg.source_location
                )
            call_args.append(CallArg(name=arg_name, value=require_instance_builder(arg).resolve()))

        func_type = self.func_type
        expected_arg_types = func_type.args
        # TODO(frist): type check fully, not just num args... requires matching keyword positions
        if len(args) != len(expected_arg_types):
            logger.error("incorrect number of arguments to subroutine call", location=location)
        result_pytyp = func_type.ret_type

        call_expr = SubroutineCallExpression(
            source_location=location,
            target=self.target,
            args=call_args,
            wtype=result_pytyp.wtype,
        )
        return builder_for_instance(result_pytyp, call_expr)


class BaseClassSubroutineInvokerExpressionBuilder(SubroutineInvokerExpressionBuilder):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        target: BaseClassSubroutineTarget,
        func_type: pytypes.FuncType,
        location: SourceLocation,
        node: mypy.nodes.FuncBase | mypy.nodes.Decorator,
    ):
        super().__init__(target, func_type, location)
        self.context = context
        self.node = node
