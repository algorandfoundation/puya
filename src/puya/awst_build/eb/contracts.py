from collections.abc import Mapping

import mypy.nodes
import mypy.types

from puya.awst.nodes import AppStateExpression, InstanceSubroutineTarget
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.contract_data import AppStateDeclaration, AppStateDeclType
from puya.awst_build.eb.app_account_state import AppAccountStateExpressionBuilder
from puya.awst_build.eb.app_state import AppStateExpressionBuilder
from puya.awst_build.eb.base import ExpressionBuilder, IntermediateExpressionBuilder
from puya.awst_build.eb.subroutine import (
    BaseClassSubroutineInvokerExpressionBuilder,
    SubroutineInvokerExpressionBuilder,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.errors import CodeError
from puya.parse import SourceLocation


class ContractTypeExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        type_info: mypy.nodes.TypeInfo,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.context = context
        self._type_info = type_info

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        return BaseClassSubroutineInvokerExpressionBuilder(
            context=self.context, type_info=self._type_info, name=name, location=location
        )


class ContractSelfExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        app_state: Mapping[str, AppStateDeclaration],
        type_info: mypy.nodes.TypeInfo,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.context = context
        self._app_state = app_state
        self._type_info = type_info

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        if (state_decl := self._app_state.get(name)) is not None:
            return _builder_for_state_access(state_decl, location)

        func_or_dec = self._type_info.get_method(name)
        if func_or_dec is None:
            raise CodeError(f"Unknown member: {name}", location)

        func_type = func_or_dec.type
        if not isinstance(func_type, mypy.types.CallableType):
            raise CodeError(f"Couldn't resolve signature of {name!r}", location)

        return SubroutineInvokerExpressionBuilder(
            context=self.context,
            target=InstanceSubroutineTarget(name=name),
            location=location,
            func_type=func_type,
        )


def _builder_for_state_access(
    state_decl: AppStateDeclaration, location: SourceLocation
) -> ExpressionBuilder:
    match state_decl.decl_type:
        case AppStateDeclType.local_proxy:
            return AppAccountStateExpressionBuilder(state_decl, location)
        case AppStateDeclType.global_proxy:
            return AppStateExpressionBuilder(state_decl, location)
        case AppStateDeclType.global_direct:
            return var_expression(
                AppStateExpression(
                    field_name=state_decl.member_name,
                    wtype=state_decl.storage_wtype,
                    source_location=location,
                )
            )
