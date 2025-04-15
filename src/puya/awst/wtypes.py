import abc
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
_NOT_SET: typing.Any = object()


# _TypeSemantics is used to define some semantics for WTypes without breaking current serialization
# by continuing to allow these values as parameters and then validating they are correct.
# Definitions can be found after the WType class definitions
@attrs.frozen
class _TypeSemantics:
    scalar_type: typing.Literal[AVMType.uint64, AVMType.bytes, None]
    # TODO: once front ends are no longer using this value, invert it's meaning and name it
    #       something like storable
    ephemeral: bool
    value_type: bool


def _type_semantics_field() -> typing.Any:  # noqa: ANN401
    def converter(value: object, wtype: "WType", field: attrs.Attribute) -> object:  # type: ignore[type-arg]
        """
        Validates field matches defined type semantics value, or falls back to defined value
        if not set.
        """
        try:
            type_data = _TYPE_SEMANTICS[wtype.name]
        # may raise AttributeError if type isn't fully constructed
        except (KeyError, AttributeError):
            try:
                type_data = _TYPE_SEMANTICS[type(wtype)]
            except KeyError:
                raise InternalError(f"no _TypeSemantics defined for {wtype}") from None
        expected_value = getattr(type_data, field.name)
        # using a sentinel value as a work-around so None can be used as an explicit value
        if value is _NOT_SET:
            value = expected_value
        elif value != expected_value:
            raise InternalError(f"invalid {field.name} value for {wtype=}")
        return value

    return attrs.field(
        default=_NOT_SET,
        converter=attrs.Converter(  # type: ignore[call-overload]
            converter,
            takes_self=True,
            takes_field=True,
        ),
    )


@attrs.frozen(kw_only=True)
class WType:
    name: str
    scalar_type: typing.Literal[AVMType.uint64, AVMType.bytes, None] = _type_semantics_field()
    "the (unbounded) AVM stack type, if any"
    ephemeral: bool = _type_semantics_field()
    """ephemeral types are not suitable for naive storage / persistence,
     even if their underlying type is a simple stack value"""
    value_type: bool = _type_semantics_field()
    """True if a value type, False if a static type that has no value at runtime"""
    immutable: bool = attrs.field(default=True, validator=attrs.validators.in_([True]))
    """
    Does this type have immutable semantics, if False and a stack based value
    then this will force a copy when aliasing the value.
    """
    # immutable is defined as a validated field as a way of locking down the value without
    # breaking current serialization, it is not part of _TypeSemantics as there are some
    # limited cases where this value is controlled by user type definitions which
    # are handled explicitly by subclasses

    def __attrs_post_init__(self) -> None:
        if not self.value_type and self.scalar_type is not None:
            raise InternalError("if a type has a scalar type it should be a value type")

    def __str__(self) -> str:
        return self.name


@attrs.frozen
class WEnumeration(WType):
    sequence_type: WType
    name: str = attrs.field(init=False)

    @name.default
    def _name_factory(self) -> str:
        return f"enumerate_{self.sequence_type.name}"


@typing.final
@attrs.frozen
class WGroupTransaction(WType):
    transaction_type: TransactionType | None
    name: str = attrs.field()

    @name.default
    def _name(self) -> str:
        name = "group_transaction"
        if self.transaction_type:
            name = f"{name}_{self.transaction_type.name}"
        return name


@typing.final
@attrs.frozen
class WInnerTransactionFields(WType):
    transaction_type: TransactionType | None
    name: str = attrs.field()

    @name.default
    def _name(self) -> str:
        name = "inner_transaction_fields"
        if self.transaction_type:
            name = f"{name}_{self.transaction_type.name}"
        return name


@typing.final
@attrs.frozen
class WInnerTransaction(WType):
    transaction_type: TransactionType | None
    name: str = attrs.field()

    @name.default
    def _name(self) -> str:
        name = "inner_transaction"
        if self.transaction_type:
            name = f"{name}_{self.transaction_type.name}"
        return name


