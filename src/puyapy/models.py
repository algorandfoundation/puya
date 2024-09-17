import abc
import contextlib
import typing
from collections.abc import Iterator, Mapping, Sequence, Set
from functools import cached_property

import attrs
from puya import log
from puya.awst import wtypes
from puya.awst.nodes import (
    AppStorageKind,
    BytesConstant,
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

from puyapy.awst_build import pytypes

logger = log.get_logger(__name__)


@attrs.define
class AppStorageDeclaration:
    member_name: str = attrs.field(on_setattr=attrs.setters.frozen)
    typ: pytypes.PyType = attrs.field(on_setattr=attrs.setters.frozen)
    defined_in: ContractReference = attrs.field(on_setattr=attrs.setters.frozen)
    source_location: SourceLocation = attrs.field(on_setattr=attrs.setters.frozen)
    key: BytesConstant | None
    """If a map type, then this is the prefix override"""
    description: str | None

    @property
    def kind(self) -> AppStorageKind:
        return self._inferred[0]

    @property
    def content_wtype(self) -> wtypes.WType:
        return self._inferred[1].wtype

    @property
    def key_wtype(self) -> wtypes.WType | None:
        return self._inferred[2]

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


@attrs.frozen
class ContractClassOptions:
    name_override: str | None
    scratch_slot_reservations: Set[int] | None
    state_totals: StateTotals | None


@attrs.frozen
class ARC4BareMethodData:
    pytype: pytypes.FuncType
    source_location: SourceLocation
    member_name: str
    config: ARC4BareMethodConfig
    is_bare: bool = attrs.field(default=True, init=False)


@attrs.frozen
class ARC4ABIMethodData:
    pytype: pytypes.FuncType
    source_location: SourceLocation
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


class ContractFragmentBase(abc.ABC):
    @property
    @abc.abstractmethod
    def id(self) -> ContractReference: ...

    # @property
    # @abc.abstractmethod
    # def source_location(self) -> SourceLocation: ...
    #
    @property
    @abc.abstractmethod
    def pytype(self) -> pytypes.PyType: ...

    @property
    @abc.abstractmethod
    def mro(self) -> Sequence["ContractFragmentBase"]: ...

    @property
    @abc.abstractmethod
    def symbols(self) -> Mapping[str, pytypes.PyType | None]: ...

    @typing.final
    def resolve_symbol(self, name: str) -> pytypes.PyType | None:
        for frag in (self, *self.mro):
            with contextlib.suppress(KeyError):
                return frag.symbols[name]
        return None

    @abc.abstractmethod
    def resolve_method(
        self, name: str, *, include_inherited: bool = True
    ) -> ContractFragmentMethod | None: ...

    @abc.abstractmethod
    def methods(
        self, *, include_inherited: bool = True, include_overridden: bool = False
    ) -> Iterator[ContractFragmentMethod]: ...

    @abc.abstractmethod
    def resolve_state(
        self, name: str, *, include_inherited: bool = True
    ) -> AppStorageDeclaration | None: ...

    @abc.abstractmethod
    def state(self, *, include_inherited: bool = True) -> Iterator[AppStorageDeclaration]: ...

    @typing.final
    def find_arc4_method_metadata(
        self,
        *,
        bare: bool | None = None,
        oca: OnCompletionAction | None = None,
        can_create: bool | None = None,
    ) -> Iterator[ARC4MethodData]:
        for method in self.methods():
            md = method.metadata
            if md is not None:
                bare_matches = bare is None or bare == md.is_bare
                oca_matches = oca is None or oca in md.config.allowed_completion_types
                can_create_matches = can_create is None or (
                    can_create != (md.config.create == ARC4CreateOption.disallow)
                )
                if bare_matches and oca_matches and can_create_matches:
                    yield md
