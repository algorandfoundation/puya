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
        context: ASTConversionModuleContext,
        target: InstanceSubroutineTarget | BaseClassSubroutineTarget | FreeSubroutineTarget,
        location: SourceLocation,
        func_type: mypy.types.CallableType,
    ):
        super().__init__(location)
        self.context = context
        self.target = target
        self.func_type = func_type

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
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
        # bit of a kludge, but it works for us for now
        if isinstance(self.target, FreeSubroutineTarget):
            expected_arg_types = func_type.arg_types
        else:
            expected_arg_types = func_type.arg_types[1:]
        # TODO: type check fully, not just num args... requires matching keyword positions
        if len(args) != len(expected_arg_types):
            logger.error("incorrect number of arguments to subroutine call", location=location)
        result_pytyp = self.context.type_to_pytype(func_type.ret_type, source_location=location)

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
        location: SourceLocation,
        node: mypy.nodes.FuncBase | mypy.nodes.Decorator,
    ):
        self.node = node
        func_type = node.type
        if not isinstance(func_type, mypy.types.CallableType):
            raise CodeError(f"Couldn't resolve signature of {node.fullname!r}", location)
        super().__init__(context, target, location, func_type)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_typs: Sequence[pytypes.PyType],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        from puya.awst_build.eb.contracts import ContractSelfExpressionBuilder

        if not args and isinstance(args[0], ContractSelfExpressionBuilder):
            raise CodeError(
                "First argument when calling a base class method directly should be self",
                args[0].source_location,
            )
        return super().call(args[1:], arg_typs[1:], arg_kinds[1:], arg_names[1:], location)
