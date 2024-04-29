import base64
import typing
from collections.abc import Callable, Iterable, Mapping, Sequence
from functools import cached_property

import attrs
from immutabledict import immutabledict

from puya import algo_constants
from puya.awst_build import constants
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puya.utils import sha512_256_hash


def _all_literals_invalid(_value: object) -> bool:
    return False


LiteralValidator: typing.TypeAlias = Callable[[object], bool]


@attrs.frozen(str=False, kw_only=True)
class WType:
    name: str
    stub_name: str
    lvalue: bool = True  # TODO: this is currently just used by void...
    immutable: bool = True
    scalar: bool = True  # is this a single value on the stack?
    is_valid_literal: LiteralValidator = attrs.field(default=_all_literals_invalid, eq=False)

    def __str__(self) -> str:
        return self.stub_name


def is_valid_bool_literal(value: object) -> typing.TypeGuard[bool]:
    return isinstance(value, bool)


def _is_unsigned_int(value: object) -> typing.TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _uint_literal_validator(*, max_bits: int) -> Callable[[object], typing.TypeGuard[int]]:
    def validator(value: object) -> typing.TypeGuard[int]:
        return _is_unsigned_int(value) and value.bit_length() <= max_bits

    return validator


is_valid_uint64_literal = _uint_literal_validator(max_bits=64)


is_valid_biguint_literal = _uint_literal_validator(max_bits=algo_constants.MAX_BIGUINT_BITS)


def _bytes_literal_validator(
    *, min_size: int = 0, max_size: int = algo_constants.MAX_BYTES_LENGTH
) -> Callable[[object], typing.TypeGuard[bytes]]:
    def validator(value: object) -> typing.TypeGuard[bytes]:
        return isinstance(value, bytes) and min_size <= len(value) <= max_size

    return validator


is_valid_bytes_literal = _bytes_literal_validator()


def is_valid_account_literal(value: object) -> typing.TypeGuard[str]:
    return isinstance(value, str) and valid_address(value)


def is_valid_utf8_literal(value: object) -> typing.TypeGuard[str]:
    return isinstance(value, str) and is_valid_bytes_literal(value.encode("utf8"))


void_wtype: typing.Final = WType(
    name="void",
    stub_name="None",
    lvalue=False,
)

bool_wtype: typing.Final = WType(
    name="bool",
    stub_name="bool",
    is_valid_literal=is_valid_bool_literal,
)

uint64_wtype: typing.Final = WType(
    name="uint64",
    stub_name=constants.CLS_UINT64_ALIAS,
    is_valid_literal=is_valid_uint64_literal,
)

biguint_wtype: typing.Final = WType(
    name="biguint",
    stub_name=constants.CLS_BIGUINT_ALIAS,
    is_valid_literal=is_valid_biguint_literal,
)

bytes_wtype: typing.Final = WType(
    name="bytes",
    stub_name=constants.CLS_BYTES_ALIAS,
    is_valid_literal=is_valid_bytes_literal,
)
string_wtype: typing.Final = WType(
    name="string",
    stub_name=constants.CLS_STRING_ALIAS,
    is_valid_literal=is_valid_utf8_literal,
)
asset_wtype: typing.Final = WType(
    name="asset",
    stub_name=constants.CLS_ASSET_ALIAS,
    is_valid_literal=is_valid_uint64_literal,
)
state_key: typing.Final = WType(
    name="state_key",
    stub_name="n/a",  # TODO: seperation
    is_valid_literal=_bytes_literal_validator(max_size=algo_constants.MAX_STATE_KEY_LENGTH),
)
box_key: typing.Final = WType(
    name="box_key",
    stub_name="n/a",  # TODO: seperation
    is_valid_literal=_bytes_literal_validator(
        min_size=algo_constants.MIN_BOX_KEY_LENGTH, max_size=algo_constants.MAX_BOX_KEY_LENGTH
    ),
)

