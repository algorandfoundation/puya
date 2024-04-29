import mypy.nodes
import mypy.types

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    AppStateExpression,
    BoxProxyField,
    InstanceSubroutineTarget,
)
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.contract_data import (
    AppStateDeclaration,
    AppStateDeclType,
    AppStorageDeclaration,
)
from puya.awst_build.eb.app_account_state import AppAccountStateExpressionBuilder
from puya.awst_build.eb.app_state import AppStateExpressionBuilder
from puya.awst_build.eb.base import ExpressionBuilder, IntermediateExpressionBuilder
from puya.awst_build.eb.box import (
    BoxMapProxyExpressionBuilder,
    BoxProxyExpressionBuilder,
    BoxRefProxyExpressionBuilder,
)
from puya.awst_build.eb.subroutine import (
    BaseClassSubroutineInvokerExpressionBuilder,
    SubroutineInvokerExpressionBuilder,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import qualified_class_name
from puya.errors import CodeError
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


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
        type_info: mypy.nodes.TypeInfo,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.context = context
        self._type_info = type_info

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        state_decl = self.context.state_defs[qualified_class_name(self._type_info)].get(name)
        if state_decl is not None:
            return _builder_for_storage_access(state_decl, location)

        sym_node = self._type_info.get(name)
        if sym_node is None or sym_node.node is None:
            raise CodeError(f"Unknown member: {name}", location)
        match sym_node.node:
            # matching types taken from mypy.nodes.TypeInfo.get_method
            case mypy.nodes.FuncBase() | mypy.nodes.Decorator() as func_or_dec:
                func_type = func_or_dec.type
                if not isinstance(func_type, mypy.types.CallableType):
                    raise CodeError(f"Couldn't resolve signature of {name!r}", location)

                return SubroutineInvokerExpressionBuilder(
                    context=self.context,
                    target=InstanceSubroutineTarget(name=name),
                    location=location,
                    func_type=func_type,
                )
            case _:
                raise CodeError(
                    f"Non-storage member {name!r} has unsupported function type", location
                )

    # def _get_storage_decl(
    #     self,
    #     name: str,
    #     typ: mypy.types.Type,
    #     defined_in: ContractReference,
    #     var_loc: SourceLocation,
    # ) -> AppStateDeclaration:
    #     match typ:
    #         case mypy.types.Instance(
    #             type=mypy.nodes.TypeInfo(fullname=constants.CLS_LOCAL_STATE),
    #             args=args,
    #         ):
    #             kind = AppStateKind.account_local
    #             decl_type = AppStateDeclType.local_proxy
    #             try:
    #                 (storage_type,) = args
    #             except ValueError:
    #                 raise CodeError(
    #                     f"{constants.CLS_LOCAL_STATE_ALIAS}"
    #                     f" requires exactly one type parameter",
    #                     var_loc,
    #                 ) from None
    #         case mypy.types.Instance(
    #             type=mypy.nodes.TypeInfo(fullname=constants.CLS_GLOBAL_STATE),
    #             args=args,
    #         ):
    #             kind = AppStateKind.app_global
    #             decl_type = AppStateDeclType.global_proxy
    #             try:
    #                 (storage_type,) = args
    #             except ValueError:
    #                 raise CodeError(
    #                     f"{constants.CLS_GLOBAL_STATE_ALIAS}"
    #                     f" requires exactly one type parameter",
    #                     var_loc,
    #                 ) from None
    #         case mypy.types.Instance(
    #             type=mypy.nodes.TypeInfo(fullname=constants.CLS_BOX_PROXY),
    #             args=args,
    #         ):
    #             kind = AppStateKind.box
    #             decl_type = AppStateDeclType.box
    #             try:
    #                 (storage_type,) = args
    #             except ValueError:
    #                 raise CodeError(
    #                     f"{constants.CLS_BOX_PROXY} requires exactly one type parameter",
    #                     var_loc,
    #                 ) from None
    #         case mypy.types.Instance(
    #             type=mypy.nodes.TypeInfo(fullname=constants.CLS_BOX_MAP_PROXY),
    #             args=args,
    #         ):
    #             kind = AppStateKind.box_map
    #             decl_type = AppStateDeclType.box_map
    #             try:
    #                 (key_type, storage_type) = args
    #             except ValueError:
    #                 raise CodeError(
    #                     f"{constants.CLS_BOX_MAP_PROXY} requires exactly two type parameters",
    #                     var_loc,
    #                 ) from None
    #         case mypy.types.Instance(
    #             type=mypy.nodes.TypeInfo(fullname=constants.CLS_BOX_REF_PROXY),
    #             args=args,
    #         ):
    #             kind = AppStateKind.box_ref
    #             decl_type = AppStateDeclType.box_ref
    #             if args:
    #                 raise CodeError(
    #                     f"{constants.CLS_BOX_REF_PROXY} requires has no type parameters",
    #                     var_loc,
    #                 )
    #         case _:
    #             kind = AppStateKind.app_global
    #             decl_type = AppStateDeclType.global_direct
    #             storage_type = typ
    #     storage_wtype = self.context.type_to_wtype(storage_type, source_location=var_loc)
    #     if not storage_wtype.lvalue:
    #         raise CodeError(
    #             f"Invalid type for Local storage - must be assignable,"
    #             f" which type {storage_wtype} is not",
    #             var_loc,
    #         )
    #     return AppStateDeclaration(
    #         member_name=name,
    #         kind=kind,
    #         storage_wtype=storage_wtype,
    #         decl_type=decl_type,
    #         source_location=var_loc,
    #         defined_in=defined_in,
    #     )


def _builder_for_storage_access(
    storage_decl: AppStorageDeclaration, location: SourceLocation
) -> ExpressionBuilder:
    match storage_decl:
        case AppStateDeclaration(decl_type=AppStateDeclType.box_ref):
            return BoxRefProxyExpressionBuilder(
                BoxProxyField(
                    source_location=storage_decl.source_location,
                    wtype=wtypes.box_ref_proxy_type,
                    field_name=storage_decl.member_name,
                )
            )
        case AppStateDeclaration(decl_type=AppStateDeclType.box):
            return BoxProxyExpressionBuilder(
                BoxProxyField(
                    source_location=storage_decl.source_location,
                    wtype=wtypes.WBoxProxy.from_content_type(storage_decl.storage_wtype),
                    field_name=storage_decl.member_name,
                )
            )
        case AppStateDeclaration(decl_type=AppStateDeclType.box_map):
            return BoxMapProxyExpressionBuilder(
                BoxProxyField(
                    source_location=storage_decl.source_location,
                    wtype=wtypes.WBoxMapProxy.from_key_and_content_type(
                        storage_decl.storage_wtype
                    ),
                    field_name=storage_decl.member_name,
                )
            )
        case AppStateDeclaration(decl_type=AppStateDeclType.local_proxy):
            return AppAccountStateExpressionBuilder(storage_decl, location)
        case AppStateDeclaration(decl_type=AppStateDeclType.global_proxy):
            return AppStateExpressionBuilder(storage_decl, location)
        case AppStateDeclaration(decl_type=AppStateDeclType.global_direct):
            return var_expression(
                AppStateExpression(
                    field_name=storage_decl.member_name,
                    wtype=storage_decl.storage_wtype,
                    source_location=location,
                )
            )
        case _:
            raise ValueError(f"Unexpected storage declaration {storage_decl}")
