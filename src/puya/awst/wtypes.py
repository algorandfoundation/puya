import abc
import enum
import typing
from collections.abc import Mapping
from functools import cached_property

import attrs
from immutabledict import immutabledict

from puya import log
from puya.avm import AVMType, TransactionType
from puya.awst.visitors import ARC4WTypeVisitor, WTypeVisitor
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puya.utils import unique

logger = log.get_logger(__name__)


@enum.unique
class _ValueType(enum.Enum):
    """
    This enum differentiates between different types of runtime representations.
    """

    uint64 = enum.auto()  # the value is always a single uint64
    bytes = enum.auto()  # the value is always a single byte-slice
    reference = enum.auto()  # the value is some sort of "pointer" to the actual data
    composite = enum.auto()  # the value can actually be backed at runtime by multiple values
    none = enum.auto()  # there is no value, it's only a type

    @property
    def avm_type(self) -> typing.Literal[AVMType.uint64, AVMType.bytes, None]:
        match self:
            case _ValueType.uint64:
                return AVMType.uint64
            case _ValueType.bytes:
                return AVMType.bytes
            case _ValueType.composite | _ValueType.none | _ValueType.reference:
                return None


@attrs.frozen
class _TypeSemanticsData:
    # these are internal details that shouldn't be exposed via (de-)serialization,
    # and shouldn't be referenced from the puyapy front-end either
    value_type: _ValueType
    persistable: bool | None

    def __attrs_post_init__(self) -> None:
        if self.value_type is _ValueType.none:
            assert self.persistable is False
        if self.persistable is None:
            assert self.value_type is _ValueType.composite


@enum.unique
class _TypeSemantics(enum.Enum):
    persistable_uint64 = _TypeSemanticsData(
        value_type=_ValueType.uint64,
        persistable=True,
    )
    persistable_bytes = _TypeSemanticsData(
        value_type=_ValueType.bytes,
        persistable=True,
    )
    maybe_persistable_composite = _TypeSemanticsData(
        value_type=_ValueType.composite,
        persistable=None,
    )
    ephemeral_uint64 = _TypeSemanticsData(
        value_type=_ValueType.uint64,
        persistable=False,
    )
    ephemeral_composite = _TypeSemanticsData(
        value_type=_ValueType.composite,
        persistable=False,
    )
    ephemeral_reference = _TypeSemanticsData(
        value_type=_ValueType.reference,
        persistable=False,
    )
    static_type = _TypeSemanticsData(
        value_type=_ValueType.none,
        persistable=False,
    )


@attrs.frozen(kw_only=True)
class WType:
    name: str
    # immutable is defined as a validated field as a way of locking down the value without
    # breaking current serialization, it is not part of _TypeSemantics as there are some
    # limited cases where this value is controlled by user type definitions which
    # are handled explicitly by subclasses
    immutable: bool = attrs.field(default=True, validator=attrs.validators.in_([True]))
    # an aggregate is a type which contains other types which are user defined,
    # e.g. arrays, structs, tuples
    is_aggregate: bool = attrs.field(default=False, init=False)
    """
    Does this type have immutable semantics, if False and a stack based value
    then this will force a copy when aliasing the value.
    """
    _type_semantics: _TypeSemantics = attrs.field(init=False)

    _type_semantics_registry: typing.ClassVar[dict[str, _TypeSemantics]] = {}

    @classmethod
    def register_basic_type(cls, name: str, semantics: _TypeSemantics) -> "WType":
        assert (
            name not in cls._type_semantics_registry
        ), f"double registration of basic WType {name!r}"
        assert cls is WType, "register_basic_type should only be called via WType"
        cls._type_semantics_registry[name] = semantics
        return cls(name=name)

    @property
    def scalar_type(self) -> typing.Literal[AVMType.uint64, AVMType.bytes, None]:
        """the (unbounded) AVM stack type, if any"""
        return self._type_semantics.value.value_type.avm_type

    @property
    def persistable(self) -> bool:
        result = self._type_semantics.value.persistable
        if result is None:
            raise InternalError(
                "maybe-persistable composite types must implement property override"
            )
        return result

    @property
    def is_reference(self) -> bool:
        return self._type_semantics.value.value_type is _ValueType.reference

    @_type_semantics.default
    def _type_semantics_factory(self) -> _TypeSemantics:
        return self._type_semantics_registry[self.name]

    def __str__(self) -> str:
        return self.name

    def accept[T](self, visitor: WTypeVisitor[T]) -> T:
        assert type(self) is WType
        return visitor.visit_basic_type(self)