account_wtype: typing.Final = WType(
    name="account",
    stub_name=constants.CLS_ACCOUNT_ALIAS,
    is_valid_literal=is_valid_account_literal,
)

application_wtype: typing.Final = WType(
    name="application",
    stub_name=constants.CLS_APPLICATION_ALIAS,
    is_valid_literal=is_valid_uint64_literal,
)


@typing.final
@attrs.frozen(str=False, kw_only=True)
class WGroupTransaction(WType):
    transaction_type: constants.TransactionType | None
    scalar: bool = attrs.field(default=False, init=False)

    @classmethod
    def from_type(cls, transaction_type: constants.TransactionType | None) -> "WGroupTransaction":
        name = "group_transaction"
        if transaction_type:
            name = f"{name}_{transaction_type.name}"
        return cls(
            transaction_type=transaction_type,
            stub_name=constants.TRANSACTION_TYPE_TO_CLS[transaction_type].gtxn,
            name=name,
        )

    # TODO only allow int literals below max group size


@attrs.define
class WInnerTransactionFields(WType):
    transaction_type: constants.TransactionType | None
    scalar: bool = attrs.field(default=False, init=False)

    @classmethod
    def from_type(
        cls, transaction_type: constants.TransactionType | None
    ) -> "WInnerTransactionFields":
        name = "inner_transaction_fields"
        if transaction_type:
            name = f"{name}_{transaction_type.name}"
        return cls(
            transaction_type=transaction_type,
            stub_name=constants.TRANSACTION_TYPE_TO_CLS[transaction_type].itxn_fields,
            name=name,
        )


@attrs.define
class WInnerTransaction(WType):
    transaction_type: constants.TransactionType | None
    scalar: bool = attrs.field(default=False, init=False)

    @classmethod
    def from_type(cls, transaction_type: constants.TransactionType | None) -> "WInnerTransaction":
        name = "inner_transaction"
        if transaction_type:
            name = f"{name}_{transaction_type.name}"
        return cls(
            transaction_type=transaction_type,
            stub_name=constants.TRANSACTION_TYPE_TO_CLS[transaction_type].itxn_result,
            name=name,
        )


@attrs.define
class WBoxProxy(WType):
    content_wtype: WType = attrs.field()

    @classmethod
    def from_content_type(cls, content_wtype: WType) -> "WBoxProxy":
        return cls(
            content_wtype=content_wtype,
            name="box_proxy",
            stub_name=constants.CLS_BOX_PROXY_ALIAS,
        )


@attrs.define
class WBoxMapProxy(WType):
    content_wtype: WType = attrs.field()

    @classmethod
    def from_key_and_content_type(cls, content_wtype: WType) -> "WBoxMapProxy":
        return cls(
            content_wtype=content_wtype,
            name="box_map_proxy",
            stub_name=constants.CLS_BOX_MAP_PROXY_ALIAS,
        )


box_ref_proxy_type: typing.Final = WType(
    name="box_ref_proxy", stub_name=constants.CLS_BOX_REF_PROXY_ALIAS
)


@typing.final
@attrs.frozen(str=False, kw_only=True, init=False)
class WStructType(WType):
    fields: Mapping[str, WType] = attrs.field(converter=immutabledict)
    scalar: bool = attrs.field(default=False, init=False)

    def __init__(
        self,
        python_name: str,  # TODO: yeet me
        fields: Mapping[str, WType],
        immutable: bool,  # noqa: FBT001
        source_location: SourceLocation | None,
    ):
        if not fields:
            raise CodeError("struct needs fields", source_location)
        if void_wtype in fields.values():
            raise CodeError("struct should not contain void types", source_location)
        name = (
            "struct<"
            + ",".join(
                f"{field_name}:{field_type.name}" for field_name, field_type in fields.items()
            )
            + ">"
        )
        self.__attrs_init__(
            name=name,
            stub_name=python_name,
            immutable=immutable,
            fields=fields,
        )


