from __future__ import annotations

import enum
import functools
import secrets
from typing import TYPE_CHECKING

import algosdk
import algosdk.transaction

from algopy_testing import arc4
from algopy_testing.constants import MAX_BYTES_SIZE, MAX_UINT8, MAX_UINT64, MAX_UINT512

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
