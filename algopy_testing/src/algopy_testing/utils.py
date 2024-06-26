from __future__ import annotations

import enum
import functools
import secrets
import typing
from types import UnionType
from typing import TYPE_CHECKING, get_args

import algosdk
import algosdk.transaction

from algopy_testing import arc4
from algopy_testing.constants import MAX_BYTES_SIZE, MAX_UINT8, MAX_UINT16, MAX_UINT64, MAX_UINT512

if TYPE_CHECKING:
    import algopy


def as_int(value: object, *, max: int | None) -> int:  # noqa: A002
    """
    Returns the underlying int value for any numeric type up to UInt512

    Raises:
        TypeError: If `value` is not a numeric type
        ValueError: If not 0 <= `value` <= max
    """

    from algopy_testing.primitives.biguint import BigUInt
    from algopy_testing.primitives.uint64 import UInt64

    match value:
        case int(int_value):
            pass
        case UInt64(value=int_value):
            pass
        case BigUInt(value=int_value):
            pass
        case arc4.UIntN():
            int_value = value.native.value
        case arc4.BigUIntN():
            int_value = value.native.value
        # TODO: add arc4 numerics
        case _:
            raise TypeError(f"value must be a numeric type, not {type(value).__name__!r}")
    if int_value < 0:
        raise ValueError(f"expected positive value, got {int_value}")
    if max is not None and int_value > max:
        raise ValueError(f"expected value <= {max}, got: {int_value}")
    return int_value


def as_int8(value: object) -> int:
    return as_int(value, max=MAX_UINT8)


def as_int16(value: object) -> int:
    return as_int(value, max=MAX_UINT16)


def as_int64(value: object) -> int:
    return as_int(value, max=MAX_UINT64)


def as_int512(value: object) -> int:
    return as_int(value, max=MAX_UINT512)


def as_bytes(value: object, *, max_size: int = MAX_BYTES_SIZE) -> bytes:
    """
    Returns the underlying bytes value for bytes or Bytes type up to 4096

    Raises:
        TypeError: If `value` is not a bytes type
        ValueError: If not 0 <= `len(value)` <= max_size
    """
    from algopy_testing.primitives.bytes import Bytes

    match value:
        case bytes(bytes_value):
            pass
        case Bytes(value=bytes_value):
            pass
        case _:
            raise TypeError(f"value must be a bytes or Bytes type, not {type(value).__name__!r}")
    if len(bytes_value) > max_size:
        raise ValueError(f"expected value length <= {max_size}, got: {len(bytes_value)}")
    return bytes_value


def as_string(value: object) -> str:
    from algopy_testing.primitives.string import String

    match value:
        case str(string_value) | String(value=string_value):
            return string_value
        case arc4.String():
            return value.native.value
        case _:
            raise TypeError(f"value must be a string or String type, not {type(value).__name__!r}")


