import typing
from collections.abc import Sequence

import attrs

from puya import log
from puya.awst.nodes import (
    AppStateExpression,
    AppStorageDefinition,
    AppStorageKind,
    InstanceMethodTarget,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
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
from puyapy.models import ContractFragmentBase

logger = log.get_logger(__name__)


class ContractTypeExpressionBuilder(TypeBuilder[pytypes.ContractType]):
    def __init__(
        self,
        pytype: pytypes.ContractType,
        fragment: ContractFragmentBase,
        location: SourceLocation,
    ):
        assert pytype.name == fragment.id
        super().__init__(pytype, location)
        self.fragment: typing.Final = fragment

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
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
                pytypes.FuncArg(type=self.produces(), name=None, kind=models.ArgKind.ARG_POS),
                *sym_type.args,
            ],
        )
        method = self.fragment.resolve_method(name)
        if method is None:
            raise CodeError("unable to resolve method member", location)
        return BaseClassSubroutineInvokerExpressionBuilder(
            self.fragment.id, method, func_type=func_type, location=location
        )


class ContractSelfExpressionBuilder(NodeBuilder):  # TODO: this _is_ an instance, technically
    def __init__(
        self,
        fragment: ContractFragmentBase,
        pytype: pytypes.ContractType,
        location: SourceLocation,
    ):
        super().__init__(location)
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
            storage = self._fragment.resolve_storage(name)
            if storage is None:
                raise CodeError("unable to resolve storage member", location)
            if storage.definition is None:
                raise CodeError("use of storage proxy before definition", location)
            return _builder_for_storage_access(sym_type, name, storage.definition, location)

    @typing.override
    def bool_eval(self, location: SourceLocation, *, negate: bool = False) -> InstanceBuilder:
        return constant_bool_and_error(value=True, location=location, negate=negate)


def _builder_for_storage_access(
    typ: pytypes.PyType,
    member_name: str,
    definition: AppStorageDefinition,
    location: SourceLocation,
) -> NodeBuilder:
    key = attrs.evolve(definition.key, source_location=location)
    if not isinstance(typ, pytypes.StorageProxyType | pytypes.StorageMapProxyType):
        app_global_expr = AppStateExpression(
            key=key,
            wtype=typ.checked_wtype(location),
            exists_assertion_message=f"check self.{member_name} exists",
            source_location=location,
        )
        return builder_for_instance(typ, app_global_expr)
    if typ == pytypes.BoxRefType:
        return BoxRefProxyExpressionBuilder(key, member_name)
    match definition.kind:
        case AppStorageKind.app_global:
            return GlobalStateExpressionBuilder(key, typ, member_name)
        case AppStorageKind.account_local:
            return LocalStateExpressionBuilder(key, typ, member_name)
        case AppStorageKind.box:
            if isinstance(typ, pytypes.StorageMapProxyType):
                return BoxMapProxyExpressionBuilder(key, typ, member_name)
            else:
                return BoxProxyExpressionBuilder(key, typ, member_name)
