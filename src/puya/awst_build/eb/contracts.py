from puya.awst.nodes import (
    AppStateDefinition,
    AppStateExpression,
    AppStateKind,
    AppStorageApi,
    InstanceSubroutineTarget,
)
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.eb.app_account_state import AppAccountStateExpressionBuilder
from puya.awst_build.eb.app_global_state import AppStateExpressionBuilder
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
)
from puya.awst_build.eb.subroutine import SubroutineInvokerExpressionBuilder
from puya.awst_build.eb.var_factory import var_expression
from puya.parse import SourceLocation


class ContractSelfExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        app_state: dict[str, AppStateDefinition],
        location: SourceLocation,
    ):
        super().__init__(location)
        self.context = context
        self._app_state = app_state

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        try:
            state_def = self._app_state[name]
        except KeyError:
            return SubroutineInvokerExpressionBuilder(
                context=self.context,
                target=InstanceSubroutineTarget(name=name),
                location=location,
            )
        if state_def.kind is AppStateKind.app_global:
            if state_def.api is AppStorageApi.simplified:
                return var_expression(
                    AppStateExpression.from_state_def(
                        location=location,
                        state_def=state_def,
                    )
                )
            elif state_def.api is AppStorageApi.full:
                return AppStateExpressionBuilder(state_def, location=location)

        else:
            assert state_def.kind is AppStateKind.app_account
            assert (
                state_def.api is AppStorageApi.full
            ), "account_local storage does not have a simplified api"
            return AppAccountStateExpressionBuilder(state_def, location)