@typing.final
@attrs.frozen(str=False, kw_only=True, init=False)
class WArray(WType):
    element_type: WType
    scalar: bool = attrs.field(default=False, init=False)

    def __init__(self, element_type: WType, source_location: SourceLocation | None):
        if element_type == void_wtype:
            raise CodeError("array element type cannot be void", source_location)
        name = f"array<{element_type.name}>"
        self.__attrs_init__(
            name=name,
            stub_name=f"{constants.CLS_ARRAY_ALIAS}[{element_type}]",
            immutable=False,
            element_type=element_type,
        )


@typing.final
@attrs.frozen(str=False, kw_only=True, init=False)
class WTuple(WType):
    types: tuple[WType, ...] = attrs.field(validator=[attrs.validators.min_len(1)])
    scalar: bool = attrs.field(default=False, init=False)

    def __init__(self, types: Iterable[WType], source_location: SourceLocation | None):
        types = tuple(types)
        if not types:
            raise CodeError("tuple needs types", source_location)
        if void_wtype in types:
            raise CodeError("tuple should not contain void types", source_location)
        name = f"tuple<{','.join([t.name for t in types])}>"
        python_name = f"tuple[{', '.join(map(str, types))}]"
        self.__attrs_init__(name=name, stub_name=python_name, types=types)


@attrs.frozen
class ARC4Type(WType):
    alias: str | None = None


@typing.final
@attrs.frozen(str=False, kw_only=True, init=False)
class ARC4UIntN(ARC4Type):
    n: int
    is_valid_literal: LiteralValidator = attrs.field(init=False, eq=False)

    @is_valid_literal.default
    def _literal_validator(self) -> LiteralValidator:
        return _uint_literal_validator(max_bits=self.n)

    def __init__(
        self,
        n: int,
        source_location: SourceLocation | None,
        *,
        name: str | None = None,
        alias: str | None = None,
        stub_name: str | None = None,
    ):
        if not (n % 8 == 0):
            raise CodeError("Bit size must be multiple of 8", source_location)
        if not (8 <= n <= 512):
            raise CodeError("Bit size must be between 8 and 512 inclusive", source_location)
        name = name or f"arc4.uint{n}"
        if stub_name is None:
            if n.bit_count() == 1:  # quick way to check for power of 2
                stub_name = f"{constants.ARC4_PREFIX}UInt{n}"
            else:
                base_cls = constants.CLS_ARC4_UINTN if n <= 64 else constants.CLS_ARC4_BIG_UINTN
                stub_name = f"{base_cls}[typing.Literal[{n}]]"
        self.__attrs_init__(n=n, name=name, stub_name=stub_name, alias=alias)


@typing.final
@attrs.frozen(str=False, kw_only=True, init=False)
class ARC4Tuple(ARC4Type):
    types: tuple[ARC4Type, ...] = attrs.field(validator=[attrs.validators.min_len(1)])

    def __init__(self, types: Iterable[WType], source_location: SourceLocation | None):
        types = tuple(types)
        if not types:
            raise CodeError("ARC4 Tuple cannot be empty", source_location)
        immutable = True
        arc4_types = []
        for typ_idx, typ in enumerate(types):
            if not isinstance(typ, ARC4Type):
                raise CodeError(
                    f"Invalid ARC4 Tuple type:"
                    f" type at index {typ_idx} is not an ARC4 encoded type",
                    source_location,
                )
            arc4_types.append(typ)
            # this seems counterintuitive, but is necessary.
            # despite the overall collection remaining stable, since ARC4 types
            # are encoded as a single value, if items within the tuple can be mutated,
            # then the overall value is also mutable
            immutable = immutable and typ.immutable
        name = f"arc4.tuple<{','.join([t.name for t in types])}>"
        python_name = f"{constants.CLS_ARC4_TUPLE}[{', '.join(map(str, types))}]"
        self.__attrs_init__(
            name=name, stub_name=python_name, types=tuple(arc4_types), immutable=immutable
        )


