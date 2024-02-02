import base64
import typing
from collections.abc import Callable, Iterable, Mapping, Sequence

import attrs
from immutabledict import immutabledict

from puya.algo_constants import (
    ADDRESS_CHECKSUM_LENGTH,
    ENCODED_ADDRESS_LENGTH,
    MAX_BIGUINT_BITS,
    MAX_BYTES_LENGTH,
    PUBLIC_KEY_HASH_LENGTH,
)
from puya.awst_build import constants
from puya.errors import InternalError
from puya.utils import sha512_256_hash


def _all_literals_invalid(_value: object) -> bool:
    return False


LiteralValidator: typing.TypeAlias = Callable[[object], bool]


@attrs.frozen(str=False, kw_only=True)
class WType:
    name: str
    stub_name: str
    lvalue: bool = True
    immutable: bool = True
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


is_valid_biguint_literal = _uint_literal_validator(max_bits=MAX_BIGUINT_BITS)


def is_valid_bytes_literal(value: object) -> typing.TypeGuard[bytes]:
    return isinstance(value, bytes) and len(value) <= MAX_BYTES_LENGTH


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
    key_wtype: WType = attrs.field()
    content_wtype: WType = attrs.field()

    @classmethod
    def from_key_and_content_type(
        cls, *, key_wtype: WType, content_wtype: WType
    ) -> "WBoxMapProxy":
        return cls(
            key_wtype=key_wtype,
            content_wtype=content_wtype,
            name="box_map_proxy",
            stub_name=constants.CLS_BOX_MAP_PROXY_ALIAS,
        )


box_blob_proxy_wtype: typing.Final = WType(
    name="box_blob_proxy", stub_name=constants.CLS_BOX_BLOB_PROXY_ALIAS
)


@typing.final
@attrs.frozen(str=False, kw_only=True)
class WStructType(WType):
    fields: Mapping[str, WType] = attrs.field(converter=immutabledict)

    @classmethod
    def from_name_and_fields(cls, python_name: str, fields: Mapping[str, WType]) -> typing.Self:
        if not fields:
            raise ValueError("struct needs fields")
        if void_wtype in fields.values():
            raise ValueError("struct should not contain void types")
        name = (
            "struct<"
            + ",".join(
                f"{field_name}:{field_type.name}" for field_name, field_type in fields.items()
            )
            + ">"
        )
        return cls(
            name=name,
            stub_name=python_name,
            immutable=False,
            fields=fields,
        )


@typing.final
@attrs.frozen(str=False, kw_only=True)
class WArray(WType):
    element_type: WType

    @classmethod
    def from_element_type(cls, element_type: WType) -> typing.Self:
        if element_type == void_wtype:
            raise ValueError("array element type cannot be void")
        name = f"array<{element_type.name}>"
        return cls(
            name=name,
            stub_name=f"{constants.CLS_ARRAY_ALIAS}[{element_type}]",
            immutable=False,
            element_type=element_type,
        )


@typing.final
@attrs.frozen(str=False, kw_only=True)
class WTuple(WType):
    types: tuple[WType, ...] = attrs.field(validator=[attrs.validators.min_len(1)])

    @classmethod
    def from_types(cls, types: Iterable[WType]) -> typing.Self:
        types = tuple(types)
        if not types:
            raise ValueError("tuple needs types")
        if void_wtype in types:
            raise ValueError("tuple should not contain void types")
        name = f"tuple<{','.join([t.name for t in types])}>"
        python_name = f"tuple[{', '.join(map(str, types))}]"
        return cls(name=name, stub_name=python_name, types=types)


@attrs.frozen
class ARC4Type(WType):
    alias: str | None = None


@typing.final
@attrs.frozen(str=False, kw_only=True)
class ARC4UIntN(ARC4Type):
    n: int

    is_valid_literal: LiteralValidator = attrs.field(init=False, eq=False)

    @is_valid_literal.default
    def _literal_validator(self) -> LiteralValidator:
        return _uint_literal_validator(max_bits=self.n)

    @classmethod
    def from_scale(cls, n: int) -> typing.Self:
        assert n % 8 == 0, "bit size must be multiple of 8"
        assert 8 <= n <= 512, "bit size must be between 8 and 512 inclusive"
        name = f"arc4.uint{n}"
        if n.bit_count() == 1:  # quick way to check for power of 2
            stub_name = f"{constants.ARC4_PREFIX}UInt{n}"
        else:
            base_cls = constants.CLS_ARC4_UINTN if n <= 64 else constants.CLS_ARC4_BIG_UINTN
            stub_name = f"{base_cls}[typing.Literal[{n}]]"

        return cls(n=n, name=name, stub_name=stub_name)


@typing.final
@attrs.frozen(str=False, kw_only=True)
class ARC4Tuple(ARC4Type):
    types: tuple[ARC4Type, ...] = attrs.field(validator=[attrs.validators.min_len(1)])

    @classmethod
    def from_types(cls, types: Iterable[ARC4Type]) -> typing.Self:
        types = tuple(types)
        if not types:
            raise ValueError("arc4.Tuple needs types")
        immutable = True
        for typ in types:
            # this seems counterintuitive, but is necessary.
            # despite the overall collection remaining stable, since ARC4 types
            # are encoded as a single value, if items within the tuple can be mutated,
            # then the overall value is also mutable
            immutable = immutable and typ.immutable
        name = f"arc4.tuple<{','.join([t.name for t in types])}>"
        python_name = f"{constants.CLS_ARC4_TUPLE}[{', '.join(map(str, types))}]"
        return cls(name=name, stub_name=python_name, types=types, immutable=immutable)


