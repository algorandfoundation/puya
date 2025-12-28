import random
import re

import algokit_utils as au
import pytest

from tests import TEST_CASES_DIR
from tests.utils.deployer import Deployer

_VALID_DYNAMIC_STRUCT_BYTES = b"\x00" * 9 + b"\x00\x0b\x00\x00"
_INVALID_DYNAMIC_STRUCT_BYTES = b"\x00" * 9 + b"\x00\x0b\x00\x01"
_STATIC_STRUCT = "test_cases.arc4_validation.contract.ARC4StaticStruct"
_DYNAMIC_STRUCT = "test_cases.arc4_validation.contract.ARC4DynamicStruct"
_WITH_A_BOOL = "test_cases.arc4_validation.contract.WithABool"
_FROZEN_DYNAMIC_STRUCT = "test_cases.arc4_validation.contract.ARC4FrozenDynamicStruct"
_NATIVE_STATIC_STRUCT = "test_cases.arc4_validation.contract.NativeStaticStruct"
_NATIVE_DYNAMIC_STRUCT = "test_cases.arc4_validation.contract.NativeDynamicStruct"


@pytest.fixture(scope="module")
def arc4_validation_client(
    localnet_clients: au.AlgoSdkClients, account: au.AddressWithSigners
) -> au.AppClient:
    # create a module scoped client
    localnet = au.AlgorandClient(localnet_clients)
    localnet.account.set_signer_from_account(account)
    deployer = Deployer(localnet=localnet, account=account)
    result = deployer.create(TEST_CASES_DIR / "arc4_validation")
    return result.client


@pytest.mark.parametrize(
    ("type_name", "size_or_bytes_value"),
    [
        ("uint64", 8),
        ("ufixed64", 8),
        ("uint8", 1),
        ("bool", 1),
        ("byte", 1),
        ("string", 2),
        ("string", (4, b"\x00" * 4)),
        ("bytes", 2),
        ("bytes", (4, b"\x00" * 4)),
        ("address", 32),
        ("account", 32),
        ("uint512", 64),
        ("uint8_arr", 2),
        ("uint8_arr", b"\x00\x01\x00"),
        ("uint8_arr3", 3),
        ("bool_arr", b"\x00\x00"),
        ("bool_arr", b"\x00\x01\x00"),
        ("bool_arr", b"\x00\x08\x00"),
        ("bool_arr", b"\x00\x0a\x00\x00"),
        ("static_struct", 9),
        ("dynamic_struct", _VALID_DYNAMIC_STRUCT_BYTES),
        ("dynamic_struct_with_a_bool", b"\x01\x00\x04\x80\x00\x01\xff"),
        ("static_tuple", 9),
        ("dynamic_tuple", _VALID_DYNAMIC_STRUCT_BYTES),
        ("static_struct_arr", b"\x00\x03" + b"\x00" * 27),
        ("static_struct_arr3", 27),
        ("dynamic_struct_arr", 2),
        (
            "dynamic_struct_arr",
            (
                2,  # len
                4,  # ptr 1
                4 + len(_VALID_DYNAMIC_STRUCT_BYTES),  # ptr 2
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
            ),
        ),
        (
            "dynamic_struct_arr3",
            (
                6,
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES),
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES) * 2,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
            ),
        ),
    ],
)
def test_arc4_validation_valid(
    arc4_validation_client: au.AppClient,
    type_name: str,
    size_or_bytes_value: bytes | int | tuple[int | bytes, ...],
) -> None:
    arc4_validation_client.send.call(
        _get_call_params(f"validate_{type_name}", size_or_bytes_value)
    )


def _invalid_size(type_name: str) -> str:
    return f"invalid number of bytes for {type_name}"


def _invalid_arr_size(element_type_name: str, size: int | None = None) -> str:
    if size is None:
        return _invalid_size(f"arc4.dynamic_array<{element_type_name}>")
    else:
        return _invalid_size(f"arc4.static_array<{element_type_name}, {size}>")