@typing.final
@attrs.frozen(str=False, kw_only=True, init=False)
class ARC4UFixedNxM(ARC4Type):
    n: int
    m: int

    def __init__(self, bits: int, precision: int, source_location: SourceLocation | None):
        n = bits
        m = precision
        if not (n % 8 == 0):
            raise CodeError("Bit size must be multiple of 8", source_location)
        if not (8 <= n <= 512):
            raise CodeError("Bit size must be between 8 and 512 inclusive", source_location)
        if not (1 <= m <= 160):
            raise CodeError("Precision must be between 1 and 160 inclusive", source_location)

        name = f"arc4.ufixed{n}x{m}"
        base_cls = constants.CLS_ARC4_UFIXEDNXM if n <= 64 else constants.CLS_ARC4_BIG_UFIXEDNXM

        def is_valid_literal(value: object) -> bool:
            import decimal

            if not isinstance(value, decimal.Decimal):
                return False
            sign, digits, exponent = value.as_tuple()
            if sign != 0:  # is negative
                return False
            if not isinstance(exponent, int):  # is infinite
                return False
            # note: input is expected to be quantized correctly already
            if -exponent != m:  # wrong precision
                return False
            adjusted_int = int("".join(map(str, digits)))
            return adjusted_int.bit_length() <= n

        self.__attrs_init__(
            n=n,
            m=m,
            name=name,
            stub_name=f"{base_cls}[typing.Literal[{n}], typing.Literal[{m}]]",
            is_valid_literal=is_valid_literal,
        )


@attrs.frozen(str=False, kw_only=True)
class ARC4Array(ARC4Type):
    element_type: ARC4Type
    immutable: bool = attrs.field(default=False, init=False)


@typing.final
@attrs.frozen(str=False, kw_only=True, init=False)
class ARC4DynamicArray(ARC4Array):

    def __init__(
        self,
        element_type: WType,
        source_location: SourceLocation | None,
        *,
        name: str | None = None,
        alias: str | None = None,
        is_valid_literal: LiteralValidator | None = None,
        stub_name: str | None = None,
    ):
        if not isinstance(element_type, ARC4Type):
            raise CodeError("ARC4 arrays must have ARC4 encoded element type", source_location)
        name = name or f"arc4.dynamic_array<{element_type.name}>"
        is_valid_literal = is_valid_literal or typing.cast(LiteralValidator, attrs.NOTHING)
        self.__attrs_init__(
            name=name,
            element_type=element_type,
            stub_name=stub_name or f"{constants.CLS_ARC4_DYNAMIC_ARRAY}[{element_type}]",
            alias=alias,
            is_valid_literal=is_valid_literal,
        )


@typing.final
@attrs.frozen(str=False, kw_only=True, init=False)
class ARC4StaticArray(ARC4Array):
    array_size: int

    def __init__(
        self,
        element_type: WType,
        array_size: int,
        source_location: SourceLocation | None,
        *,
        alias: str | None = None,
        name: str | None = None,
        stub_name: str | None = None,
    ):
        if not isinstance(element_type, ARC4Type):
            raise CodeError("ARC4 arrays must have ARC4 encoded element type", source_location)
        if array_size < 0:
            raise CodeError("ARC4 static array size must be non-negative", source_location)
        name = name or f"arc4.static_array<{element_type.name}, {array_size}>"
        self.__attrs_init__(
            array_size=array_size,
            name=name,
            element_type=element_type,
            stub_name=stub_name
            or (
                f"{constants.CLS_ARC4_STATIC_ARRAY}["
                f"{element_type}, typing.Literal[{array_size}]"
                f"]"
            ),
            alias=alias,
        )


