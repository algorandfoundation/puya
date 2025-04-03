import abc
import contextlib
import typing
from collections.abc import Iterator, Mapping, Sequence, Set
from functools import cached_property

import attrs
from mypy.nodes import ArgKind as ArgKind  # noqa: PLC0414

from puya import log
from puya.avm import OnCompletionAction
from puya.awst.nodes import (
    AppStorageDefinition,
    AppStorageKind,
    ARC4ABIMethodConfig,
    ARC4BareMethodConfig,
    ARC4CreateOption,
    ContractMethod,
    StateTotals,
)
from puya.errors import CodeError
from puya.parse import SourceLocation
from puya.program_refs import ContractReference
from puyapy.awst_build import pytypes

logger = log.get_logger(__name__)


@attrs.frozen
class ContractClassOptions:
    name_override: str | None
    scratch_slot_reservations: Set[int] | None
    state_totals: StateTotals | None
    avm_version: int | None


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
                f"invalid type for an ARC-4 method: {bad_type}", self.config.source_location
            )

        return {
            k: pytype_to_arc4_pytype(v, on_error=on_error, encode_resource_types=k == "output")
            for k, v in self._signature.items()
        }

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


@attrs.define
class ContractFragmentStorage:
    member_name: str = attrs.field(on_setattr=attrs.setters.frozen)
    source_location: SourceLocation = attrs.field(on_setattr=attrs.setters.frozen)
    kind: AppStorageKind = attrs.field(on_setattr=attrs.setters.frozen)
    definition: AppStorageDefinition | None


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
    def resolve_storage(
        self, name: str, *, include_inherited: bool = True
    ) -> ContractFragmentStorage | None: ...

    @abc.abstractmethod
    def state(self, *, include_inherited: bool = True) -> Iterator[ContractFragmentStorage]: ...

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


ConstantValue: typing.TypeAlias = int | str | bytes | bool