@pytest.mark.parametrize(
    ("type_name", "size_or_bytes_value", "expected_error"),
    [
        ("uint64", 7, _invalid_size("arc4.uint64")),
        ("ufixed64", 7, _invalid_size("arc4.ufixed64x2")),
        ("uint8", 2, _invalid_size("arc4.uint8")),
        ("bool", 2, _invalid_size("arc4.bool")),
        ("byte", 2, _invalid_size("arc4.uint8")),
        ("string", 5, _invalid_arr_size("arc4.uint8")),
        ("bytes", 5, _invalid_arr_size("arc4.uint8")),
        ("address", 0, _invalid_arr_size("arc4.uint8", 32)),
        ("address", 33, _invalid_arr_size("arc4.uint8", 32)),
        ("account", 0, _invalid_arr_size("arc4.uint8", 32)),
        ("account", 33, _invalid_arr_size("arc4.uint8", 32)),
        ("uint512", 63, _invalid_size("arc4.uint512")),
        ("uint8_arr", 1, "invalid array length header"),
        ("uint8_arr", 3, _invalid_arr_size("arc4.uint8")),
        ("uint8_arr3", 1, _invalid_arr_size("arc4.uint8", 3)),
        ("uint8_arr3", 4, _invalid_arr_size("arc4.uint8", 3)),
        ("bool_arr", b"\x00\x01", _invalid_arr_size("arc4.bool")),
        ("bool_arr", b"\x00\x09\x00", _invalid_arr_size("arc4.bool")),
        ("static_struct", 8, _invalid_size(_STATIC_STRUCT)),
        ("dynamic_struct", 0, "invalid tuple encoding"),
        ("dynamic_struct", 11, "invalid tail pointer"),
        ("dynamic_struct", _INVALID_DYNAMIC_STRUCT_BYTES, _invalid_size(_DYNAMIC_STRUCT)),
        ("dynamic_struct_with_a_bool", b"\x01", "invalid tuple encoding"),
        (
            "dynamic_struct_with_a_bool",
            b"\x01\x00\x04\x80\x00\x01\xff\x00",
            _invalid_size(_WITH_A_BOOL),
        ),
        ("dynamic_struct_with_a_bool", b"\x01\x00\x03\x80\x00\x01\xff", "invalid tail pointer"),
        ("static_tuple", 8, _invalid_size("arc4.tuple<arc4.uint64,arc4.uint8>")),
        ("dynamic_tuple", 0, "invalid tuple encoding"),
        ("dynamic_tuple", 11, "invalid tail pointer"),
        (
            "dynamic_tuple",
            _INVALID_DYNAMIC_STRUCT_BYTES,
            _invalid_size("arc4.tuple<arc4.uint64,arc4.uint8,arc4.dynamic_array<arc4.uint8>>"),
        ),
        ("static_struct_arr", 0, "invalid array length header"),
        ("static_struct_arr", 1, "invalid array length header"),
        ("static_struct_arr", 29, _invalid_arr_size(_STATIC_STRUCT)),
        ("static_struct_arr3", 26, _invalid_arr_size(_STATIC_STRUCT, 3)),
        ("dynamic_struct_arr", 0, "invalid array length header"),
        ("dynamic_struct_arr", 1, "invalid array length header"),
        ("dynamic_struct_arr", 29, _invalid_arr_size(_DYNAMIC_STRUCT)),
        ("dynamic_struct_arr3", 27, "invalid tail pointer"),
        (
            "dynamic_struct_arr3",
            (
                6,
                6,
                6,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
            ),
            "invalid tail pointer",
        ),
        (
            "dynamic_struct_arr3",
            0,
            "invalid array encoding",
        ),
        (
            "dynamic_struct_arr3",
            (
                6,
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES),
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES) * 2,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _INVALID_DYNAMIC_STRUCT_BYTES,
            ),
            _invalid_arr_size(_DYNAMIC_STRUCT, 3),
        ),
    ],
)
def test_arc4_validation_invalid(
    arc4_validation_client: au.AppClient,
    type_name: str,
    size_or_bytes_value: bytes | int | tuple[int | bytes, ...],
    expected_error: str,
) -> None:
    with pytest.raises(au.LogicError, match=re.escape(expected_error) + r"[^\n]*<-- Error"):
        arc4_validation_client.send.call(
            _get_call_params(f"validate_{type_name}", size_or_bytes_value)
        )