# region Basic WTypes
void_wtype: typing.Final = WType.register_basic_type(
    name="void",
    semantics=_TypeSemantics.static_type,
)
bool_wtype: typing.Final = WType.register_basic_type(
    name="bool",
    semantics=_TypeSemantics.persistable_uint64,
)
uint64_wtype: typing.Final = WType.register_basic_type(
    name="uint64",
    semantics=_TypeSemantics.persistable_uint64,
)
biguint_wtype: typing.Final = WType.register_basic_type(
    name="biguint",
    semantics=_TypeSemantics.persistable_bytes,
)
string_wtype: typing.Final = WType.register_basic_type(
    name="string",
    semantics=_TypeSemantics.persistable_bytes,
)
asset_wtype: typing.Final = WType.register_basic_type(
    name="asset",
    semantics=_TypeSemantics.persistable_uint64,
)
account_wtype: typing.Final = WType.register_basic_type(
    name="account",
    semantics=_TypeSemantics.persistable_bytes,
)
application_wtype: typing.Final = WType.register_basic_type(
    name="application",
    semantics=_TypeSemantics.persistable_uint64,
)
state_key: typing.Final = WType.register_basic_type(
    name="state_key",
    semantics=_TypeSemantics.persistable_bytes,
)
box_key: typing.Final = WType.register_basic_type(
    name="box_key",
    semantics=_TypeSemantics.persistable_bytes,
)
uint64_range_wtype: typing.Final = WType.register_basic_type(
    name="uint64_range",
    semantics=_TypeSemantics.static_type,
)
# endregion


class _WTypeInstance(WType, abc.ABC):
    @typing.override
    @abc.abstractmethod
    def accept[T](self, visitor: WTypeVisitor[T]) -> T: ...


@attrs.frozen(kw_only=True)
class BytesWType(_WTypeInstance):
    length: int | None = attrs.field(validator=attrs.validators.optional(attrs.validators.ge(0)))
    name: str = attrs.field(init=False, eq=False)
    _type_semantics: _TypeSemantics = attrs.field(
        default=_TypeSemantics.persistable_bytes, init=False
    )
    immutable: bool = attrs.field(default=True, init=False)

    @name.default
    def _name_factory(self) -> str:
        return "bytes" if self.length is None else f"bytes[{self.length}]"

    def accept[T](self, visitor: WTypeVisitor[T]) -> T:
        return visitor.visit_bytes_type(self)


bytes_wtype: typing.Final = BytesWType(length=None)


@attrs.frozen
class WEnumeration(_WTypeInstance):
    sequence_type: WType
    name: str = attrs.field(init=False)
    _type_semantics: _TypeSemantics = attrs.field(default=_TypeSemantics.static_type, init=False)

    @name.default
    def _name_factory(self) -> str:
        return f"enumerate_{self.sequence_type.name}"

    @typing.override
    def accept[T](self, visitor: WTypeVisitor[T]) -> T:
        return visitor.visit_enumeration_type(self)


@typing.final
@attrs.frozen
class WGroupTransaction(_WTypeInstance):
    transaction_type: TransactionType | None
    name: str = attrs.field()
    _type_semantics: _TypeSemantics = attrs.field(
        default=_TypeSemantics.ephemeral_uint64, init=False
    )

    @name.default
    def _name(self) -> str:
        name = "group_transaction"
        if self.transaction_type:
            name = f"{name}_{self.transaction_type.name}"
        return name

    @typing.override
    def accept[T](self, visitor: WTypeVisitor[T]) -> T:
        return visitor.visit_group_transaction_type(self)


@typing.final
@attrs.frozen
class WInnerTransactionFields(_WTypeInstance):
    transaction_type: TransactionType | None
    name: str = attrs.field()
    _type_semantics: _TypeSemantics = attrs.field(
        default=_TypeSemantics.ephemeral_composite, init=False
    )

    @name.default
    def _name(self) -> str:
        name = "inner_transaction_fields"
        if self.transaction_type:
            name = f"{name}_{self.transaction_type.name}"
        return name

    @typing.override
    def accept[T](self, visitor: WTypeVisitor[T]) -> T:
        return visitor.visit_inner_transaction_fields_type(self)


@typing.final
@attrs.frozen
class WInnerTransaction(_WTypeInstance):
    transaction_type: TransactionType | None
    name: str = attrs.field()
    _type_semantics: _TypeSemantics = attrs.field(
        default=_TypeSemantics.ephemeral_composite, init=False
    )

    @name.default
    def _name(self) -> str:
        name = "inner_transaction"
        if self.transaction_type:
            name = f"{name}_{self.transaction_type.name}"
        return name

    @typing.override
    def accept[T](self, visitor: WTypeVisitor[T]) -> T:
        return visitor.visit_inner_transaction_type(self)