@typing.final
@attrs.frozen(str=False, kw_only=True)
class ARC4UFixedNxM(ARC4Type):
    n: int
    m: int

    @classmethod
    def from_scale_and_precision(cls, n: int, m: int) -> typing.Self:
        assert n % 8 == 0, "bit size must be multiple of 8"
        assert 8 <= n <= 512, "bit size must be between 8 and 512 inclusive"
        assert 1 <= m <= 160, "precision must be between 1 and 160 inclusive"

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

        return cls(
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
@attrs.frozen(str=False, kw_only=True)
class ARC4DynamicArray(ARC4Array):
    @classmethod
    def from_element_type(cls, element_type: ARC4Type) -> typing.Self:
        name = f"arc4.dynamic_array<{element_type.name}>"
        return cls(
            name=name,
            element_type=element_type,
            stub_name=f"{constants.CLS_ARC4_DYNAMIC_ARRAY}[{element_type}]",
        )


@typing.final
@attrs.frozen(str=False, kw_only=True)
class ARC4StaticArray(ARC4Array):
    array_size: int

    @classmethod
    def from_element_type_and_size(
        cls, element_type: ARC4Type, array_size: int, alias: str | None = None
    ) -> typing.Self:
        name = f"arc4.static_array<{element_type.name}, {array_size}>"
        return cls(
            array_size=array_size,
            name=name,
            element_type=element_type,
            stub_name=(
                f"{constants.CLS_ARC4_STATIC_ARRAY}["
                f"{element_type}, typing.Literal[{array_size}]"
                f"]"
            ),
            alias=alias,
        )


@typing.final
@attrs.frozen(str=False, kw_only=True)
class ARC4Struct(ARC4Type):
    fields: Mapping[str, ARC4Type] = attrs.field(
        converter=immutabledict, validator=[attrs.validators.min_len(1)]
    )
    names: Sequence[str] = attrs.field(init=False, eq=False)
    types: Sequence[ARC4Type] = attrs.field(init=False, eq=False)
    immutable: bool = attrs.field(default=False, init=False)

    @names.default
    def _names_factory(self) -> Sequence[str]:
        return list(self.fields.keys())

    @types.default
    def _types_factory(self) -> Sequence[WType]:
        return list(self.fields.values())

    @classmethod
    def from_name_and_fields(
        cls, *, python_name: str, fields: Mapping[str, ARC4Type]
    ) -> typing.Self:
        if not fields:
            raise ValueError("arc4.Struct needs at least one element")
        name = (
            "arc4.struct<"
            + ",".join(
                f"{field_name}:{field_type.name}" for field_name, field_type in fields.items()
            )
            + ">"
        )
        return cls(name=name, stub_name=python_name, fields=fields)


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
arc4_byte_type: typing.Final = ARC4UIntN(
    n=8,
    name="arc4.byte",
    stub_name=constants.CLS_ARC4_BYTE,
    alias="byte",
)
arc4_dynamic_bytes: typing.Final = ARC4DynamicArray(
    name="arc4.dynamic_bytes",
    element_type=arc4_byte_type,
    is_valid_literal=is_valid_bytes_literal,
    stub_name=constants.CLS_ARC4_DYNAMIC_BYTES,
)
arc4_address_type: typing.Final = ARC4StaticArray(
    array_size=32,
    name="arc4.address",
    element_type=arc4_byte_type,
    stub_name=constants.CLS_ARC4_ADDRESS,
    alias="address",
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
    if not (len(address) == ENCODED_ADDRESS_LENGTH and valid_base32(padded_address)):
        return False
    address_bytes = base64.b32decode(padded_address)
    if len(address_bytes) != PUBLIC_KEY_HASH_LENGTH + ADDRESS_CHECKSUM_LENGTH:
        return False

    public_key_hash = address_bytes[:PUBLIC_KEY_HASH_LENGTH]
    check_sum = address_bytes[PUBLIC_KEY_HASH_LENGTH:]
    verified_check_sum = sha512_256_hash(public_key_hash)[-ADDRESS_CHECKSUM_LENGTH:]
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


def is_arc4_encoded_type(wtype: WType) -> typing.TypeGuard[ARC4Type]:
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
        return ARC4UIntN.from_scale(64)
    if wtype is biguint_wtype:
        return ARC4UIntN.from_scale(512)
    if wtype is bytes_wtype:
        return arc4_dynamic_bytes
    if wtype is string_wtype:
        return arc4_string_wtype
    if isinstance(wtype, WTuple):
        return ARC4Tuple.from_types(
            types=[
                t if is_arc4_encoded_type(t) else avm_to_arc4_equivalent_type(t)
                for t in wtype.types
            ]
        )
    raise InternalError(f"{wtype} does not have an arc4 equivalent type")


def arc4_to_avm_equivalent_wtype(arc4_wtype: WType) -> WType:
    match arc4_wtype:
        case ARC4UIntN(n=n) | ARC4UFixedNxM(n=n):
            return uint64_wtype if n <= 64 else biguint_wtype
        case ARC4Tuple(types=types):
            return WTuple.from_types(types)
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
