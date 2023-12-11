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
from puya.utils import sha512_256_hash


def _all_literals_invalid(_value: object) -> bool:
    return False


@attrs.frozen(str=False, kw_only=True)
class WType:
    name: str
    stub_name: str
    lvalue: bool = True
    immutable: bool = True
    is_valid_literal: Callable[[object], bool] = attrs.field(
        default=_all_literals_invalid,
        eq=False,  # TODO: is this the right thing to do?
    )

    def __str__(self) -> str:
        return self.stub_name


def is_valid_bool_literal(value: object) -> typing.TypeGuard[bool]:
    return isinstance(value, bool)


def _is_unsigned_int(value: object) -> typing.TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def is_valid_uint64_literal(value: object) -> typing.TypeGuard[int]:
    return _is_unsigned_int(value) and value.bit_length() <= 64


def is_valid_biguint_literal(value: object) -> typing.TypeGuard[int]:
    return _is_unsigned_int(value) and value.bit_length() <= MAX_BIGUINT_BITS


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
class WTransaction(WType):
    transaction_type: constants.TransactionType | None
    # TODO only allow int literals below max group size


transaction_base_wtype: typing.Final = WTransaction(
    transaction_type=None,
    name="txn",
    stub_name=constants.CLS_TRANSACTION_BASE_ALIAS,
)
payment_wtype: typing.Final = WTransaction(
    transaction_type=constants.TransactionType.pay,
    name="payment",
    stub_name=constants.CLS_PAYMENT_TRANSACTION_ALIAS,
)

key_registration_wtype: typing.Final = WTransaction(
    transaction_type=constants.TransactionType.keyreg,
    name="key_registration",
    stub_name=constants.CLS_KEY_REGISTRATION_TRANSACTION_ALIAS,
)

asset_config_wtype: typing.Final = WTransaction(
    transaction_type=constants.TransactionType.acfg,
    name="asset_config",
    stub_name=constants.CLS_ASSET_CONFIG_TRANSACTION_ALIAS,
)

asset_transfer_wtype: typing.Final = WTransaction(
    transaction_type=constants.TransactionType.axfer,
    name="asset_transfer",
    stub_name=constants.CLS_ASSET_TRANSFER_TRANSACTION_ALIAS,
)

asset_freeze_wtype: typing.Final = WTransaction(
    transaction_type=constants.TransactionType.afrz,
    name="asset_freeze",
    stub_name=constants.CLS_ASSET_FREEZE_TRANSACTION_ALIAS,
)

application_call_wtype: typing.Final = WTransaction(
    transaction_type=constants.TransactionType.appl,
    name="application_call",
    stub_name=constants.CLS_APPLICATION_CALL_TRANSACTION_ALIAS,
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
    alias: str | None = attrs.field(default=None)


@typing.final
@attrs.frozen(str=False, kw_only=True)
class ARC4UIntN(ARC4Type):
    n: int

    @classmethod
    def from_scale(cls, n: int, *, alias: str | None = None) -> typing.Self:
        name = f"arc4.uint{n}"
        base_cls = constants.CLS_ARC4_UINTN if n <= 64 else constants.CLS_ARC4_BIG_UINTN

        def is_valid_literal(value: object) -> bool:
            return isinstance(value, int) and value >= 0 and value.bit_length() <= n

        return cls(
            n=n,
            name=name,
            stub_name=f"{base_cls}[typing.Literal[{n}]]",
            alias=alias,
            is_valid_literal=is_valid_literal,
        )


@typing.final
@attrs.frozen(str=False, kw_only=True)
class ARC4Tuple(ARC4Type):
    types: tuple[WType, ...] = attrs.field(validator=[attrs.validators.min_len(1)])

    @classmethod
    def from_types(cls, types: Iterable[WType]) -> typing.Self:
        types = tuple(types)
        if not types:
            raise ValueError("arc4.Tuple needs types")
        for typ in types:
            if not is_arc4_encoded_type(typ):
                raise ValueError(f"Invalid type for arc4.Tuple: {typ}")
        name = f"arc4.tuple<{','.join([t.name for t in types])}>"
        python_name = f"{constants.CLS_ARC4_TUPLE}[{', '.join(map(str, types))}]"
        return cls(name=name, stub_name=python_name, types=types)


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
            if value < 0 or not value.is_finite():
                return False
            decimal_str = str(value)
            try:
                whole, part = decimal_str.split(".")
            except ValueError:
                return False
            # note: input is expected to be quantized correctly already
            if len(part) != m:
                return False
            adjusted_int = int(decimal_str.replace(".", ""))
            return adjusted_int.bit_length() <= n

        return cls(
            n=n,
            m=m,
            name=name,
            stub_name=f"{base_cls}[typing.Literal[{n}], typing.Literal[{m}]]",
            is_valid_literal=is_valid_literal,
        )


@typing.final
@attrs.frozen(str=False, kw_only=True)
class ARC4DynamicArray(ARC4Type):
    element_type: WType

    @classmethod
    def from_element_type(cls, element_type: WType) -> typing.Self:
        if not is_arc4_encoded_type(element_type):
            raise ValueError(f"Invalid type for arc4.DynamicArray: {element_type}")
        name = f"arc4.dynamic_array<{element_type.name}>"
        return cls(
            name=name,
            immutable=False,
            element_type=element_type,
            stub_name=f"{constants.CLS_ARC4_DYNAMIC_ARRAY}[{element_type}]",
        )


@typing.final
@attrs.frozen(str=False, kw_only=True)
class ARC4StaticArray(ARC4Type):
    element_type: WType
    array_size: int

    @classmethod
    def from_element_type_and_size(
        cls, element_type: WType, array_size: int, alias: str | None = None
    ) -> typing.Self:
        if not is_arc4_encoded_type(element_type):
            raise ValueError(f"Invalid type for arc4.StaticArray: {element_type}")
        name = f"arc4.static_array<{element_type.name}, {array_size}>"
        return cls(
            array_size=array_size,
            name=name,
            immutable=False,
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
    fields: Mapping[str, WType] = attrs.field(
        converter=immutabledict, validator=[attrs.validators.min_len(1)]
    )
    names: Sequence[str] = attrs.field(init=False, eq=False)
    types: Sequence[WType] = attrs.field(init=False, eq=False)

    @names.default
    def _names_factory(self) -> Sequence[str]:
        return list(self.fields.keys())

    @types.default
    def _types_factory(self) -> Sequence[WType]:
        return list(self.fields.values())

    @classmethod
    def from_name_and_fields(cls, *, python_name: str, fields: Mapping[str, WType]) -> typing.Self:
        if not fields:
            raise ValueError("arc4.Struct needs at least one element")
        for t in fields.values():
            if not is_arc4_encoded_type(t):
                raise ValueError(f"arc4.Struct should not contain non arc4 types: {t}")
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
    name="arc4.bool", stub_name=constants.CLS_ARC4_BOOL, alias="bool"
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


def is_transaction_type(wtype: WType) -> typing.TypeGuard[WTransaction]:
    return isinstance(wtype, WTransaction)


def is_reference_type(wtype: WType) -> bool:
    return wtype in (asset_wtype, account_wtype, application_wtype)


def is_arc4_encoded_type(wtype: WType) -> typing.TypeGuard[ARC4Type]:
    return isinstance(wtype, ARC4Type)


def is_arc4_argument_type(wtype: WType) -> bool:
    return (
        is_arc4_encoded_type(wtype)
        or is_reference_type(wtype)
        or (is_transaction_type(wtype) and wtype.transaction_type is not None)
    )
