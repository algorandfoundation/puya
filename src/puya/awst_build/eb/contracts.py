import mypy.nodes
import mypy.types

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    AppStateExpression,
    AppStateKind,
    BoxProxyField,
    InstanceSubroutineTarget,
)
from puya.awst_build import constants
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.contract_data import (
    AppStateDeclaration,
    AppStateDeclType,
    AppStorageDeclaration,
    BoxDeclaration,
)
from puya.awst_build.eb.app_account_state import AppAccountStateExpressionBuilder
from puya.awst_build.eb.app_state import AppStateExpressionBuilder
from puya.awst_build.eb.base import ExpressionBuilder, IntermediateExpressionBuilder
from puya.awst_build.eb.box import (
    BoxBlobProxyExpressionBuilder,
    BoxMapProxyExpressionBuilder,
    BoxProxyExpressionBuilder,
)
from puya.awst_build.eb.subroutine import (
    BaseClassSubroutineInvokerExpressionBuilder,
    SubroutineInvokerExpressionBuilder,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.errors import CodeError, InternalError
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
            case mypy.nodes.Var() as member:
                if member.type is None:
                    raise CodeError(f"Unable to resolve type of {name!r}", location)
                var_loc = self.context.node_location(member)
                typ = mypy.types.get_proper_type(member.type)
                if typ is None:
                    raise InternalError(
                        f"symbol table for class {self._type_info.fullname}"
                        f" contains Var node entry for {name} without type",
                        var_loc,
                    )
                storage_decl = self._get_storage_decl(name=name, typ=typ, var_loc=var_loc)
                return _builder_for_storage_access(storage_decl, location)
            case _:
                raise CodeError(f"Type of self reference to {name} is unsupported", location)

    def _get_storage_decl(
        self, name: str, typ: mypy.types.Type, var_loc: SourceLocation
    ) -> AppStateDeclaration | BoxDeclaration:
        match typ:
            case mypy.types.Instance(
                type=mypy.nodes.TypeInfo(fullname=constants.CLS_LOCAL_STATE),
                args=args,
            ):
                kind = AppStateKind.account_local
                decl_type = AppStateDeclType.local_proxy
                try:
                    (storage_type,) = args
                except ValueError:
                    raise CodeError(
                        f"{constants.CLS_LOCAL_STATE_ALIAS}"
                        f" requires exactly one type parameter",
                        var_loc,
                    ) from None
            case mypy.types.Instance(
                type=mypy.nodes.TypeInfo(fullname=constants.CLS_GLOBAL_STATE),
                args=args,
            ):
                kind = AppStateKind.app_global
                decl_type = AppStateDeclType.global_proxy
                try:
                    (storage_type,) = args
                except ValueError:
                    raise CodeError(
                        f"{constants.CLS_GLOBAL_STATE_ALIAS}"
                        f" requires exactly one type parameter",
                        var_loc,
                    ) from None
            case mypy.types.Instance(
                type=mypy.nodes.TypeInfo(fullname=constants.CLS_BOX_PROXY),
                args=args,
            ):
                try:
                    (content_type,) = args
                    wtype: wtypes.WType = wtypes.WBoxProxy.from_content_type(
                        self.context.type_to_wtype(content_type, source_location=var_loc)
                    )
                except ValueError:
                    raise CodeError(
                        f"{constants.CLS_BOX_PROXY} requires exactly one type parameter",
                        var_loc,
                    ) from None
                return BoxDeclaration(
                    wtype=wtype,
                    member_name=name,
                    source_location=var_loc,
                )
            case mypy.types.Instance(
                type=mypy.nodes.TypeInfo(fullname=constants.CLS_BOX_MAP_PROXY),
                args=args,
            ):
                try:
                    (
                        key_type,
                        content_type,
                    ) = args
                    wtype = wtypes.WBoxMapProxy.from_key_and_content_type(
                        key_wtype=self.context.type_to_wtype(key_type, source_location=var_loc),
                        content_wtype=self.context.type_to_wtype(
                            content_type, source_location=var_loc
                        ),
                    )
                except ValueError:
                    raise CodeError(
                        f"{constants.CLS_BOX_MAP_PROXY} requires exactly two type parameters",
                        var_loc,
                    ) from None
                return BoxDeclaration(
                    wtype=wtype,
                    member_name=name,
                    source_location=var_loc,
                )

            case mypy.types.Instance(
                type=mypy.nodes.TypeInfo(fullname=constants.CLS_BOX_BLOB_PROXY),
                args=args,
            ):
                if args:
                    raise CodeError(
                        f"{constants.CLS_BOX_BLOB_PROXY} requires has no type parameters",
                        var_loc,
                    )
                return BoxDeclaration(
                    wtype=wtypes.box_blob_proxy_wtype,
                    member_name=name,
                    source_location=var_loc,
                )
            case _:
                kind = AppStateKind.app_global
                decl_type = AppStateDeclType.global_direct
                storage_type = typ
        storage_wtype = self.context.type_to_wtype(storage_type, source_location=var_loc)
        if not storage_wtype.lvalue:
            raise CodeError(
                f"Invalid type for Local storage - must be assignable,"
                f" which type {storage_wtype} is not",
                var_loc,
            )
        return AppStateDeclaration(
            member_name=name,
            kind=kind,
            storage_wtype=storage_wtype,
            decl_type=decl_type,
            source_location=var_loc,
        )


def _builder_for_storage_access(
    storage_decl: AppStorageDeclaration, location: SourceLocation
) -> ExpressionBuilder:
    match storage_decl:
        case BoxDeclaration(wtype=wtypes.box_blob_proxy_wtype):
            return BoxBlobProxyExpressionBuilder(
                BoxProxyField(
                    source_location=storage_decl.source_location,
                    wtype=wtypes.box_blob_proxy_wtype,
                    field_name=storage_decl.member_name,
                )
            )
        case BoxDeclaration(wtype=wtypes.WBoxProxy() as box_proxy_wtype):
            return BoxProxyExpressionBuilder(
                BoxProxyField(
                    source_location=storage_decl.source_location,
                    wtype=box_proxy_wtype,
                    field_name=storage_decl.member_name,
                )
            )
        case BoxDeclaration(wtype=wtypes.WBoxMapProxy() as box_map_proxy_wtype):
            return BoxMapProxyExpressionBuilder(
                BoxProxyField(
                    source_location=storage_decl.source_location,
                    wtype=box_map_proxy_wtype,
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
