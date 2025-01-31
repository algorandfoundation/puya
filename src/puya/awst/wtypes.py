import typing
from collections.abc import Iterable, Mapping
from functools import cached_property

import attrs
from immutabledict import immutabledict

from puya import log
from puya.avm import AVMType, TransactionType
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puya.utils import unique

logger = log.get_logger(__name__)


@attrs.frozen(kw_only=True)
class WType:
    name: str
    scalar_type: typing.Literal[AVMType.uint64, AVMType.bytes, None]
    "the (unbound) AVM stack type, if any"
    ephemeral: bool = False
    """ephemeral types are not suitable for naive storage / persistence,
     even if their underlying type is a simple stack value"""
    immutable: bool

    def __str__(self) -> str:
        return self.name


void_wtype: typing.Final = WType(
    name="void",
    scalar_type=None,
    immutable=True,
)

bool_wtype: typing.Final = WType(
    name="bool",
    scalar_type=AVMType.uint64,
    immutable=True,
)

uint64_wtype: typing.Final = WType(
    name="uint64",
    scalar_type=AVMType.uint64,
    immutable=True,
)

biguint_wtype: typing.Final = WType(
    name="biguint",
    scalar_type=AVMType.bytes,
    immutable=True,
)

bytes_wtype: typing.Final = WType(
    name="bytes",
    scalar_type=AVMType.bytes,
    immutable=True,
)
string_wtype: typing.Final = WType(
    name="string",
    scalar_type=AVMType.bytes,
    immutable=True,
)
asset_wtype: typing.Final = WType(
    name="asset",
    scalar_type=AVMType.uint64,
    immutable=True,
)

account_wtype: typing.Final = WType(
    name="account",
    scalar_type=AVMType.bytes,
    immutable=True,
)

application_wtype: typing.Final = WType(
    name="application",
    scalar_type=AVMType.uint64,
    immutable=True,
)

state_key: typing.Final = WType(
    name="state_key",
    scalar_type=AVMType.bytes,
    immutable=True,
)
box_key: typing.Final = WType(
    name="box_key",
    scalar_type=AVMType.bytes,
    immutable=True,
)

uint64_range_wtype: typing.Final = WType(
    name="uint64_range",
    scalar_type=None,
    immutable=True,
)


@attrs.frozen
class WEnumeration(WType):
    sequence_type: WType
    name: str = attrs.field(init=False)
    immutable: bool = attrs.field(default=True, init=False)
    scalar_type: None = attrs.field(default=None, init=False)
    ephemeral: bool = attrs.field(default=False, init=False)

    @name.default
    def _name_factory(self) -> str:
        return f"enumerate_{self.sequence_type.name}"


@attrs.frozen
class _TransactionRelatedWType(WType):
    transaction_type: TransactionType | None
    ephemeral: bool = attrs.field(default=True, init=False)
    immutable: bool = attrs.field(default=True, init=False)


@typing.final
@attrs.frozen
class WGroupTransaction(_TransactionRelatedWType):
    scalar_type: typing.Literal[AVMType.uint64] = attrs.field(default=AVMType.uint64, init=False)

    @classmethod
    def from_type(cls, transaction_type: TransactionType | None) -> "WGroupTransaction":
        name = "group_transaction"
        if transaction_type:
            name = f"{name}_{transaction_type.name}"
        return cls(name=name, transaction_type=transaction_type)


@typing.final
@attrs.frozen
class WInnerTransactionFields(_TransactionRelatedWType):
    scalar_type: None = attrs.field(default=None, init=False)

    @classmethod
    def from_type(cls, transaction_type: TransactionType | None) -> "WInnerTransactionFields":
        name = "inner_transaction_fields"
        if transaction_type:
            name = f"{name}_{transaction_type.name}"
        return cls(name=name, transaction_type=transaction_type)


@typing.final
@attrs.frozen
class WInnerTransaction(_TransactionRelatedWType):
    scalar_type: None = attrs.field(default=None, init=False)

    @classmethod
    def from_type(cls, transaction_type: TransactionType | None) -> "WInnerTransaction":
        name = "inner_transaction"
        if transaction_type:
            name = f"{name}_{transaction_type.name}"
        return cls(name=name, transaction_type=transaction_type)


