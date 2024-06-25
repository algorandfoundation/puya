import typing
from collections.abc import Sequence

import mypy.nodes
import mypy.types

from puya import log
from puya.awst.nodes import (
    AppStateExpression,
    BaseClassSubroutineTarget,
    InstanceSubroutineTarget,
)
from puya.awst_build import pytypes
from puya.awst_build.context import ASTConversionModuleContext
from puya.awst_build.contract_data import AppStorageDeclaration
from puya.awst_build.eb._utils import constant_bool_and_error
from puya.awst_build.eb.factories import builder_for_instance
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder
from puya.awst_build.eb.storage import (
    BoxMapProxyExpressionBuilder,
    BoxProxyExpressionBuilder,
    BoxRefProxyExpressionBuilder,
    GlobalStateExpressionBuilder,
    LocalStateExpressionBuilder,
)
from puya.awst_build.eb.subroutine import (
    BaseClassSubroutineInvokerExpressionBuilder,
    SubroutineInvokerExpressionBuilder,
)
from puya.awst_build.utils import qualified_class_name, resolve_method_from_type_info
from puya.errors import CodeError
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


class ContractTypeExpressionBuilder(TypeBuilder):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        pytype: pytypes.PyType,
        type_info: mypy.nodes.TypeInfo,
        location: SourceLocation,
    ):
        super().__init__(pytype, location)
        self.context = context
        self._type_info = type_info
        self._cref = qualified_class_name(type_info)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("Cannot instantiate contract classes", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        func_or_dec = resolve_method_from_type_info(self._type_info, name, location)
        if func_or_dec is None:
            raise CodeError(f"Unknown member {name!r} of {self._type_info.fullname!r}", location)
        target = BaseClassSubroutineTarget(self._cref, name)
        return BaseClassSubroutineInvokerExpressionBuilder(
            context=self.context, target=target, node=func_or_dec, location=location
        )


class ContractSelfExpressionBuilder(NodeBuilder):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        type_info: mypy.nodes.TypeInfo,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.context = context
        self._type_info = type_info

    @typing.override
    @property
    def pytype(self) -> None:
        return None  # TODO ?

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        state_decl = self.context.state_defs(qualified_class_name(self._type_info)).get(name)
        if state_decl is not None:
            return _builder_for_storage_access(state_decl, location)
        node = self._type_info.get(name)
        if node is None:
            raise CodeError("unrecognised member", location)
        if node.node is None:
            raise CodeError("unable to resolve type of member", location)
        if not isinstance(node.node, mypy.nodes.FuncBase | mypy.nodes.Decorator):
            raise CodeError("cannot resolve state member", location)
        func_type = node.node.type
        if not isinstance(func_type, mypy.types.CallableType):
            raise CodeError("unable to resolve function type", location)

        return SubroutineInvokerExpressionBuilder(
            context=self.context,
            target=InstanceSubroutineTarget(name=name),
            location=location,
            func_type=func_type,
        )

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(value=True, location=location, negate=negate)


def _builder_for_storage_access(
    storage_decl: AppStorageDeclaration, location: SourceLocation
) -> NodeBuilder:
    match storage_decl.typ:
        case pytypes.PyType(generic=pytypes.GenericLocalStateType):
            return LocalStateExpressionBuilder(
                storage_decl.key, storage_decl.typ, storage_decl.member_name
            )
        case pytypes.PyType(generic=pytypes.GenericGlobalStateType):
            return GlobalStateExpressionBuilder(
                storage_decl.key, storage_decl.typ, storage_decl.member_name
            )
        case pytypes.BoxRefType:
            return BoxRefProxyExpressionBuilder(storage_decl.key, storage_decl.member_name)
        case pytypes.PyType(generic=pytypes.GenericBoxType):
            return BoxProxyExpressionBuilder(
                storage_decl.key, storage_decl.typ, storage_decl.member_name
            )
        case pytypes.PyType(generic=pytypes.GenericBoxMapType):
            return BoxMapProxyExpressionBuilder(
                storage_decl.key, storage_decl.typ, storage_decl.member_name
            )
        case content_type:
            return builder_for_instance(
                content_type,
                AppStateExpression(
                    key=storage_decl.key,
                    wtype=content_type.wtype,
                    exists_assertion_message=f"check self.{storage_decl.member_name} exists",
                    source_location=location,
                ),
            )