@typing.final
@attrs.frozen(str=False, kw_only=True, init=False)
class ARC4Struct(ARC4Type):
    fields: Mapping[str, ARC4Type] = attrs.field(
        converter=immutabledict, validator=[attrs.validators.min_len(1)]
    )

    @cached_property
    def names(self) -> Sequence[str]:
        return list(self.fields.keys())

    @cached_property
    def types(self) -> Sequence[WType]:
        return list(self.fields.values())

    def __init__(
        self,
        python_name: str,  # TODO: yeet me
        fields: Mapping[str, WType],
        immutable: bool,  # noqa: FBT001
        source_location: SourceLocation | None,
    ):
        if not fields:
            raise CodeError("arc4.Struct needs at least one element", source_location)
        arc4_fields = {}
        for field_name, field_wtype in fields.items():
            if not isinstance(field_wtype, ARC4Type):
                raise CodeError(
                    f"Invalid ARC4 Struct declaration: {field_name} is not an ARC4 encoded type",
                    source_location,
                )
            arc4_fields[field_name] = field_wtype
            # this seems counterintuitive, but is necessary.
            # despite the overall collection remaining stable, since ARC4 types
            # are encoded as a single value, if items within a "frozen" struct can be mutated,
            # then the overall value is also mutable
            immutable = immutable and field_wtype.immutable

        name = (
            "arc4.struct<"
            + ",".join(
                f"{field_name}:{field_type.name}" for field_name, field_type in arc4_fields.items()
            )
            + ">"
        )
        self.__attrs_init__(
            name=name,
            stub_name=python_name,
            immutable=immutable,
            fields=arc4_fields,
        )


arc4_string_wtype: typing.Final = ARC4Type(
    name="arc4.string",
    stub_name=constants.CLS_ARC4_STRING,
    alias="string",
    is_valid_literal=is_valid_utf8_literal,
)
arc4_bool_wtype: typing.Final = ARC4Type(
    name="arc4.bool",
    stub_name=constants.CLS_ARC4_BOOL,
    alias="bool",
    is_valid_literal=is_valid_bool_literal,
)
arc4_byte_type: typing.Final = ARC4UIntN(  # TODO: REMOVE ME
    n=8,
    name="arc4.byte",
    alias="byte",
    source_location=None,
    stub_name=constants.CLS_ARC4_BYTE,
)
arc4_dynamic_bytes: typing.Final = ARC4DynamicArray(  # TODO: REMOVE ME
    name="arc4.dynamic_bytes",
    element_type=arc4_byte_type,
    is_valid_literal=is_valid_bytes_literal,
    stub_name=constants.CLS_ARC4_DYNAMIC_BYTES,
    source_location=None,
)
arc4_address_type: typing.Final = ARC4StaticArray(
    array_size=32,
    name="arc4.address",
    element_type=arc4_byte_type,
    stub_name=constants.CLS_ARC4_ADDRESS,
    alias="address",
    source_location=None,
)


# TODO: move these validation functions somewhere else
def valid_base32(s: str) -> bool:
    """check if s is a valid base32 encoding string and fits into AVM bytes type"""
    try:
        value = base64.b32decode(s)
    except ValueError:
        return False
    return bytes_wtype.is_valid_literal(value)
    # regex from PyTEAL, appears to be RFC-4648
    # ^(?:[A-Z2-7]{8})*(?:([A-Z2-7]{2}([=]{6})?)|([A-Z2-7]{4}([=]{4})?)|([A-Z2-7]{5}([=]{3})?)|([A-Z2-7]{7}([=]{1})?))?  # noqa: E501


def valid_base16(s: str) -> bool:
    try:
        value = base64.b16decode(s)
    except ValueError:
        return False
    return bytes_wtype.is_valid_literal(value)


def valid_base64(s: str) -> bool:
    """check if s is a valid base64 encoding string and fits into AVM bytes type"""
    try:
        value = base64.b64decode(s, validate=True)
    except ValueError:
        return False
    return bytes_wtype.is_valid_literal(value)
    # regex from PyTEAL, appears to be RFC-4648
    # ^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$