@typing.final
@attrs.frozen
class WStructType(WType):
    fields: immutabledict[str, WType] = attrs.field(converter=immutabledict)
    frozen: bool
    immutable: bool = attrs.field(init=False)
    scalar_type: None = attrs.field(default=None, init=False)
    source_location: SourceLocation | None = attrs.field(eq=False)
    desc: str | None = None

    @immutable.default
    def _immutable(self) -> bool:
        # TODO: determine correct behaviour when implementing native structs
        raise NotImplementedError

    @fields.validator
    def _fields_validator(self, _: object, fields: immutabledict[str, WType]) -> None:
        if not fields:
            raise CodeError("struct needs fields", self.source_location)
        if void_wtype in fields.values():
            raise CodeError("struct should not contain void types", self.source_location)


@typing.final
@attrs.frozen
class WArray(WType):
    element_type: WType = attrs.field()
    name: str = attrs.field(init=False)
    scalar_type: None = attrs.field(default=None, init=False)
    source_location: SourceLocation | None = attrs.field(eq=False)
    immutable: bool = attrs.field(default=False, init=False)

    @element_type.validator
    def _element_type_validator(self, _: object, element_type: WType) -> None:
        if element_type == void_wtype:
            raise CodeError("array element type cannot be void", self.source_location)

    @name.default
    def _name(self) -> str:
        return f"array<{self.element_type.name}>"


@typing.final
@attrs.frozen(eq=False)
class WTuple(WType):
    types: tuple[WType, ...] = attrs.field(converter=tuple[WType, ...])
    source_location: SourceLocation | None = attrs.field(default=None)
    scalar_type: None = attrs.field(default=None, init=False)
    immutable: bool = attrs.field(default=True, init=False)
    name: str = attrs.field(kw_only=True)
    names: tuple[str, ...] | None = attrs.field(default=None)
    desc: str | None = None

    def __eq__(self, other: object) -> bool:
        # this custom equality check ensures that
        # tuple field names are only considered when both sides
        # have defined names
        if not isinstance(other, WTuple):
            return False
        return self.types == other.types and (
            self.names == other.names or None in (self.names, other.names)
        )

    def __hash__(self) -> int:
        return hash(self.types)

    @types.validator
    def _types_validator(self, _attribute: object, types: tuple[WType, ...]) -> None:
        if void_wtype in types:
            raise CodeError("tuple should not contain void types", self.source_location)

    @name.default
    def _name(self) -> str:
        return f"tuple<{','.join([t.name for t in self.types])}>"

    @names.validator
    def _names_validator(self, _attribute: object, names: tuple[str, ...] | None) -> None:
        if names is None:
            return
        if len(names) != len(self.types):
            raise InternalError("mismatch between tuple item names length and types")
        if len(names) != len(unique(names)):
            raise CodeError("tuple item names are not unique", self.source_location)

    @cached_property
    def fields(self) -> Mapping[str, WType]:
        """Mapping of item names to types if `names` is defined, otherwise empty."""
        if self.names is None:
            return {}
        return dict(zip(self.names, self.types, strict=True))

    def name_to_index(self, name: str, source_location: SourceLocation) -> int:
        if self.names is None:
            raise CodeError(
                "cannot access tuple item by name of an unnamed tuple", source_location
            )
        try:
            return self.names.index(name)
        except ValueError:
            raise CodeError(f"{name} is not a member of {self.name}") from None


@attrs.frozen(kw_only=True)
class ARC4Type(WType):
    scalar_type: typing.Literal[AVMType.bytes] = attrs.field(default=AVMType.bytes, init=False)
    arc4_name: str = attrs.field(eq=False)  # exclude from equality in case of aliasing
    native_type: WType | None

    def can_encode_type(self, wtype: WType) -> bool:
        return wtype == self.native_type


arc4_bool_wtype: typing.Final = ARC4Type(
    name="arc4.bool",
    arc4_name="bool",
    immutable=True,
    native_type=bool_wtype,
)


