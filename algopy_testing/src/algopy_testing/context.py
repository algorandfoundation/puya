from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from algopy_testing.models.account import Account
from algopy_testing.models.application import Application
from algopy_testing.models.asset import Asset
from algopy_testing.models.global_state import GlobalFields
from algopy_testing.models.itxn import ITxnFields
from algopy_testing.models.txn import TxnFields

if TYPE_CHECKING:
    from collections.abc import Generator


T = TypeVar("T")


class TestContext(Generic[T]):
    def __init__(self) -> None:
        self.accounts: dict[str, Account] = {}
        self.applications: dict[int, Application] = {}
        self.assets: dict[int, Asset] = {}
        self.global_state: GlobalFields = GlobalFields()
        self.transaction_state: TxnFields = TxnFields()
        self.itxn_state: ITxnFields = ITxnFields()

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
