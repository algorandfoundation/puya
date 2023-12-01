import base64
import typing
from collections.abc import Callable, Iterable, Mapping, Sequence

import attrs

from wyvern.algo_constants import (
    ENCODED_ADDRESS_LENGTH,
    MAX_BIGUINT_BITS,
    MAX_BYTES_LENGTH,
)
from wyvern.awst_build import constants


def _all_literals_invalid(_value: object) -> bool:
    return False


@attrs.frozen(str=False, kw_only=True)
class WType:
    name: str
    python_type: str
    lvalue: bool = True
    immutable: bool = True
    is_valid_literal: Callable[[object], bool] = attrs.field(
        default=_all_literals_invalid,
        eq=False,  # TODO: is this the right thing to do?
    )

    def __str__(self) -> str:
        return self.python_type


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


def is_valid_address_literal(value: object) -> typing.TypeGuard[str]:
    return isinstance(value, str) and valid_address(value)


void_wtype: typing.Final = WType(
    name="void",
    python_type="None",
    lvalue=False,
)

bool_wtype: typing.Final = WType(
    name="bool",
    python_type="bool",
    is_valid_literal=is_valid_bool_literal,
)

uint64_wtype: typing.Final = WType(
    name="uint64",
    python_type=constants.CLS_UINT64_ALIAS,
    is_valid_literal=is_valid_uint64_literal,
)

biguint_wtype: typing.Final = WType(
    name="biguint",
    python_type=constants.CLS_BIGUINT_ALIAS,
    is_valid_literal=is_valid_biguint_literal,
)

bytes_wtype: typing.Final = WType(
    name="bytes",
    python_type=constants.CLS_BYTES_ALIAS,
    is_valid_literal=is_valid_bytes_literal,
)
address_wtype: typing.Final = WType(
    name="address",
    python_type=constants.CLS_ADDRESS_ALIAS,
    is_valid_literal=is_valid_address_literal,
)

asset_wtype: typing.Final = WType(name="asset", python_type=constants.CLS_ASSET)


abi_string_wtype: typing.Final = WType(name="abi_string", python_type=constants.CLS_ABI_STRING)


@typing.final
@attrs.frozen(str=False, kw_only=True)
class AbiUIntN(WType):
    n: int

    @classmethod
    def from_scale(cls, n: int) -> typing.Self:
        name = f"uint{n}"
        return cls(
            n=n,
            name=name,
            immutable=False,
            python_type=constants.CLS_ABI_UINTN,
        )


@typing.final
@attrs.frozen(str=False, kw_only=True)
class AbiDynamicArray(WType):
    element_type: WType

    @classmethod
    def from_element_type(cls, element_type: WType) -> typing.Self:
        if element_type == void_wtype:
            raise ValueError("array element type cannot be void")
        name = f"abi_dynamic_array<{element_type.name}>"
        return cls(
            name=name,
            immutable=False,
            element_type=element_type,
            python_type=constants.CLS_ABI_DYNAMIC_ARRAY,
        )


@typing.final
@attrs.frozen(str=False, kw_only=True)
class AbiStaticArray(WType):
    element_type: WType
    array_size: int

    @classmethod
    def from_element_type_and_size(cls, element_type: WType, array_size: int) -> typing.Self:
        if element_type == void_wtype:
            raise ValueError("array element type cannot be void")
        name = f"abi_static_array<{element_type.name}, {array_size}>"
        return cls(
            array_size=array_size,
            name=name,
            immutable=False,
            element_type=element_type,
            python_type=constants.CLS_ABI_STATIC_ARRAY,
        )


@typing.final
@attrs.frozen(str=False, kw_only=True)
class WStructType(WType):
    fields: Mapping[str, WType] = attrs.field(eq=False)
    _data: Sequence[tuple[str, WType]] = attrs.field(init=False)

    @_data.default
    def _data_factory(self) -> Sequence[tuple[str, WType]]:
        return tuple(self.fields.items())

    @classmethod
    def from_name_and_fields(cls, python_name: str, fields: dict[str, WType]) -> typing.Self:
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
            python_type=python_name,
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
            python_type=f"{constants.CLS_ARRAY_ALIAS}[{element_type}]",
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
        return cls(
            name=name,
            python_type=f"tuple[{', '.join(map(str, types))}]",
            types=types,
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
    # TODO: additional validation??
    return len(address) == ENCODED_ADDRESS_LENGTH and valid_base32(address + (6 * "="))