@typing.final
@attrs.frozen
class WStructType(WType):
    fields: immutabledict[str, WType] = attrs.field(converter=immutabledict)
    frozen: bool
    immutable: bool = attrs.field(init=False)
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


@attrs.frozen
class NativeArray(WType, abc.ABC):
    element_type: WType = attrs.field()
    source_location: SourceLocation | None = attrs.field(eq=False)

    @element_type.validator
    def _element_type_validator(self, _: object, element_type: WType) -> None:
        if element_type == void_wtype:
            raise CodeError("array element type cannot be void", self.source_location)
        if not element_type.immutable:
            logger.error("arrays must have immutable elements", location=self.source_location)


@typing.final
@attrs.frozen
class StackArray(NativeArray):
    name: str = attrs.field(init=False)
    immutable: bool = attrs.field(default=True, init=False)

    @name.default
    def _name(self) -> str:
        return f"stack_array<{self.element_type.name}>"


@typing.final
@attrs.frozen
class ReferenceArray(NativeArray):
    name: str = attrs.field(init=False)
    immutable: bool = attrs.field(default=False, init=False)

    @name.default
    def _name(self) -> str:
        return f"ref_array<{self.element_type.name}>"


@typing.final
@attrs.frozen(eq=False)
class WTuple(WType):
    types: tuple[WType, ...] = attrs.field(converter=tuple[WType, ...])
    source_location: SourceLocation | None = attrs.field(default=None)
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
    arc4_name: str = attrs.field(eq=False)  # exclude from equality in case of aliasing


@typing.final
@attrs.frozen(kw_only=True)
class ARC4UIntN(ARC4Type):
    immutable: bool = attrs.field(default=True, init=False)
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


@typing.final
@attrs.frozen(kw_only=True)
class ARC4UFixedNxM(ARC4Type):
    n: int = attrs.field()
    m: int = attrs.field()
    immutable: bool = attrs.field(default=True, init=False)
    arc4_name: str = attrs.field(init=False, eq=False)
    name: str = attrs.field(init=False)
    source_location: SourceLocation | None = attrs.field(default=None, eq=False)

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


def _required_arc4_wtypes(
    wtypes: Iterable[WType], tup: attrs.AttrsInstance
) -> tuple[ARC4Type, ...]:
    invalid_elements = [idx for idx, wtype in enumerate(wtypes) if not isinstance(wtype, ARC4Type)]
    if invalid_elements:
        *head, tail = map(str, invalid_elements)
        if head:
            invalid_elements_desc = f"{', '.join(head)} and {tail}"
        else:
            invalid_elements_desc = tail
        raise CodeError(
            f"ARC-4 tuples can only contain ARC-4 types but elements {invalid_elements_desc}"
            " are not ARC-4 types",
            tup.source_location,  # type: ignore[attr-defined]
        )

    return tuple(wtypes)  # type: ignore[arg-type]


@typing.final
@attrs.frozen(kw_only=True)
class ARC4Tuple(ARC4Type):
    source_location: SourceLocation | None = attrs.field(default=None, eq=False)
    types: tuple[ARC4Type, ...] = attrs.field(
        converter=attrs.Converter(_required_arc4_wtypes, takes_self=True)  # type: ignore[misc]
    )
    name: str = attrs.field(init=False)
    arc4_name: str = attrs.field(init=False, eq=False)
    immutable: bool = attrs.field(init=False)

    @name.default
    def _name(self) -> str:
        return f"arc4.tuple<{','.join(t.name for t in self.types)}>"

    @arc4_name.default
    def _arc4_name(self) -> str:
        return f"({','.join(item.arc4_name for item in self.types)})"

    @immutable.default
    def _immutable(self) -> bool:
        return all(typ.immutable for typ in self.types)


def _array_requires_arc4_type(wtype: WType, arr: attrs.AttrsInstance) -> ARC4Type:
    assert isinstance(arr, ARC4Array)
    if not isinstance(wtype, ARC4Type):
        raise CodeError("ARC-4 arrays can only contain ARC-4 elements", arr.source_location)
    return wtype


