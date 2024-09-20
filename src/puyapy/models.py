import contextlib
import typing
from collections.abc import Iterator, Mapping, Sequence
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
from puya.models import (
    ARC4ABIMethodConfig,
    ARC4BareMethodConfig,
    ARC4CreateOption,
    ContractReference,
    OnCompletionAction,
)
from puya.parse import SourceLocation
from puya.utils import StableSet, set_add

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


@attrs.define(kw_only=True)
class ContractFragmentMethod:
    member_name: str = attrs.field(on_setattr=attrs.setters.frozen)
    source_location: SourceLocation = attrs.field(on_setattr=attrs.setters.frozen)
    metadata: ARC4MethodData | None = attrs.field(on_setattr=attrs.setters.frozen)
    is_trivial: bool = attrs.field(on_setattr=attrs.setters.frozen)
    synthetic: bool = attrs.field(default=False, on_setattr=attrs.setters.frozen)
    inheritable: bool = attrs.field(default=True, on_setattr=attrs.setters.frozen)
    implementation: ContractMethod | None = attrs.field(default=None)

    @implementation.validator
    def _implementation_validate(self, _attr: object, value: ContractMethod | None) -> None:
        if value is None:
            return
        assert not self.is_trivial, "trivial methods should not have an implementation"
        assert value.member_name == self.member_name


@attrs.define(kw_only=True)
class ContractFragment:
    # constant data
    id: ContractReference = attrs.field(on_setattr=attrs.setters.frozen)
    source_location: SourceLocation = attrs.field(on_setattr=attrs.setters.frozen)
    pytype: pytypes.PyType = attrs.field(on_setattr=attrs.setters.frozen)
    mro: list["ContractFragment"] = attrs.field(on_setattr=attrs.setters.frozen)
    # constant references
    _methods: dict[str, ContractFragmentMethod] = attrs.field(
        factory=dict, on_setattr=attrs.setters.frozen
    )
    _state_defs: dict[str, AppStorageDeclaration] = attrs.field(
        factory=dict, on_setattr=attrs.setters.frozen
    )
    # mutable data
    _finalized: bool = False

    @property
    def is_arc4_client(self) -> bool:
        return pytypes.ARC4ClientBaseType in self.pytype.mro

    @property
    def is_finalized(self) -> bool:
        return self._finalized

    def finalize(self) -> None:
        assert not self._finalized, "attempted to finalize contract fragment twice"
        self._finalized = True

    def add_method(self, method: ContractFragmentMethod) -> None:
        assert not self._finalized, "attempted to add method data to finalized contract fragment"
        if self.is_arc4_client:
            assert method.is_trivial, "attempted to add non-trivial method to ARC4Client class"
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

    def resolve_method(self, name: str) -> ContractFragmentMethod | None:
        with contextlib.suppress(KeyError):
            return self._methods[name]
        for fragment in self.mro:
            with contextlib.suppress(KeyError):
                method = fragment._methods[name]  # noqa: SLF001
                if method.inheritable:
                    return method
        return None

    def collect_method_implementations(self) -> Iterator[ContractMethod | None]:
        for method in self._methods.values():
            # class being built for lowering should not have trivial methods defined
            yield method.implementation
        for ancestor in self.mro:
            for method in ancestor._methods.values():  # noqa: SLF001
                if method.inheritable and not method.is_trivial:
                    yield method.implementation

    def find_arc4_method_metadata(
        self,
        *,
        bare: bool | None = None,
        oca: OnCompletionAction | None = None,
        can_create: bool | None = None,
    ) -> Iterator[ARC4MethodData]:
        seen_names = set[str]()
        for frag in (self, *self.mro):
            for method_name, method in frag._methods.items():  # noqa: SLF001
                if (method.inheritable or frag is self) and set_add(seen_names, method_name):
                    md = method.metadata
                    if md is not None:
                        bare_matches = bare is None or bare == md.is_bare
                        oca_matches = oca is None or oca in md.config.allowed_completion_types
                        can_create_matches = can_create is None or (
                            can_create != (md.config.create == ARC4CreateOption.disallow)
                        )
                        if bare_matches and oca_matches and can_create_matches:
                            yield md

    def resolve_state(self, name: str) -> AppStorageDeclaration | None:
        if self._finalized:
            return self.state_defs.get(name)
        for fragment in (self, *self.mro):
            try:
                return fragment._state_defs[name]  # noqa: SLF001
            except KeyError:
                pass
        return None

    def add_state_def(self, decl: AppStorageDeclaration) -> None:
        assert not self.is_arc4_client, "attempted to add storage data to ARC4Client class"
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

    @cached_property
    def state_defs(self) -> Mapping[str, AppStorageDeclaration]:
        assert self._finalized, "attempted to enumerate storage data before finalization"
        result = self._state_defs
        for ancestor in self.mro:
            result = ancestor._state_defs | result  # noqa: SLF001
        return result
