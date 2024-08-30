import typing
from collections.abc import Iterable, Mapping, Sequence
from functools import cached_property

import attrs
from immutabledict import immutabledict

from puya import log
from puya.avm_type import AVMType
from puya.errors import CodeError, InternalError
from puya.models import TransactionType
from puya.parse import SourceLocation

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
@attrs.frozen(init=False)
class WStructType(WType):
    fields: Mapping[str, WType] = attrs.field(converter=immutabledict)
    scalar_type: None = attrs.field(default=None, init=False)

    def __init__(
        self,
        fields: Mapping[str, WType],
        *,
        name: str,
        immutable: bool,
        source_location: SourceLocation | None,
    ):
        if not fields:
            raise CodeError("struct needs fields", source_location)
        if void_wtype in fields.values():
            raise CodeError("struct should not contain void types", source_location)
        self.__attrs_init__(name=name, fields=fields, immutable=immutable)


@typing.final
@attrs.frozen(init=False)
class WArray(WType):
    element_type: WType
    scalar_type: None = attrs.field(default=None, init=False)

    def __init__(self, element_type: WType, source_location: SourceLocation | None):
        if element_type == void_wtype:
            raise CodeError("array element type cannot be void", source_location)
        name = f"array<{element_type.name}>"
        self.__attrs_init__(name=name, element_type=element_type, immutable=False)


@typing.final
@attrs.frozen
class WTuple(WType):
    types: Sequence[WType] = attrs.field(converter=tuple[WType, ...])
    scalar_type: None = attrs.field(default=None, init=False)
    immutable: bool = attrs.field(default=True, init=False)
    name: str = attrs.field(init=False)
    source_location: SourceLocation | None = attrs.field(default=None, eq=False)

    @types.validator
    def _types_validator(self, _attribute: object, types: Sequence[WType]) -> None:
        if not types:
            raise CodeError("empty tuples are not supported", self.source_location)
        if void_wtype in types:
            raise CodeError("tuple should not contain void types", self.source_location)

    @name.default
    def _name(self) -> str:
        return f"tuple<{','.join([t.name for t in self.types])}>"


@attrs.frozen(kw_only=True)
class ARC4Type(WType):
    scalar_type: typing.Literal[AVMType.bytes] = attrs.field(default=AVMType.bytes, init=False)
    arc4_name: str = attrs.field(eq=False)  # exclude from equality in case of aliasing
    decode_type: WType | None

    @property
    def encodeable_types(self) -> Sequence[WType]:
        if self.decode_type:
            return (self.decode_type,)
        else:
            return ()


arc4_bool_wtype: typing.Final = ARC4Type(
    name="arc4.bool",
    arc4_name="bool",
    immutable=True,
    decode_type=bool_wtype,
)


@typing.final
@attrs.frozen(kw_only=True)
class ARC4UIntN(ARC4Type):
    immutable: bool = attrs.field(default=True, init=False)
    decode_type: WType = attrs.field()
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

    @decode_type.validator
    def _decode_type_validator(self, _attribute: object, decode_type: WType) -> None:
        if decode_type == uint64_wtype:
            if self.n > 64:
                raise InternalError(
                    f"ARC-4 UIntN type received decode type {decode_type},"
                    f" which is smaller than size {self.n}",
                    self.source_location,
                )
        elif decode_type == biguint_wtype:
            pass
        else:
            raise InternalError(
                f"Unhandled decode_type for ARC-4 UIntN: {decode_type}", self.source_location
            )

    @arc4_name.default
    def _arc4_name(self) -> str:
        return f"uint{self.n}"

    @name.default
    def _name(self) -> str:
        return f"arc4.{self._arc4_name()}"

    @property
    def encodeable_types(self) -> Sequence[WType]:
        return *super().encodeable_types, bool_wtype, uint64_wtype, biguint_wtype


@typing.final
@attrs.frozen(kw_only=True)
class ARC4UFixedNxM(ARC4Type):
    n: int = attrs.field()
    m: int = attrs.field()
    immutable: bool = attrs.field(default=True, init=False)
    arc4_name: str = attrs.field(init=False, eq=False)
    name: str = attrs.field(init=False)
    source_location: SourceLocation | None = attrs.field(default=None, eq=False)
    decode_type = attrs.field(default=None, init=False)

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


def _required_arc4_wtypes(wtypes: Iterable[WType]) -> Sequence[ARC4Type]:
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
    types: Sequence[ARC4Type] = attrs.field(converter=_required_arc4_wtypes)
    name: str = attrs.field(init=False)
    arc4_name: str = attrs.field(init=False, eq=False)
    immutable: bool = attrs.field(init=False)
    decode_type: WTuple = attrs.field(init=False)

    @name.default
    def _name(self) -> str:
        return f"arc4.tuple<{','.join(t.name for t in self.types)}>"

    @arc4_name.default
    def _arc4_name(self) -> str:
        return f"({','.join(item.arc4_name for item in self.types)})"

    @immutable.default
    def _immutable(self) -> bool:
        return all(typ.immutable for typ in self.types)

    @decode_type.default
    def _decode_type(self) -> WTuple:
        return WTuple(self.types, self.source_location)


def _expect_arc4_type(wtype: WType) -> ARC4Type:
    if not isinstance(wtype, ARC4Type):
        raise CodeError(f"expected ARC4 type: {wtype}")
    return wtype


@attrs.frozen(kw_only=True)
class ARC4Array(ARC4Type):
    element_type: ARC4Type = attrs.field(converter=_expect_arc4_type)
    decode_type: WType | None = None
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
            "Invalid ARC4 Struct declaration,"
            f" the following fields are not ARC4 encoded types: {', '.join(non_arc4_fields)}",
        )
    return immutabledict(fields)


@typing.final
@attrs.frozen(kw_only=True)
class ARC4Struct(ARC4Type):
    fields: Mapping[str, ARC4Type] = attrs.field(converter=_require_arc4_fields)
    immutable: bool = attrs.field()
    source_location: SourceLocation | None = attrs.field(default=None, eq=False)
    arc4_name: str = attrs.field(init=False, eq=False)
    decode_type: WType | None = None

    @immutable.default
    def _immutable(self) -> bool:
        return all(typ.immutable for typ in self.fields.values())

    @arc4_name.default
    def _arc4_name(self) -> str:
        return f"({','.join(item.arc4_name for item in self.types)})"

    @cached_property
    def names(self) -> Sequence[str]:
        return list(self.fields.keys())

    @cached_property
    def types(self) -> Sequence[ARC4Type]:
        return list(self.fields.values())


arc4_byte_alias: typing.Final = ARC4UIntN(
    n=8,
    arc4_name="byte",
    decode_type=uint64_wtype,
    source_location=None,
)

arc4_string_alias: typing.Final = ARC4DynamicArray(
    arc4_name="string",
    element_type=arc4_byte_alias,
    decode_type=string_wtype,
    immutable=True,
    source_location=None,
)

arc4_address_alias: typing.Final = ARC4StaticArray(
    arc4_name="address",
    element_type=arc4_byte_alias,
    decode_type=account_wtype,
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
