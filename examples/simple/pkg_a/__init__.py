from typing import TypeAlias

from algopy import UInt64 as MyUInt64
from algopy._gen import Transaction

from . import pkg_1

__all__ = [
    "MyUInt64",
    "pkg_1",
    "Txn",
]

Txn: TypeAlias = Transaction