def valid_address(address: str) -> bool:
    """check if address is a valid address with checksum"""
    # Pad address so it's a valid b32 string
    padded_address = address + (6 * "=")
    if not (
        len(address) == algo_constants.ENCODED_ADDRESS_LENGTH and valid_base32(padded_address)
    ):
        return False
    address_bytes = base64.b32decode(padded_address)
    if (
        len(address_bytes)
        != algo_constants.PUBLIC_KEY_HASH_LENGTH + algo_constants.ADDRESS_CHECKSUM_LENGTH
    ):
        return False

    public_key_hash = address_bytes[: algo_constants.PUBLIC_KEY_HASH_LENGTH]
    check_sum = address_bytes[algo_constants.PUBLIC_KEY_HASH_LENGTH :]
    verified_check_sum = sha512_256_hash(public_key_hash)[
        -algo_constants.ADDRESS_CHECKSUM_LENGTH :
    ]
    return check_sum == verified_check_sum


def is_transaction_type(wtype: WType) -> typing.TypeGuard[WGroupTransaction]:
    return isinstance(wtype, WGroupTransaction)


def is_inner_transaction_type(wtype: WType) -> typing.TypeGuard[WInnerTransaction]:
    return isinstance(wtype, WInnerTransaction)


def is_inner_transaction_tuple_type(wtype: WType) -> typing.TypeGuard[WTuple]:
    return isinstance(wtype, WTuple) and all(is_inner_transaction_type(t) for t in wtype.types)


def is_inner_transaction_field_type(wtype: WType) -> typing.TypeGuard[WInnerTransactionFields]:
    return isinstance(wtype, WInnerTransactionFields)


def is_reference_type(wtype: WType) -> bool:
    return wtype in (asset_wtype, account_wtype, application_wtype)


def is_arc4_encoded_type(wtype: WType | None) -> typing.TypeGuard[ARC4Type]:
    return isinstance(wtype, ARC4Type)


def is_arc4_argument_type(wtype: WType) -> bool:
    return is_arc4_encoded_type(wtype) or is_reference_type(wtype) or (is_transaction_type(wtype))


def has_arc4_equivalent_type(wtype: WType) -> bool:
    """
    Checks if a non-arc4 encoded type has an arc4 equivalent
    """
    if wtype in (bool_wtype, uint64_wtype, bytes_wtype, biguint_wtype, string_wtype):
        return True

    match wtype:
        case WTuple(types=types):
            return all(
                (has_arc4_equivalent_type(t) or is_arc4_encoded_type(t))
                and not isinstance(t, WTuple)
                for t in types
            )
    return False


def avm_to_arc4_equivalent_type(wtype: WType) -> ARC4Type:
    if wtype is bool_wtype:
        return arc4_bool_wtype
    if wtype is uint64_wtype:
        return ARC4UIntN(64, source_location=None)
    if wtype is biguint_wtype:
        return ARC4UIntN(512, source_location=None)
    if wtype is bytes_wtype:
        return arc4_dynamic_bytes
    if wtype is string_wtype:
        return arc4_string_wtype
    if isinstance(wtype, WTuple):
        return ARC4Tuple(
            types=(
                t if is_arc4_encoded_type(t) else avm_to_arc4_equivalent_type(t)
                for t in wtype.types
            ),
            source_location=None,
        )
    raise InternalError(f"{wtype} does not have an arc4 equivalent type")


def arc4_to_avm_equivalent_wtype(arc4_wtype: WType, source_location: SourceLocation) -> WType:
    match arc4_wtype:
        case ARC4UIntN(n=n) | ARC4UFixedNxM(n=n):
            return uint64_wtype if n <= 64 else biguint_wtype
        case ARC4Tuple(types=types):
            return WTuple(types, source_location=source_location)
        case ARC4DynamicArray(element_type=ARC4UIntN(n=8)):
            return bytes_wtype
    if arc4_wtype is arc4_string_wtype:
        return string_wtype
    elif arc4_wtype is arc4_bool_wtype:
        return bool_wtype

    raise InternalError(f"Invalid arc4_wtype: {arc4_wtype}")


def is_uint64_on_stack(wtype: WType) -> bool:
    if wtype in (bool_wtype, uint64_wtype, asset_wtype, application_wtype):
        return True
    return False