@pytest.mark.parametrize(
    ("type_name", "size_or_bytes_value"),
    [
        ("static_struct", 9),
        ("dynamic_struct", _VALID_DYNAMIC_STRUCT_BYTES),
        ("static_struct_arr", b"\x00\x03" + b"\x00" * 27),
        ("static_struct_arr3", 27),
        ("dynamic_struct_arr", 2),
        (
            "dynamic_struct_arr",
            (
                2,  # len
                4,  # ptr 1
                4 + len(_VALID_DYNAMIC_STRUCT_BYTES),  # ptr 2
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
            ),
        ),
        ("dynamic_struct_imm_arr", 2),
        (
            "dynamic_struct_imm_arr",
            (
                2,  # len
                4,  # ptr 1
                4 + len(_VALID_DYNAMIC_STRUCT_BYTES),  # ptr 2
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
            ),
        ),
        (
            "dynamic_struct_arr3",
            (
                6,
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES),
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES) * 2,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
            ),
        ),
        (
            "dynamic_struct_imm_arr3",
            (
                6,
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES),
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES) * 2,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
            ),
        ),
    ],
)
def test_native_validation_valid(
    arc4_validation_client: au.AppClient,
    type_name: str,
    size_or_bytes_value: bytes | int | tuple[int | bytes, ...],
) -> None:
    arc4_validation_client.send.call(
        _get_call_params(f"validate_native_{type_name}", size_or_bytes_value)
    )


@pytest.mark.parametrize(
    ("type_name", "size_or_bytes_value", "expected_error"),
    [
        ("static_struct", 8, _invalid_size(_NATIVE_STATIC_STRUCT)),
        ("dynamic_struct", 0, "invalid tuple encoding"),
        ("dynamic_struct", 11, "invalid tail pointer"),
        ("dynamic_struct", _INVALID_DYNAMIC_STRUCT_BYTES, _invalid_size(_NATIVE_DYNAMIC_STRUCT)),
        ("static_struct_arr", 0, "invalid array length header"),
        ("static_struct_arr", 1, "invalid array length header"),
        ("static_struct_arr", 29, _invalid_arr_size(_NATIVE_STATIC_STRUCT)),
        ("static_struct_arr3", 26, _invalid_arr_size(_NATIVE_STATIC_STRUCT, 3)),
        ("dynamic_struct_arr", 0, "invalid array length header"),
        ("dynamic_struct_arr", 1, "invalid array length header"),
        ("dynamic_struct_arr", 29, _invalid_arr_size(_NATIVE_DYNAMIC_STRUCT)),
        ("dynamic_struct_arr3", 27, "invalid tail pointer"),
        (
            "dynamic_struct_arr3",
            (
                6,
                6,
                6,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
            ),
            "invalid tail pointer",
        ),
        (
            "dynamic_struct_arr3",
            (
                6,
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES),
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES) * 2,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _INVALID_DYNAMIC_STRUCT_BYTES,
            ),
            _invalid_arr_size(_NATIVE_DYNAMIC_STRUCT, 3),
        ),
        ("dynamic_struct_imm_arr", 0, "invalid array length header"),
        ("dynamic_struct_imm_arr", 1, "invalid array length header"),
        (
            "dynamic_struct_imm_arr",
            29,
            _invalid_arr_size(_FROZEN_DYNAMIC_STRUCT),
        ),
        ("dynamic_struct_imm_arr3", 27, "invalid tail pointer"),
        (
            "dynamic_struct_imm_arr3",
            (
                6,
                6,
                6,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
            ),
            "invalid tail pointer",
        ),
        (
            "dynamic_struct_imm_arr3",
            (
                6,
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES),
                6 + len(_VALID_DYNAMIC_STRUCT_BYTES) * 2,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _VALID_DYNAMIC_STRUCT_BYTES,
                _INVALID_DYNAMIC_STRUCT_BYTES,
            ),
            _invalid_arr_size(_FROZEN_DYNAMIC_STRUCT, 3),
        ),
    ],
)
def test_native_validation_invalid(
    arc4_validation_client: au.AppClient,
    type_name: str,
    size_or_bytes_value: bytes | int | tuple[int | bytes, ...],
    expected_error: str,
) -> None:
    with pytest.raises(au.LogicError, match=re.escape(expected_error) + r"[^\n]*<-- Error"):
        arc4_validation_client.send.call(
            _get_call_params(f"validate_native_{type_name}", size_or_bytes_value)
        )


def _get_call_params(
    method: str, size_or_bytes_value: bytes | int | tuple[int | bytes, ...]
) -> au.AppClientMethodCallParams:
    bytes_value = _get_bytes_value(size_or_bytes_value)
    return au.AppClientMethodCallParams(
        method=method, args=[bytes_value], note=random.randbytes(8)
    )


def _get_bytes_value(size_or_bytes_value: bytes | int | tuple[int | bytes, ...]) -> bytes:
    if isinstance(size_or_bytes_value, bytes):
        return size_or_bytes_value
    elif isinstance(size_or_bytes_value, int):
        return b"\x00" * size_or_bytes_value
    else:
        return b"".join(
            b if isinstance(b, bytes) else b.to_bytes(length=2) for b in size_or_bytes_value
        )
