import typing

from algopy import UInt64
from algopy._transaction import (
    _ApplicationProtocol,
    _AssetConfigProtocol,
    _AssetFreezeProtocol,
    _AssetTransferProtocol,
    _KeyRegistrationProtocol,
    _PaymentProtocol,
    _TransactionBaseProtocol,
)

class _GroupTransaction:
    def __init__(self, group_index: UInt64 | int): ...

class TransactionBase(_TransactionBaseProtocol, typing.Protocol):
    """Shared transaction properties"""

class PaymentTransaction(_PaymentProtocol, TransactionBase, _GroupTransaction):
    """Payment group transaction"""

class KeyRegistrationTransaction(_KeyRegistrationProtocol, TransactionBase, _GroupTransaction):
    """Key registration group transaction"""

class AssetConfigTransaction(_AssetConfigProtocol, TransactionBase, _GroupTransaction):
    """Asset config group transaction"""

class AssetTransferTransaction(_AssetTransferProtocol, TransactionBase, _GroupTransaction):
    """Asset transfer group transaction"""

class AssetFreezeTransaction(_AssetFreezeProtocol, TransactionBase, _GroupTransaction):
    """Asset freeze group transaction"""

class ApplicationCallTransaction(_ApplicationProtocol, TransactionBase, _GroupTransaction):
    """Application call group transaction"""

class Transaction(
    _PaymentProtocol,
    _KeyRegistrationProtocol,
    _AssetConfigProtocol,
    _AssetTransferProtocol,
    _AssetFreezeProtocol,
    _ApplicationProtocol,
    TransactionBase,
    _GroupTransaction,
):
    """Group Transaction of any type"""
