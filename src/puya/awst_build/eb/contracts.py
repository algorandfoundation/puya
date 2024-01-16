from puya.awst.nodes import (
    AppStateExpression,
    InstanceSubroutineTarget,
)
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.contract_data import AppStateDeclaration, AppStateDeclType
from puya.awst_build.eb.app_account_state import AppAccountStateExpressionBuilder
from puya.awst_build.eb.app_state import AppStateExpressionBuilder
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
        app_state: dict[str, AppStateDeclaration],
        location: SourceLocation,
    ):
        super().__init__(location)
        self.context = context
        self._app_state = app_state

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        try:
            state_decl = self._app_state[name]
        except KeyError:
            return SubroutineInvokerExpressionBuilder(
                context=self.context,
                target=InstanceSubroutineTarget(name=name),
                location=location,
            )
        state_def = state_decl.state_def
        match state_decl.decl_type:
            case AppStateDeclType.local_proxy:
                return AppAccountStateExpressionBuilder(state_def, location)
            case AppStateDeclType.global_proxy:
                return AppStateExpressionBuilder(state_def, location)
            case AppStateDeclType.global_direct:
                return var_expression(
                    AppStateExpression.from_state_def(location=location, state_def=state_def)
                )