@typing.final
@attrs.frozen(kw_only=True)
class ARC4UIntN(ARC4Type):
    immutable: bool = attrs.field(default=True, init=False)
    native_type: WType = attrs.field(default=biguint_wtype, init=False)
    n: int = attrs.field()
    arc4_name: str = attrs.field(eq=False)
    name: str = attrs.field(init=False)
    source_location: SourceLocation | None = attrs.field(default=None, eq=False)

    @n.validator
    def _n_validator(self, _attribute: object, n: int) -> None:
        if not (n % 8 == 0):
            raise CodeError("Bit size must be multiple of 8", self.source_location)
        if not (8 <= n <= 512):
            raise CodeError("Bit size must be between 8 and 512 inclusive", self.source_location)

    @arc4_name.default
    def _arc4_name(self) -> str:
        return f"uint{self.n}"

    @name.default
    def _name(self) -> str:
        return f"arc4.{self._arc4_name()}"

    def can_encode_type(self, wtype: WType) -> bool:
        return wtype in (bool_wtype, uint64_wtype, biguint_wtype)


@typing.final
@attrs.frozen(kw_only=True)
class ARC4UFixedNxM(ARC4Type):
    n: int = attrs.field()
    m: int = attrs.field()
    immutable: bool = attrs.field(default=True, init=False)
    arc4_name: str = attrs.field(init=False, eq=False)
    name: str = attrs.field(init=False)
    source_location: SourceLocation | None = attrs.field(default=None, eq=False)
    native_type: None = attrs.field(default=None, init=False)

    @arc4_name.default
    def _arc4_name(self) -> str:
        return f"ufixed{self.n}x{self.m}"

    @name.default
    def _name(self) -> str:
        return f"arc4.{self.arc4_name}"

    @n.validator
    def _n_validator(self, _attribute: object, n: int) -> None:
        if not (n % 8 == 0):
            raise CodeError("Bit size must be multiple of 8", self.source_location)
        if not (8 <= n <= 512):
            raise CodeError("Bit size must be between 8 and 512 inclusive", self.source_location)

    @m.validator
    def _m_validator(self, _attribute: object, m: int) -> None:
        if not (1 <= m <= 160):
            raise CodeError("Precision must be between 1 and 160 inclusive", self.source_location)


def _required_arc4_wtypes(wtypes: Iterable[WType]) -> tuple[ARC4Type, ...]:
    result = []
    for wtype in wtypes:
        if not isinstance(wtype, ARC4Type):
            raise CodeError(f"expected ARC4 type: {wtype}")
        result.append(wtype)
    return tuple(result)


@typing.final
@attrs.frozen(kw_only=True)
class ARC4Tuple(ARC4Type):
    source_location: SourceLocation | None = attrs.field(default=None, eq=False)
    types: tuple[ARC4Type, ...] = attrs.field(converter=_required_arc4_wtypes)
    name: str = attrs.field(init=False)
    arc4_name: str = attrs.field(init=False, eq=False)
    immutable: bool = attrs.field(init=False)
    native_type: WTuple = attrs.field(init=False)

    @name.default
    def _name(self) -> str:
        return f"arc4.tuple<{','.join(t.name for t in self.types)}>"

    @arc4_name.default
    def _arc4_name(self) -> str:
        return f"({','.join(item.arc4_name for item in self.types)})"

    @immutable.default
    def _immutable(self) -> bool:
        return all(typ.immutable for typ in self.types)

    @native_type.default
    def _native_type(self) -> WTuple:
        return WTuple(self.types, self.source_location)

    def can_encode_type(self, wtype: WType) -> bool:
        return super().can_encode_type(wtype) or _is_arc4_encodeable_tuple(wtype, self.types)


def _is_arc4_encodeable_tuple(
    wtype: WType, target_types: tuple[ARC4Type, ...]
) -> typing.TypeGuard[WTuple]:
    return (
        isinstance(wtype, WTuple)
        and len(wtype.types) == len(target_types)
        and all(
            arc4_wtype == encode_wtype or arc4_wtype.can_encode_type(encode_wtype)
            for arc4_wtype, encode_wtype in zip(target_types, wtype.types, strict=True)
        )
    )


def _expect_arc4_type(wtype: WType) -> ARC4Type:
    if not isinstance(wtype, ARC4Type):
        raise CodeError(f"expected ARC4 type: {wtype}")
    return wtype


@attrs.frozen(kw_only=True)
class ARC4Array(ARC4Type):
    element_type: ARC4Type = attrs.field(converter=_expect_arc4_type)
    native_type: WType | None = None
    immutable: bool = False


