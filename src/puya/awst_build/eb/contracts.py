import mypy.nodes
import mypy.types

from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    AppStateExpression,
    BaseClassSubroutineTarget,
    BoxProxyField,
    InstanceSubroutineTarget,
)
from puya.awst_build import pytypes
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.contract_data import AppStorageDeclaration
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
from puya.awst_build.utils import qualified_class_name, resolve_method_from_type_info
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
        self._cref = qualified_class_name(type_info)

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder:
        func_or_dec = resolve_method_from_type_info(self._type_info, name, location)
        if func_or_dec is None:
            raise CodeError(f"Unknown member {name!r} of {self._type_info.fullname!r}", location)
        target = BaseClassSubroutineTarget(self._cref, name)
        return BaseClassSubroutineInvokerExpressionBuilder(
            context=self.context, target=target, node=func_or_dec, location=location
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
        state_decl = self.context.state_defs(qualified_class_name(self._type_info)).get(name)
        if state_decl is not None:
            return _builder_for_storage_access(state_decl, location)

        func_or_dec = resolve_method_from_type_info(self._type_info, name, location)
        if func_or_dec is None:
            raise CodeError(f"Unknown member {name!r} of {self._type_info.fullname!r}", location)
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
    match storage_decl.typ:
        case pytypes.BoxRefType:
            return BoxRefProxyExpressionBuilder(
                BoxProxyField(
                    source_location=storage_decl.source_location,
                    wtype=wtypes.box_ref_proxy_type,
                    field_name=storage_decl.member_name,
                )
            )
        case pytypes.PyType(generic=pytypes.GenericBoxType):
            return BoxProxyExpressionBuilder(
                BoxProxyField(
                    source_location=storage_decl.source_location,
                    wtype=wtypes.WBoxProxy.from_content_type(
                        storage_decl.definition.storage_wtype
                    ),
                    field_name=storage_decl.member_name,
                )
            )
        case pytypes.PyType(generic=pytypes.GenericBoxMapType):
            if storage_decl.definition.key_wtype is None:
                raise InternalError("BoxMap should have key WType", location)
            return BoxMapProxyExpressionBuilder(
                BoxProxyField(
                    source_location=storage_decl.source_location,
                    wtype=wtypes.WBoxMapProxy.from_key_and_content_type(
                        storage_decl.definition.key_wtype, storage_decl.definition.storage_wtype
                    ),
                    field_name=storage_decl.member_name,
                )
            )
        case pytypes.PyType(generic=pytypes.GenericLocalStateType):
            return AppAccountStateExpressionBuilder(storage_decl, location)
        case pytypes.PyType(generic=pytypes.GenericGlobalStateType):
            return AppStateExpressionBuilder(storage_decl, location)
        case _:
            return var_expression(
                AppStateExpression(
                    key=storage_decl.key,
                    field_name=storage_decl.member_name,
                    wtype=storage_decl.definition.storage_wtype,
                    source_location=location,
                )
            )