@typing.final
@attrs.frozen
class ReferenceArray(_WTypeInstance):
    element_type: WType = attrs.field()
    name: str = attrs.field(init=False)
    immutable: bool = attrs.field(default=False, init=False)
    is_aggregate: bool = attrs.field(default=True, init=False)
    _type_semantics: _TypeSemantics = attrs.field(
        default=_TypeSemantics.ephemeral_reference, init=False
    )
    source_location: SourceLocation | None = attrs.field(eq=False)

    @element_type.validator
    def _element_type_validator(self, _: object, element_type: WType) -> None:
        if element_type == void_wtype:
            raise CodeError("array element type cannot be void", self.source_location)
        if not element_type.immutable:
            logger.error("arrays must have immutable elements", location=self.source_location)

    @name.default
    def _name(self) -> str:
        return f"ref_array<{self.element_type.name}>"

    @typing.override
    def accept[T](self, visitor: WTypeVisitor[T]) -> T:
        return visitor.visit_reference_array(self)


@typing.final
@attrs.frozen(eq=False)
class WTuple(_WTypeInstance):
    types: tuple[WType, ...] = attrs.field(converter=tuple[WType, ...])
    source_location: SourceLocation | None = attrs.field(default=None)
    immutable: bool = attrs.field(init=False)
    name: str = attrs.field(kw_only=True)
    names: tuple[str, ...] | None = attrs.field(default=None)
    desc: str | None = None
    is_aggregate: bool = attrs.field(default=True, init=False)
    _type_semantics: _TypeSemantics = attrs.field(
        default=_TypeSemantics.maybe_persistable_composite, init=False
    )

    @property
    @typing.override
    def persistable(self) -> bool:
        return all(t.persistable for t in self.types)

    @immutable.default
    def _immutable(self) -> bool:
        return all(typ.immutable for typ in self.types)

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

    @typing.override
    def accept[T](self, visitor: WTypeVisitor[T]) -> T:
        return visitor.visit_tuple_type(self)


@attrs.frozen(kw_only=True)
class ARC4Type(_WTypeInstance):
    arc4_alias: str | None = attrs.field(default=None, eq=False)
    _type_semantics: _TypeSemantics = attrs.field(
        default=_TypeSemantics.persistable_bytes, init=False
    )

    @typing.override
    def accept[T](self, visitor: ARC4WTypeVisitor[T]) -> T:
        return visitor.visit_basic_arc4_type(self)


arc4_bool_wtype: typing.Final = ARC4Type(
    name="arc4.bool",
)


class _ARC4WTypeInstance(ARC4Type, abc.ABC):
    @typing.override
    @abc.abstractmethod
    def accept[T](self, visitor: ARC4WTypeVisitor[T]) -> T: ...


@typing.final
@attrs.frozen(kw_only=True)
class ARC4UIntN(_ARC4WTypeInstance):
    immutable: bool = attrs.field(default=True, init=False)
    n: int = attrs.field()
    name: str = attrs.field(init=False)
    source_location: SourceLocation | None = attrs.field(default=None, eq=False)

    @n.validator
    def _n_validator(self, _attribute: object, n: int) -> None:
        if not (n % 8 == 0):
            raise CodeError("Bit size must be multiple of 8", self.source_location)
        if not (8 <= n <= 512):
            raise CodeError("Bit size must be between 8 and 512 inclusive", self.source_location)

    @name.default
    def _name(self) -> str:
        return f"arc4.uint{self.n}"

    @typing.override
    def accept[T](self, visitor: ARC4WTypeVisitor[T]) -> T:
        return visitor.visit_arc4_uint(self)


@typing.final
@attrs.frozen(kw_only=True)
class ARC4UFixedNxM(_ARC4WTypeInstance):
    n: int = attrs.field()
    m: int = attrs.field()
    immutable: bool = attrs.field(default=True, init=False)
    name: str = attrs.field(init=False)
    source_location: SourceLocation | None = attrs.field(default=None, eq=False)

    @name.default
    def _name(self) -> str:
        return f"arc4.ufixed{self.n}x{self.m}"

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

    @typing.override
    def accept[T](self, visitor: ARC4WTypeVisitor[T]) -> T:
        return visitor.visit_arc4_ufixed(self)