@attrs.frozen(kw_only=True)
class ARC4Array(ARC4Type):
    source_location: SourceLocation | None = attrs.field(default=None, eq=False)
    element_type: ARC4Type = attrs.field(
        converter=attrs.Converter(_array_requires_arc4_type, takes_self=True)  # type: ignore[misc]
    )
    immutable: bool = False


@typing.final
@attrs.frozen(kw_only=True)
class ARC4DynamicArray(ARC4Array):
    name: str = attrs.field(init=False)
    arc4_name: str = attrs.field(eq=False)

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
            "invalid ARC-4 Struct declaration,"
            f" the following fields are not ARC-4 encoded types: {', '.join(non_arc4_fields)}",
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


_persistable_uint64 = _TypeSemantics(
    scalar_type=AVMType.uint64,
    ephemeral=False,
    value_type=True,
)
_persistable_bytes = _TypeSemantics(
    scalar_type=AVMType.bytes,
    ephemeral=False,
    value_type=True,
)
_persistable_aggregate = _TypeSemantics(
    scalar_type=None,
    ephemeral=False,
    value_type=True,
)
_ephemeral_uint64 = _TypeSemantics(
    scalar_type=AVMType.uint64,
    ephemeral=True,
    value_type=True,
)
_ephemeral_aggregate = _TypeSemantics(
    scalar_type=None,
    ephemeral=True,
    value_type=True,
)
_static_type = _TypeSemantics(
    scalar_type=None,
    ephemeral=False,
    value_type=False,
)
_TYPE_SEMANTICS: immutabledict[type | str, _TypeSemantics] = immutabledict(
    {
        "bool": _persistable_uint64,
        "uint64": _persistable_uint64,
        "asset": _persistable_uint64,
        "application": _persistable_uint64,
        "biguint": _persistable_bytes,
        "bytes": _persistable_bytes,
        "string": _persistable_bytes,
        "account": _persistable_bytes,
        "state_key": _persistable_bytes,
        "box_key": _persistable_bytes,
        ARC4Type: _persistable_bytes,
        ARC4UIntN: _persistable_bytes,
        ARC4UFixedNxM: _persistable_bytes,
        ARC4Tuple: _persistable_bytes,
        ARC4StaticArray: _persistable_bytes,
        ARC4DynamicArray: _persistable_bytes,
        ARC4Struct: _persistable_bytes,
        StackArray: _persistable_bytes,
        WGroupTransaction: _ephemeral_uint64,
        WTuple: _persistable_aggregate,
        WStructType: _persistable_aggregate,
        WInnerTransactionFields: _ephemeral_aggregate,
        WInnerTransaction: _ephemeral_aggregate,
        ReferenceArray: _ephemeral_aggregate,
        "void": _static_type,
        "uint64_range": _static_type,
        WEnumeration: _static_type,
    }
)


void_wtype: typing.Final = WType(name="void")
bool_wtype: typing.Final = WType(name="bool")
uint64_wtype: typing.Final = WType(name="uint64")
biguint_wtype: typing.Final = WType(name="biguint")
bytes_wtype: typing.Final = WType(name="bytes")
string_wtype: typing.Final = WType(name="string")
asset_wtype: typing.Final = WType(name="asset")
account_wtype: typing.Final = WType(name="account")
application_wtype: typing.Final = WType(name="application")
state_key: typing.Final = WType(name="state_key")
box_key: typing.Final = WType(name="box_key")
uint64_range_wtype: typing.Final = WType(name="uint64_range")
arc4_bool_wtype: typing.Final = ARC4Type(
    name="arc4.bool",
    arc4_name="bool",
)
arc4_byte_alias: typing.Final = ARC4UIntN(
    n=8,
    arc4_name="byte",
    source_location=None,
)
arc4_string_alias: typing.Final = ARC4DynamicArray(
    arc4_name="string",
    element_type=arc4_byte_alias,
    immutable=True,
    source_location=None,
)
arc4_address_alias: typing.Final = ARC4StaticArray(
    arc4_name="address",
    element_type=arc4_byte_alias,
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
