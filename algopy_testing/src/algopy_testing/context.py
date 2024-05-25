from __future__ import annotations

import dataclasses
import typing
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Generic, TypeVar

from algopy import Account, Application, Asset, Global

if typing.TYPE_CHECKING:
    from collections.abc import Generator


T = TypeVar("T")


@dataclasses.dataclass
class BlockchainContext(Generic[T]):
    accounts: dict[str, Account] = dataclasses.field(default_factory=dict)
    applications: dict[int, Application] = dataclasses.field(default_factory=dict)
    assets: dict[int, Asset] = dataclasses.field(default_factory=dict)
    global_state: Global = dataclasses.field(default_factory=Global)
    # For anything else that is needed to test the algopy codebase
    context_state: dict[str, T] = dataclasses.field(default_factory=dict)

    def create_account(self, address: str) -> Account:
        account = Account(address)
        self.accounts[address] = account
        return account

    def get_account(self, address: str) -> Account:
        return self.accounts[address]

    def update_account(self, address: str, account: Account) -> None:
        self.accounts[address] = account

    def create_asset(self, asset_id: int) -> Asset:
        asset = Asset(asset_id)
        self.assets[asset_id] = asset
        return asset

    def get_asset(self, asset_id: int) -> Asset:
        return self.assets[asset_id]

    def update_asset(self, asset_id: int, asset: Asset) -> None:
        self.assets[asset_id] = asset

    def create_application(self, app_id: int) -> Application:
        app = Application(app_id)
        self.applications[app_id] = app
        return app

    def get_application(self, app_id: int) -> Application:
        return self.applications[app_id]

    def set_global_state(self, global_state: Global) -> None:
        self.global_state = global_state

    def get_global_state(self) -> Global:
        return self.global_state

    def set_custom_value(self, key: str, value: T) -> None:
        self.context_state[key] = value

    def get_custom_value(self, key: str) -> T | None:
        return self.context_state.get(key)


_var = ContextVar[BlockchainContext[Any]]("_var")


def get_blockchain_context() -> BlockchainContext[Any]:
    return _var.get()


@contextmanager
def blockchain_context() -> Generator[BlockchainContext[Any], None, None]:
    token = _var.set(BlockchainContext[Any]())
    try:
        yield _var.get()
    finally:
        _var.reset(token)