@typing.final
@attrs.frozen(kw_only=True)
class ARC4DynamicArray(ARC4Array):
    name: str = attrs.field(init=False)
    arc4_name: str = attrs.field(eq=False)
    source_location: SourceLocation | None = attrs.field(default=None, eq=False)

    @name.default
    def _name(self) -> str:
        return f"arc4.dynamic_array<{self.element_type.name}>"

    @arc4_name.default
    def _arc4_name(self) -> str:
        return f"{self.element_type.arc4_name}[]"


@typing.final
@attrs.frozen(kw_only=True)
class ARC4StaticArray(ARC4Array):
    array_size: int = attrs.field(validator=attrs.validators.ge(0))
    name: str = attrs.field(init=False)
    arc4_name: str = attrs.field(eq=False)
    source_location: SourceLocation | None = attrs.field(default=None, eq=False)

    @name.default
    def _name(self) -> str:
        return f"arc4.static_array<{self.element_type.name}, {self.array_size}>"

    @arc4_name.default
    def _arc4_name(self) -> str:
        return f"{self.element_type.arc4_name}[{self.array_size}]"


def _require_arc4_fields(fields: Mapping[str, WType]) -> immutabledict[str, ARC4Type]:
    if not fields:
        raise CodeError("arc4.Struct needs at least one element")
    non_arc4_fields = [
        field_name
        for field_name, field_type in fields.items()
        if not isinstance(field_type, ARC4Type)
    ]
    if non_arc4_fields:
        raise CodeError(
            "invalid ARC4 Struct declaration,"
            f" the following fields are not ARC4 encoded types: {', '.join(non_arc4_fields)}",
        )
    return immutabledict(fields)


@typing.final
@attrs.frozen(kw_only=True)
class ARC4Struct(ARC4Type):
    fields: immutabledict[str, ARC4Type] = attrs.field(converter=_require_arc4_fields)
    frozen: bool
    immutable: bool = attrs.field(init=False)
    source_location: SourceLocation | None = attrs.field(default=None, eq=False)
    arc4_name: str = attrs.field(init=False, eq=False)
    native_type: None = attrs.field(default=None, init=False)
    desc: str | None = None

    @immutable.default
    def _immutable(self) -> bool:
        return self.frozen and all(typ.immutable for typ in self.fields.values())

    @arc4_name.default
    def _arc4_name(self) -> str:
        return f"({','.join(item.arc4_name for item in self.types)})"

    @cached_property
    def names(self) -> tuple[str, ...]:
        return tuple(self.fields.keys())

    @cached_property
    def types(self) -> tuple[ARC4Type, ...]:
        return tuple(self.fields.values())

    def can_encode_type(self, wtype: WType) -> bool:
        return super().can_encode_type(wtype) or (
            _is_arc4_encodeable_tuple(wtype, self.types)
            and (wtype.names is None or wtype.names == self.names)
        )


arc4_byte_alias: typing.Final = ARC4UIntN(
    n=8,
    arc4_name="byte",
    source_location=None,
)

arc4_string_alias: typing.Final = ARC4DynamicArray(
    arc4_name="string",
    element_type=arc4_byte_alias,
    native_type=string_wtype,
    immutable=True,
    source_location=None,
)

arc4_address_alias: typing.Final = ARC4StaticArray(
    arc4_name="address",
    element_type=arc4_byte_alias,
    native_type=account_wtype,
    array_size=32,
    immutable=True,
    source_location=None,
)


def persistable_stack_type(
    wtype: WType, location: SourceLocation
) -> typing.Literal[AVMType.uint64, AVMType.bytes]:
    match _storage_type_or_error(wtype):
        case str(error):
            raise CodeError(error, location=location)
        case result:
            return result


def validate_persistable(wtype: WType, location: SourceLocation) -> bool:
    match _storage_type_or_error(wtype):
        case str(error):
            logger.error(error, location=location)
            return False
        case _:
            return True


def _storage_type_or_error(wtype: WType) -> str | typing.Literal[AVMType.uint64, AVMType.bytes]:
    if wtype.ephemeral:
        return "ephemeral types (such as transaction related types) are not suitable for storage"
    if wtype.scalar_type is None:
        return "type is not suitable for storage"
    return wtype.scalar_type
