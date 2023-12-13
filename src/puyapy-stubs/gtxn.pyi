import typing

from puyapy import UInt64
from puyapy._transaction import (
    ApplicationCallTransactionFields,
    AssetConfigTransactionFields,
    AssetFreezeTransactionFields,
    AssetTransferTransactionFields,
    KeyRegistrationTransactionFields,
    PaymentTransactionFields,
    SharedTransactionFields,
)

class _GroupTransaction:
    def __init__(self, group_index: UInt64 | int): ...

class TransactionBase(SharedTransactionFields, typing.Protocol):
    """Shared transaction properties"""

class PaymentTransaction(PaymentTransactionFields, TransactionBase, _GroupTransaction):
    """Payment group transaction"""

class KeyRegistrationTransaction(
    KeyRegistrationTransactionFields, TransactionBase, _GroupTransaction
):
    """Key registration group transaction"""

class AssetConfigTransaction(AssetConfigTransactionFields, TransactionBase, _GroupTransaction):
    """Asset config group transaction"""

class AssetTransferTransaction(AssetTransferTransactionFields, TransactionBase, _GroupTransaction):
    """Asset transfer group transaction"""

class AssetFreezeTransaction(AssetFreezeTransactionFields, TransactionBase, _GroupTransaction):
    """Asset freeze group transaction"""

class ApplicationCallTransaction(
    ApplicationCallTransactionFields, TransactionBase, _GroupTransaction
):
    """Application call group transaction"""

class AnyTransaction(
    PaymentTransactionFields,
    KeyRegistrationTransactionFields,
    AssetConfigTransactionFields,
    AssetTransferTransactionFields,
    AssetFreezeTransactionFields,
    ApplicationCallTransactionFields,
    TransactionBase,
    _GroupTransaction,
):
    """Group Transaction of any type"""
