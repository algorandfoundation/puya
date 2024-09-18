import enum
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
    ContractMethod,
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
    member_name: str
    config: ARC4BareMethodConfig
    is_bare: bool = attrs.field(default=True, init=False)


@attrs.frozen
class ARC4ABIMethodData:
    member_name: str
    config: ARC4ABIMethodConfig
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


class ContractFragmentRoot(enum.Enum):
    contract = enum.auto()
    arc4_contract = enum.auto()
    arc4_client = enum.auto()


@attrs.define(kw_only=True)
class ContractFragment:
    # constant data
    id: ContractReference = attrs.field(on_setattr=attrs.setters.frozen)
    source_location: SourceLocation = attrs.field(on_setattr=attrs.setters.frozen)
    pytype: pytypes.ContractType | pytypes.StaticType = attrs.field(
        on_setattr=attrs.setters.frozen
    )
    mro: list["ContractFragment"] = attrs.field(on_setattr=attrs.setters.frozen)
    is_abstract: bool = attrs.field(on_setattr=attrs.setters.frozen)
    root: ContractFragmentRoot = attrs.field(on_setattr=attrs.setters.frozen)
    # constant references
    _methods: dict[str, ContractMethod] = attrs.field(
        factory=dict, on_setattr=attrs.setters.frozen
    )
    _arc4_methods: dict[str, ARC4MethodData] = attrs.field(
        factory=dict, on_setattr=attrs.setters.frozen
    )
    _synthetic_arc4_methods: dict[str, ARC4MethodData] = attrs.field(
        factory=dict, on_setattr=attrs.setters.frozen
    )
    _state_defs: dict[str, AppStorageDeclaration] = attrs.field(
        factory=dict, on_setattr=attrs.setters.frozen
    )
    # mutable data
    _finalized: bool = False

    @property
    def is_finalized(self) -> bool:
        return self._finalized

    def finalize(self) -> None:
        assert not self._finalized, "attempted to finalize contract fragment twice"
        self._finalized = True

    def add_method(
        self,
        method: ContractMethod,
        arc4_method_data: ARC4MethodData | None,
        *,
        is_inheritable: bool = True,
    ) -> None:
        assert not self._finalized, "attempted to add method data to finalized contract fragment"
        # TODO: non-inheritable methods collection
        set_result = self._methods.setdefault(method.member_name, method)
        if set_result is not method:
            logger.info(
                f"previous definition of {method.member_name} was here",
                location=set_result.source_location,
            )
            logger.error(
                f"redefinition of {method.member_name}",
                location=method.source_location,
            )
        elif arc4_method_data is not None:
            if not is_inheritable:
                self._synthetic_arc4_methods[method.member_name] = arc4_method_data
            else:
                self._arc4_methods[method.member_name] = arc4_method_data

    def add_state_def(self, decl: AppStorageDeclaration) -> None:
        assert (
            self.root is not ContractFragmentRoot.arc4_client
        ), "attempted to add storage data to ARC4Client class"
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

    def get_contract_method(
        self, name: str, *, default: ContractMethod | None = None
    ) -> ContractMethod | None:
        if self._finalized:
            return self.contract_methods.get(name, default)
        for fragment in (self, *self.mro):
            try:
                return fragment._methods[name]  # noqa: SLF001
            except KeyError:
                pass
        return default

    @cached_property
    def contract_methods(self) -> Mapping[str, ContractMethod]:
        assert self._finalized, "attempted to enumerate method data before finalization"
        result = self._methods
        for ancestor in self.mro:
            result = ancestor._methods | result  # noqa: SLF001
        return result

    def get_arc4_method(
        self, name: str, *, default: ARC4MethodData | None = None
    ) -> ARC4MethodData | None:
        if self._finalized:
            return self.arc4_methods.get(name, default)
        for fragment in (self, *self.mro):
            try:
                return fragment._arc4_methods[name]  # noqa: SLF001
            except KeyError:
                pass
        return default

    @cached_property
    def arc4_methods(self) -> Mapping[str, ARC4MethodData]:
        assert self._finalized, "attempted to enumerate method data before finalization"
        result = self._arc4_methods
        for ancestor in self.mro:
            result = ancestor._arc4_methods | result  # noqa: SLF001
        assert not (
            result.keys() & self._synthetic_arc4_methods.keys()
        ), "synthetic method already exists"
        return self._synthetic_arc4_methods | result

    def get_state_def(
        self, name: str, *, default: AppStorageDeclaration | None = None
    ) -> AppStorageDeclaration | None:
        if self._finalized:
            return self.state_defs.get(name, default)
        for fragment in (self, *self.mro):
            try:
                return fragment._state_defs[name]  # noqa: SLF001
            except KeyError:
                pass
        return default

    @cached_property
    def state_defs(self) -> Mapping[str, AppStorageDeclaration]:
        assert self._finalized, "attempted to enumerate storage data before finalization"
        result = self._state_defs
        for ancestor in self.mro:
            result = ancestor._state_defs | result  # noqa: SLF001
        return result
