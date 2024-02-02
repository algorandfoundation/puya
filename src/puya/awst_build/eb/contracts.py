from collections.abc import Mapping

import mypy.nodes
import mypy.types

from puya.awst import wtypes
from puya.awst.nodes import AppStateExpression, BoxProxyField, InstanceSubroutineTarget
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
        app_storage: Mapping[str, AppStorageDeclaration],
        type_info: mypy.nodes.TypeInfo,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.context = context
        self._app_storage = app_storage
        self._type_info = type_info

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        if (storage_decl := self._app_storage.get(name)) is not None:
            return _builder_for_storage_access(storage_decl, location)

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
