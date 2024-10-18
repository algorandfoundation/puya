import typing
from collections.abc import Sequence

import attrs
import mypy.nodes
from puya import log
from puya.awst.nodes import AppStateExpression, InstanceMethodTarget
from puya.errors import CodeError
from puya.parse import SourceLocation

from puyapy.awst_build import pytypes
from puyapy.awst_build.context import ASTConversionModuleContext
from puyapy.awst_build.eb._utils import constant_bool_and_error
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder
from puyapy.awst_build.eb.storage import (
    BoxMapProxyExpressionBuilder,
    BoxProxyExpressionBuilder,
    BoxRefProxyExpressionBuilder,
    GlobalStateExpressionBuilder,
    LocalStateExpressionBuilder,
)
from puyapy.awst_build.eb.subroutine import (
    BaseClassSubroutineInvokerExpressionBuilder,
    SubroutineInvokerExpressionBuilder,
)
from puyapy.models import AppStorageDeclaration, ContractFragmentBase

logger = log.get_logger(__name__)


class ContractTypeExpressionBuilder(TypeBuilder[pytypes.ContractType]):
    def __init__(
        self,
        context: ASTConversionModuleContext,
        pytype: pytypes.ContractType,
        fragment: ContractFragmentBase,
        location: SourceLocation,
    ):
        super().__init__(pytype, location)
        self.context: typing.Final = context
        self.fragment: typing.Final = fragment
        self.cref: typing.Final = pytype.name

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError("cannot instantiate contract classes", location)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        sym_type = self.fragment.resolve_symbol(name)
        if sym_type is None:
            return super().member_access(name, location)
        if not isinstance(sym_type, pytypes.FuncType):
            raise CodeError("static references are only supported for methods", location)
        func_type = attrs.evolve(
            sym_type,
            args=[
                pytypes.FuncArg(
                    type=self.fragment.pytype, name=None, kind=mypy.nodes.ArgKind.ARG_POS
                ),
                *sym_type.args,
            ],
        )
        return BaseClassSubroutineInvokerExpressionBuilder(
            context=self.context,
            cref=self.cref,
            member_name=name,
            func_type=func_type,
            location=location,
        )


class ContractSelfExpressionBuilder(NodeBuilder):  # TODO: this _is_ an instance, technically
    def __init__(
        self,
        context: ASTConversionModuleContext,
        fragment: ContractFragmentBase,
        pytype: pytypes.ContractType,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.context = context
        self._fragment = fragment
        self._pytype = pytype

    @typing.override
    @property
    def pytype(self) -> pytypes.ContractType:
        return self._pytype

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        sym_type = self._fragment.resolve_symbol(name)
        if sym_type is None:
            raise CodeError(f"unrecognised member of {self.pytype}: {name}", location)
        if isinstance(sym_type, pytypes.FuncType):
            return SubroutineInvokerExpressionBuilder(
                target=InstanceMethodTarget(member_name=name),
                func_type=sym_type,
                location=location,
            )
        else:
            state_decl = self.context.contract_fragments[self._pytype.name].resolve_state(name)
            if state_decl is not None:
                return _builder_for_storage_access(state_decl, location)
            raise CodeError("cannot resolve state member", location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(value=True, location=location, negate=negate)


def _builder_for_storage_access(
    storage_decl: AppStorageDeclaration, location: SourceLocation
) -> NodeBuilder:
    if storage_decl.key is None:
        raise CodeError("use of storage proxy before definition", location)
    key = attrs.evolve(storage_decl.key, source_location=location)
    match storage_decl.typ:
        case pytypes.PyType(generic=pytypes.GenericLocalStateType):
            return LocalStateExpressionBuilder(key, storage_decl.typ, storage_decl.member_name)
        case pytypes.PyType(generic=pytypes.GenericGlobalStateType):
            return GlobalStateExpressionBuilder(key, storage_decl.typ, storage_decl.member_name)
        case pytypes.BoxRefType:
            return BoxRefProxyExpressionBuilder(key, storage_decl.member_name)
        case pytypes.PyType(generic=pytypes.GenericBoxType):
            return BoxProxyExpressionBuilder(key, storage_decl.typ, storage_decl.member_name)
        case pytypes.PyType(generic=pytypes.GenericBoxMapType):
            return BoxMapProxyExpressionBuilder(key, storage_decl.typ, storage_decl.member_name)
        case content_type:
            return builder_for_instance(
                content_type,
                AppStateExpression(
                    key=key,
                    wtype=content_type.wtype,
                    exists_assertion_message=f"check self.{storage_decl.member_name} exists",
                    source_location=location,
                ),
            )