def int_to_bytes(x: int, pad_to: int | None = None) -> bytes:
    result = x.to_bytes((x.bit_length() + 7) // 8, "big")
    result = (
        b"\x00" * (pad_to - len(result)) if pad_to is not None and len(result) < pad_to else b""
    ) + result

    return result


def dummy_transaction_id() -> bytes:
    private_key, address = algosdk.account.generate_account()

    suggested_params = algosdk.transaction.SuggestedParams(fee=1000, first=0, last=1, gh="")
    txn = algosdk.transaction.PaymentTxn(
        sender=address,
        receiver=address,
        amt=1000,
        sp=suggested_params,
        note=secrets.token_bytes(8),
    )

    signed_txn = txn.sign(private_key)
    txn_id = str(signed_txn.transaction.get_txid()).encode("utf-8")
    return txn_id


class _TransactionStrType(enum.StrEnum):
    PAYMENT = algosdk.constants.PAYMENT_TXN
    KEYREG = algosdk.constants.KEYREG_TXN
    ASSETCONFIG = algosdk.constants.ASSETCONFIG_TXN
    ASSETTRANSFER = algosdk.constants.ASSETTRANSFER_TXN
    ASSETFREEZE = algosdk.constants.ASSETFREEZE_TXN
    APPCALL = algosdk.constants.APPCALL_TXN


@functools.cache
def txn_type_to_bytes(txn_type: int) -> algopy.Bytes:
    import algopy

    match txn_type:
        case algopy.TransactionType.Payment:
            result = _TransactionStrType.PAYMENT
        case algopy.TransactionType.KeyRegistration:
            result = _TransactionStrType.KEYREG
        case algopy.TransactionType.AssetConfig:
            result = _TransactionStrType.ASSETCONFIG
        case algopy.TransactionType.AssetTransfer:
            result = _TransactionStrType.ASSETTRANSFER
        case algopy.TransactionType.AssetFreeze:
            result = _TransactionStrType.ASSETFREEZE
        case algopy.TransactionType.ApplicationCall:
            result = _TransactionStrType.APPCALL
        case _:
            raise ValueError(f"invalid transaction type: {txn_type}")

    return algopy.Bytes(bytes(result, encoding="utf-8"))


def is_instance(obj: object, class_or_tuple: type | UnionType) -> bool:
    if isinstance(class_or_tuple, UnionType):
        return any(is_instance(obj, arg) for arg in get_args(class_or_tuple))

    if isinstance(obj, typing._ProtocolMeta):  # type: ignore[type-check, unused-ignore]
        return (
            f"{obj.__module__}.{obj.__name__}"
            == f"{class_or_tuple.__module__}.{class_or_tuple.__name__}"  # type: ignore[union-attr, unused-ignore]
        )

    # Manual comparison by module and name
    if (
        hasattr(obj, "__module__")
        and hasattr(obj, "__name__")
        and (
            obj.__module__,
            obj.__name__,  # type: ignore[attr-defined, unused-ignore]
        )
        == (
            class_or_tuple.__module__,
            class_or_tuple.__name__,
        )
    ):
        return True

    return isinstance(obj, class_or_tuple)


def abi_type_name_for_arg(  # noqa: PLR0912, C901, PLR0911
    *, arg: object, is_return_type: bool = False
) -> str:
    """
    Returns the ABI type name for the given argument. Especially convenient for use with
    algosdk to generate method signatures
    """
    import algopy

    if is_instance(arg, algopy.arc4.String | algopy.String | str):
        return "string"
    if is_instance(arg, algopy.arc4.Bool | bool):
        return "bool"
    if is_instance(arg, algopy.BigUInt):
        return "uint512"
    if is_instance(arg, algopy.UInt64):
        return "uint64"
    if isinstance(arg, int):
        return "uint64" if arg <= MAX_UINT64 else "uint512"
    if is_instance(arg, algopy.Bytes | bytes):
        return "byte[]"
    if is_instance(arg, algopy.arc4.Address):
        return "address"
    if is_instance(arg, algopy.Asset):
        return "uint64" if is_return_type else "asset"
    if is_instance(arg, algopy.Account):
        return "uint64" if is_return_type else "account"
    if is_instance(arg, algopy.Application):
        return "uint64" if is_return_type else "application"
    if is_instance(arg, algopy.arc4.UIntN):
        return "uint" + str(arg._bit_size)  # type: ignore[attr-defined]
    if is_instance(arg, algopy.arc4.BigUIntN):
        return "uint" + str(arg._bit_size)  # type: ignore[attr-defined]
    if is_instance(arg, algopy.arc4.UFixedNxM):
        return f"ufixed{arg._n}x{arg._m}"  # type: ignore[attr-defined]
    if is_instance(arg, algopy.arc4.BigUFixedNxM):
        return f"ufixed{arg._n}x{arg._m}"  # type: ignore[attr-defined]
    if is_instance(arg, algopy.arc4.StaticArray):
        return f"{abi_type_name_for_arg(arg=arg[0],    # type: ignore[index]
                                        is_return_type=is_return_type)}[{arg.length.value}]"  # type: ignore[attr-defined]
    if is_instance(arg, algopy.arc4.DynamicArray):
        return f"{abi_type_name_for_arg(arg=arg[0], # type: ignore[index]
                                        is_return_type=is_return_type)}[]"
    if isinstance(arg, tuple):
        return f"({','.join(abi_type_name_for_arg(arg=a,
                                                  is_return_type=is_return_type) for a in arg)})"
    raise ValueError(f"Unsupported type {type(arg)}")


def abi_return_type_annotation_for_arg(arg: object) -> str:
    """
    Returns the ABI type name for the given argument. Especially convenient for use with
    algosdk to generate method signatures
    """

    try:
        return abi_type_name_for_arg(arg=arg, is_return_type=True)
    except ValueError:
        if arg is None:
            return "void"
        raise
