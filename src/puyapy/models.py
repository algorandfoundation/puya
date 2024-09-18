import typing
from collections.abc import Mapping, Sequence
from functools import cached_property

import attrs
from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    AppStorageDefinition,
    AppStorageKind,
    BytesConstant,
    BytesEncoding,
    StateTotals,
)
from puya.errors import CodeError
from puya.models import ARC4ABIMethodConfig, ARC4BareMethodConfig, ContractReference
from puya.parse import SourceLocation
from puya.utils import StableSet

from puyapy.awst_build import pytypes

logger = log.get_logger(__name__)


@attrs.frozen
class AppStorageDeclaration:
    member_name: str
    typ: pytypes.PyType
    key_override: BytesConstant | None
    """If a map type, then this is the prefix override"""
    source_location: SourceLocation
    defined_in: ContractReference
    description: str | None

    @property
    def key(self) -> BytesConstant:
        match self._inferred[0]:
            case AppStorageKind.app_global | AppStorageKind.account_local:
                wtype = wtypes.state_key
            case AppStorageKind.box:
                wtype = wtypes.box_key
            case invalid_kind:
                typing.assert_never(invalid_kind)
        if self.key_override is not None:
            bytes_const = self.key_override
        else:
            bytes_const = BytesConstant(
                value=self.member_name.encode("utf8"),
                encoding=BytesEncoding.utf8,
                source_location=self.source_location,
                wtype=wtype,
            )

        return bytes_const

    @cached_property
    def definition(self) -> AppStorageDefinition:
        kind, content, key_wtype = self._inferred
        return AppStorageDefinition(
            key=self.key,
            description=self.description,
            storage_wtype=content.wtype,
            key_wtype=key_wtype,
            source_location=self.source_location,
            kind=kind,
            member_name=self.member_name,
        )

    @cached_property
    def _inferred(self) -> tuple[AppStorageKind, pytypes.PyType, wtypes.WType | None]:
        key_wtype = None
        match self.typ:
            case pytypes.StorageProxyType(generic=pytypes.GenericLocalStateType, content=content):
                kind = AppStorageKind.account_local
            case pytypes.StorageProxyType(generic=pytypes.GenericGlobalStateType, content=content):
                kind = AppStorageKind.app_global
            case pytypes.BoxRefType:
                kind = AppStorageKind.box
                content = pytypes.BytesType
            case pytypes.StorageProxyType(generic=pytypes.GenericBoxType, content=content):
                kind = AppStorageKind.box
            case pytypes.StorageMapProxyType(
                generic=pytypes.GenericBoxMapType, content=content, key=key_typ
            ):
                kind = AppStorageKind.box
                key_wtype = key_typ.wtype
            case _ as content:
                kind = AppStorageKind.app_global
        return kind, content, key_wtype


@attrs.define
class ContractClassOptions:
    name_override: str | None
    scratch_slot_reservations: StableSet[int]
    state_totals: StateTotals | None


@attrs.frozen
class ARC4BareMethodData:
    config: ARC4BareMethodConfig
    is_synthetic_create: bool
    is_bare: bool = attrs.field(default=True, init=False)


@attrs.frozen
class ARC4ABIMethodData:
    config: ARC4ABIMethodConfig
    is_synthetic_create: bool = attrs.field(default=False, init=False)
    is_bare: bool = attrs.field(default=False, init=False)
    _signature: dict[str, pytypes.PyType]
    _arc4_signature: Mapping[str, pytypes.PyType] = attrs.field(init=False)

    @_arc4_signature.default
    def _arc4_signature_default(self) -> Mapping[str, pytypes.PyType]:
        from puyapy.awst_build.arc4_utils import pytype_to_arc4_pytype  # TODO: resolve circularity

        def on_error(bad_type: pytypes.PyType) -> typing.Never:
            raise CodeError(
                f"invalid type for an ARC4 method: {bad_type}", self.config.source_location
            )

        return {k: pytype_to_arc4_pytype(v, on_error=on_error) for k, v in self._signature.items()}

    @property
    def signature(self) -> Mapping[str, pytypes.PyType]:
        return self._signature

    @cached_property
    def return_type(self) -> pytypes.PyType:
        return self._signature["output"]

    @cached_property
    def arc4_return_type(self) -> pytypes.PyType:
        return self._arc4_signature["output"]

    @cached_property
    def argument_types(self) -> Sequence[pytypes.PyType]:
        names, types = zip(*self._signature.items(), strict=True)
        assert names[-1] == "output"
        return tuple(types[:-1])

    @cached_property
    def arc4_argument_types(self) -> Sequence[pytypes.PyType]:
        names, types = zip(*self._arc4_signature.items(), strict=True)
        assert names[-1] == "output"
        return tuple(types[:-1])


ARC4MethodData: typing.TypeAlias = ARC4BareMethodData | ARC4ABIMethodData


@attrs.define(kw_only=True)
class ContractFragment:
    id: ContractReference
    mro: list[ContractReference] = attrs.field(factory=list)
    is_abstract: bool
    _arc4_methods: dict[str, ARC4MethodData] = attrs.field(factory=dict)
    _state_defs: dict[str, AppStorageDeclaration] = attrs.field(factory=dict)
    _finalized: bool = False
    _is_arc4_client: bool = False

    @property
    def is_finalized(self) -> bool:
        return self._finalized

    def finalize(self) -> None:
        assert not self._finalized, "attempted to finalize contract fragment twice"
        self._finalized = True

    def get_arc4_method(
        self, name: str, *, default: ARC4MethodData | None = None
    ) -> ARC4MethodData | None:
        # assert self._finalized, "attempted to retrieve method data before finalization"
        return self._arc4_methods.get(name, default)

    @property
    def arc4_methods(self) -> Mapping[str, ARC4MethodData]:
        assert self._finalized, "attempted to enumerate method data before finalization"
        return self._arc4_methods

    def add_arc4_method_data(self, func_name: str, data: ARC4MethodData) -> None:
        assert not self._finalized, "attempted to add method data to finalized contract fragment"
        self._arc4_methods[func_name] = data

    def get_state_def(
        self, name: str, *, default: AppStorageDeclaration | None = None
    ) -> AppStorageDeclaration | None:
        # assert self._finalized, "attempted to retrieve storage data before finalization"
        return self._state_defs.get(name, default)

    @property
    def state_defs(self) -> Mapping[str, AppStorageDeclaration]:
        assert self._finalized, "attempted to enumerate storage data before finalization"
        return self._state_defs

    def add_state_def(self, decl: AppStorageDeclaration) -> None:
        assert not self._is_arc4_client, "attempted to add storage data to ARC4Client class"
        assert not self._finalized, "attempted to add storage data to finalized contract fragment"
        set_result = self._state_defs.setdefault(decl.member_name, decl)
        if set_result is not decl:
            logger.info(
                f"previous definition of {decl.member_name} was here",
                location=set_result.source_location,
            )
            logger.error(
                f"redefinition of {decl.member_name}",
                location=decl.source_location,
            )
