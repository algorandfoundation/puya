import typing
from collections.abc import Sequence

from puya import log
from puya.awst.nodes import (
    CallArg,
    ContractMethodTarget,
    SubroutineCallExpression,
    SubroutineTarget,
)
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puya.program_refs import ContractReference
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb._utils import dummy_value
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puyapy.awst_build.utils import get_arg_mapping
from puyapy.models import ContractFragmentMethod

logger = log.get_logger(__name__)


class SubroutineInvokerExpressionBuilder(FunctionBuilder):
    def __init__(
        self, target: SubroutineTarget, func_type: pytypes.FuncType, location: SourceLocation
    ):
        super().__init__(location)
        self.target = target
        self.func_type = func_type

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        result_pytyp = self.func_type.ret_type
        result_wtype = result_pytyp.wtype
        if isinstance(result_wtype, str):
            raise CodeError(
                f"unsupported return type for user function: {result_pytyp}", location=location
            )
        if any(arg_kind.is_star() for arg_kind in arg_kinds):
            logger.error(
                "argument unpacking at call site not currently supported", location=location
            )
            return dummy_value(result_pytyp, location)

        required_positional_names = list[str]()
        optional_positional_names = list[str]()
        required_kw_only = list[str]()
        optional_kw_only = list[str]()
        type_arg_map = dict[str, pytypes.FuncArg]()
        for idx, typ_arg in enumerate(self.func_type.args):
            if typ_arg.name is None and typ_arg.kind.is_named():
                raise InternalError("argument marked as named has no name", location)
            arg_map_name = typ_arg.name or str(idx)
            match typ_arg.kind:
                case models.ArgKind.ARG_POS:
                    required_positional_names.append(arg_map_name)
                case models.ArgKind.ARG_OPT:
                    optional_positional_names.append(arg_map_name)
                case models.ArgKind.ARG_NAMED:
                    required_kw_only.append(arg_map_name)
                case models.ArgKind.ARG_NAMED_OPT:
                    optional_kw_only.append(arg_map_name)
                case models.ArgKind.ARG_STAR | models.ArgKind.ARG_STAR2:
                    logger.error(
                        "functions with variadic arguments are not supported", location=location
                    )
                    return dummy_value(result_pytyp, location)
                case _:
                    typing.assert_never(typ_arg.kind)
            type_arg_map[arg_map_name] = typ_arg

        arg_map, any_missing = get_arg_mapping(
            required_positional_names=required_positional_names,
            optional_positional_names=optional_positional_names,
            required_kw_only=required_kw_only,
            optional_kw_only=optional_kw_only,
            args=args,
            arg_names=arg_names,
            call_location=location,
            raise_on_missing=False,
        )
        if any_missing:
            return dummy_value(result_pytyp, location)

        call_args = []
        # TODO: ideally, we would iterate arg_map, so the order is the same as the call site
        #       need to build map from arg to FuncArg then though to extract expected type(s)
        for arg_map_name, typ_arg in type_arg_map.items():
            arg_typ = typ_arg.type
            if isinstance(arg_typ, pytypes.UnionType):
                logger.error("union types are not supported in user functions", location=location)
                return dummy_value(result_pytyp, location)
            if isinstance(arg_typ, pytypes.LiteralOnlyType):
                logger.error(
                    f"unsupported type for user function argument: {arg_typ}", location=location
                )
                return dummy_value(result_pytyp, location)

            arg = arg_map[arg_map_name]
            if pytypes.ContractBaseType < arg_typ:
                if not (arg_typ <= arg.pytype):
                    logger.error("unexpected argument type", location=arg.source_location)
            else:
                arg = expect.argument_of_type_else_dummy(arg, arg_typ)
                passed_name = arg_map_name if arg_map_name in arg_names else None
                call_args.append(CallArg(name=passed_name, value=arg.resolve()))

        call_expr = SubroutineCallExpression(
            target=self.target,
            args=call_args,
            wtype=result_wtype,
            source_location=location,
        )
        return builder_for_instance(result_pytyp, call_expr)


class BaseClassSubroutineInvokerExpressionBuilder(SubroutineInvokerExpressionBuilder):
    def __init__(
        self,
        cref: ContractReference,
        method: ContractFragmentMethod,
        func_type: pytypes.FuncType,
        location: SourceLocation,
    ):
        target = ContractMethodTarget(cref=cref, member_name=method.member_name)
        super().__init__(target, func_type, location)
        self.cref: typing.Final = cref
        self.method: typing.Final = method
