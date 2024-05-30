from __future__ import annotations

import random
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Generic, TypeVar

import algosdk

from algopy_testing.constants import MAX_BYTES_SIZE, MAX_UINT64
from algopy_testing.itxn import BaseInnerTransaction
from algopy_testing.models.account import Account
from algopy_testing.models.application import Application
from algopy_testing.models.asset import Asset
from algopy_testing.models.global_state import GlobalFields, GlobalFieldsKwargs
from algopy_testing.models.itxn import ITxnFields
from algopy_testing.models.txn import TxnFields, TxnFieldsDict
from algopy_testing.primitives.bytes import Bytes
from algopy_testing.primitives.uint64 import UInt64

if TYPE_CHECKING:
    from collections.abc import Generator


T = TypeVar("T")
U = TypeVar("U")


class TestContext(Generic[T]):
    def __init__(self) -> None:
        self.accounts: dict[str, Account] = {}
        self.applications: dict[int, Application] = {}
        self.assets: dict[int, Asset] = {}
        self.inner_transactions: list[BaseInnerTransaction] = []
        self.global_fields: GlobalFields = GlobalFields()
        self.txn_fields: TxnFields = TxnFields()
        self.itxn_fields: ITxnFields = ITxnFields()
        self.logs: list[str] = []
        self._asset_id_count: UInt64 = UInt64(1)
        self._app_id_count: UInt64 = UInt64(1)

    def _next_asset_id(self) -> UInt64:
        self._asset_id_count += 1
        return self._asset_id_count

    def _next_app_id(self) -> UInt64:
        self._app_id_count += 1
        return self._app_id_count

    def set_global_fields(self, kwargs: GlobalFieldsKwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self.global_fields, key):
                setattr(self.global_fields, key, value)
            else:
                raise AttributeError(f"GlobalFields has no attribute '{key}'")

    def set_txn_fields(self, kwargs: TxnFieldsDict) -> None:
        for key, value in kwargs.items():
            if hasattr(self.global_fields, key):
                setattr(self.global_fields, key, value)
            else:
                raise AttributeError(f"GlobalFields has no attribute '{key}'")

    def set_itxn_fields(self, itxn_fields: ITxnFields) -> None:
        self.itxn_fields = itxn_fields

    def add_account(self, account: object) -> None:
        if not isinstance(account, Account):
            raise TypeError("account must be an instance of Account")
        if not account.bytes:
            raise ValueError("Account address is required")
        self.accounts[str(account)] = account

    def get_account(self, address: str) -> Account:
        return self.accounts[address]

    def update_account(self, address: str, account: Account) -> None:
        self.accounts[address] = account

    def add_asset(
        self,
        asset: object,
    ) -> None:
        if not isinstance(asset, Asset):
            raise TypeError("asset must be an instance of Asset")

        if not asset.id:
            raise ValueError("Asset ID is required")

        self.assets[int(asset.id)] = asset

    def get_asset(self, asset_id: int) -> Asset:
        return self.assets[asset_id]

    def update_asset(self, asset_id: int, asset: Asset) -> None:
        self.assets[asset_id] = asset

    def add_application(
        self,
        app: object,
    ) -> None:
        if not isinstance(app, Application):
            raise TypeError("app must be an instance of Application")
        if not app.id:
            raise ValueError("Application ID is required")

        self.applications[int(app.id)] = app

    def get_application(self, app_id: int) -> Application:
        return self.applications[app_id]

    def add_inner_transaction(self, itxn: BaseInnerTransaction) -> None:
        self.inner_transactions.append(itxn)

    def any_account(self) -> Account:
        new_account_address = algosdk.account.generate_account()[1]
        new_account = Account(new_account_address)
        self.add_account(new_account)
        return new_account

    def any_asset(self) -> Asset:
        new_asset = Asset(self._next_asset_id())
        self.add_asset(new_asset)
        return new_asset

    def any_application(self) -> Application:
        new_app = Application(self._next_app_id())
        self.add_application(new_app)
        return new_app

    def any_uint64(self, min_value: int = 0, max_value: int = MAX_UINT64) -> UInt64:
        if max_value > MAX_UINT64:
            raise ValueError("max_value must be less than or equal to MAX_UINT64")
        if min_value > max_value:
            raise ValueError("min_value must be less than or equal to max_value")

        random_value = random.randint(min_value, max_value)  # noqa: S311
        return UInt64(random_value)

    def any_bytes(self, length: int = MAX_BYTES_SIZE) -> Bytes:
        return Bytes(random.randbytes(length))  # noqa: S311


_var: ContextVar[TestContext[Any]] = ContextVar("_var")


def get_test_context() -> TestContext[Any]:
    return _var.get()


@contextmanager
def blockchain_context() -> Generator[TestContext[Any], None, None]:
    token = _var.set(TestContext[Any]())
    try:
        yield _var.get()
    finally:
        _var.reset(token)
