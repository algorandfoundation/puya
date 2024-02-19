import typing

from puyapy import UInt64
from puyapy._transaction import (
    ApplicationProtocol,
    AssetConfigProtocol,
    AssetFreezeProtocol,
    AssetTransferProtocol,
    KeyRegistrationProtocol,
    PaymentProtocol,
    TransactionBaseProtocol,
)

class _GroupTransaction:
    def __init__(self, group_index: UInt64 | int): ...

class TransactionBase(TransactionBaseProtocol, typing.Protocol):
    """Shared transaction properties"""

class PaymentTransaction(PaymentProtocol, TransactionBase, _GroupTransaction):
    """Payment group transaction"""

class KeyRegistrationTransaction(KeyRegistrationProtocol, TransactionBase, _GroupTransaction):
    """Key registration group transaction"""

class AssetConfigTransaction(AssetConfigProtocol, TransactionBase, _GroupTransaction):
    """Asset config group transaction"""

class AssetTransferTransaction(AssetTransferProtocol, TransactionBase, _GroupTransaction):
    """Asset transfer group transaction"""

class AssetFreezeTransaction(AssetFreezeProtocol, TransactionBase, _GroupTransaction):
    """Asset freeze group transaction"""

class ApplicationCallTransaction(ApplicationProtocol, TransactionBase, _GroupTransaction):
    """Application call group transaction"""

class Transaction(
    PaymentProtocol,
    KeyRegistrationProtocol,
    AssetConfigProtocol,
    AssetTransferProtocol,
    AssetFreezeProtocol,
    ApplicationProtocol,
    TransactionBase,
    _GroupTransaction,
):
    """Group Transaction of any type"""