@typing.final
@attrs.frozen(kw_only=True)
class ARC4Tuple(_ARC4WTypeInstance):
    arc4_alias: None = attrs.field(default=None, init=False)
    source_location: SourceLocation | None = attrs.field(default=None, eq=False)
    types: tuple[WType, ...] = attrs.field(converter=tuple[WType, ...])
    name: str = attrs.field(init=False)
    immutable: bool = attrs.field(init=False)
    is_aggregate: bool = attrs.field(default=True, init=False)

    @name.default
    def _name(self) -> str:
        return f"arc4.tuple<{','.join(t.name for t in self.types)}>"

    @immutable.default
    def _immutable(self) -> bool:
        return all(typ.immutable for typ in self.types)

    @typing.override
    def accept[T](self, visitor: ARC4WTypeVisitor[T]) -> T:
        return visitor.visit_arc4_tuple(self)

    @types.validator
    def _types_validator(self, _attribute: object, value: tuple[WType]) -> None:
        loc = self.source_location
        if any(not typ.persistable for typ in value):
            raise CodeError("ARC-4 tuples can only contain persistable elements", loc)


@attrs.frozen(kw_only=True)
class ARC4Array(_ARC4WTypeInstance, abc.ABC):
    source_location: SourceLocation | None = attrs.field(default=None, eq=False)
    immutable: bool = False
    element_type: WType = attrs.field()
    is_aggregate: bool = attrs.field(init=False)

    @is_aggregate.default
    def _aggregate_default(self) -> bool:
        return self.arc4_alias is None

    @element_type.validator
    def _element_type_validator(self, _attribute: object, value: WType) -> None:
        loc = self.source_location
        if not value.persistable:
            raise CodeError("arrays can only contain persistable elements", loc)
        if self.immutable and not value.immutable:
            raise CodeError("immutable arrays must have immutable elements", loc)


@attrs.frozen(kw_only=True)
class ARC4DynamicArray(ARC4Array):
    name: str = attrs.field(init=False)

    @name.default
    def _name(self) -> str:
        return f"arc4.dynamic_array<{self.element_type.name}>"

    @typing.override
    def accept[T](self, visitor: ARC4WTypeVisitor[T]) -> T:
        return visitor.visit_arc4_dynamic_array(self)


@typing.final
@attrs.frozen(kw_only=True)
class ARC4StaticArray(ARC4Array):
    array_size: int = attrs.field(validator=attrs.validators.ge(0))
    name: str = attrs.field(init=False)

    @name.default
    def _name(self) -> str:
        return f"arc4.static_array<{self.element_type.name}, {self.array_size}>"

    @typing.override
    def accept[T](self, visitor: ARC4WTypeVisitor[T]) -> T:
        return visitor.visit_arc4_static_array(self)


@typing.final
@attrs.frozen(kw_only=True)
class ARC4Struct(_ARC4WTypeInstance):
    arc4_alias: None = attrs.field(default=None, init=False)
    fields: immutabledict[str, WType] = attrs.field(converter=immutabledict[str, WType])
    frozen: bool
    immutable: bool = attrs.field(init=False)
    source_location: SourceLocation | None = attrs.field(default=None, eq=False)
    desc: str | None = None
    is_aggregate: bool = attrs.field(default=True, init=False)

    @fields.validator
    def _fields_validator(self, _attribute: object, value: immutabledict[str, WType]) -> None:
        unpersistable = [
            field_name for field_name, field_type in value.items() if not field_type.persistable
        ]
        if unpersistable:
            raise CodeError(
                "invalid ARC-4 Struct declaration,"
                f" the following fields are not persistable: {', '.join(unpersistable)}",
            )

    @immutable.default
    def _immutable(self) -> bool:
        return self.frozen and all(typ.immutable for typ in self.fields.values())

    @cached_property
    def names(self) -> tuple[str, ...]:
        return tuple(self.fields.keys())

    @cached_property
    def types(self) -> tuple[WType, ...]:
        return tuple(self.fields.values())

    @typing.override
    def accept[T](self, visitor: ARC4WTypeVisitor[T]) -> T:
        return visitor.visit_arc4_struct(self)


# region ARC4 aliases
arc4_byte_alias: typing.Final = ARC4UIntN(
    n=8,
    arc4_alias="byte",
    source_location=None,
)
arc4_string_alias: typing.Final = ARC4DynamicArray(
    arc4_alias="string",
    element_type=arc4_byte_alias,
    immutable=True,
    source_location=None,
)
arc4_address_alias: typing.Final = ARC4StaticArray(
    arc4_alias="address",
    element_type=arc4_byte_alias,
    array_size=32,
    immutable=True,
    source_location=None,
)
# endregion
