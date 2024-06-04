from __future__ import annotations

import random
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Generic, TypeVar, Unpack

import algosdk

from algopy_testing.constants import MAX_BYTES_SIZE, MAX_UINT64
from algopy_testing.models.account import AccountData, AccountFields
from algopy_testing.models.application import ApplicationFields
from algopy_testing.models.asset import AssetFields
from algopy_testing.models.global_state import GlobalFields
from algopy_testing.models.itxn import ITxnFields
from algopy_testing.models.txn import TxnFields

if TYPE_CHECKING:
    from collections.abc import Generator

    import algopy
    import algopy.gtxn

    from algopy_testing.itxn import BaseInnerTransaction


T = TypeVar("T")
U = TypeVar("U")


class AlgopyTestContext(Generic[T]):
    def __init__(self, contract_cls: type[T] | None = None) -> None:
        self._contract_cls = (
            contract_cls  # TODO: not utilized yet, just storing the reference for now
        )
        self.account_data: dict[str, AccountData] = {}
        self.application_data: dict[int, ApplicationFields] = {}
        self.asset_data: dict[int, AssetFields] = {}
        self.inner_transactions: list[BaseInnerTransaction] = []
        self.global_fields: dict[str, Any] = {}
        self.txn_fields: dict[str, Any] = {}
        self.itxn_fields: dict[str, Any] = {}
        self.gtxns: list[algopy.gtxn.TransactionBase] = []
        self.logs: list[str] = []
        self._asset_id_count: int = 1
        self._app_id_count: int = 1

    def _next_asset_id(self) -> int:
        self._asset_id_count += 1
        return self._asset_id_count

    def _next_app_id(self) -> int:
        self._app_id_count += 1
        return self._app_id_count

    def patch_global_fields(self, **global_fields: Unpack[GlobalFields]) -> None:
        """
        Patch 'Global' fields in the test context based on provided key-value pairs.

        Args:
            **global_fields: Key-value pairs corresponding to global fields.

        Raises:
            AttributeError: If a key does not correspond to a valid global field.
        """
        for key, value in global_fields.items():
            if key in GlobalFields.__annotations__:
                self.global_fields[key] = value
            else:
                raise AttributeError(
                    f"`algopy.Global` has no attribute '{key}' to set in the test context!"
                )

    def patch_txn_fields(self, **txn_fields: Unpack[TxnFields]) -> None:
        """
        Patch 'algopy.Txn' fields in the test context based on provided key-value pairs.

        Args:
            **txn_fields: Key-value pairs corresponding to transaction fields.

        Raises:
            AttributeError: If a key does not correspond to a valid transaction field.
        """
        for key, value in txn_fields.items():
            if key in TxnFields.__annotations__:
                self.txn_fields[key] = value
            else:
                raise AttributeError(
                    f"`algopy.Txn` has no attribute '{key}' to set in the test context!"
                )

    def patch_itxn_fields(self, **itxn_fields: Unpack[ITxnFields]) -> None:
        """
        Patch 'algopy.ITxn' fields in the test context based on provided key-value pairs.

        Args:
            **itxn_fields: Key-value pairs corresponding to inner transaction fields.

        Raises:
            AttributeError: If a key does not correspond to a valid inner transaction field.
        """
        for key, value in itxn_fields.items():
            if key in ITxnFields.__annotations__:
                self.itxn_fields[key] = value
            else:
                raise AttributeError(
                    f"`algopy.ITxn` has no attribute '{key}' to set in the test context!"
                )

    def get_account_data(self, address: str) -> AccountData:
        """
        Retrieve an account from the test context by address.

        Args:
            address (str): The address of the account to retrieve.

        Returns:
            algopy.Account: The account associated with the provided address.
        """

        return self.account_data[address]

    def update_account(self, address: str, **account_fields: Unpack[AccountFields]) -> None:
        """
        Update an existing account in the test context.

        Args:
            address (str): The address of the account to update.
            account (algopy.Account): The new account data.

        Raises:
            TypeError: If the provided object is not an instance of `Account`.
        """

        if address not in self.account_data:
            raise ValueError("Account not found")

        for key, value in account_fields.items():
            setattr(self.account_data[address].data, key, value)

    def get_asset_data(self, asset_id: int) -> AssetFields:
        """
        Retrieve an asset from the test context by ID.

        Args:
            asset_id (int): The ID of the asset to retrieve.

        Returns:
            algopy.Asset: The asset associated with the provided ID.
        """
        if asset_id not in self.asset_data:
            raise ValueError("Asset not found in testing context!")

        return self.asset_data[asset_id]

    def update_asset(self, asset_id: int, **asset_fields: Unpack[AssetFields]) -> None:
        """
        Update an existing asset in the test context.

        Args:
            asset_id (int): The ID of the asset to update.
            asset (algopy.Asset): The new asset data.
        """
        if asset_id not in self.asset_data:
            raise ValueError("Asset not found in testing context!")

        for key, value in asset_fields.items():
            setattr(self.asset_data[asset_id], key, value)

    def get_application(self, app_id: int) -> algopy.Application:
        """
        Retrieve an application from the test context by ID.

        Args:
            app_id (int): The ID of the application to retrieve.

        Returns:
            algopy.Application: The application associated with the provided ID.
        """
        from algopy import Application

        if app_id not in self.application_data:
            raise ValueError("Application not found in testing context!")

        return Application(app_id)

    def add_inner_transaction(self, itxn: BaseInnerTransaction) -> None:
        """
        Add an inner transaction to the test context.

        Args:
            itxn (BaseInnerTransaction): The inner transaction to be added.

        Raises:
            TypeError: If the provided object is not an instance of `BaseInnerTransaction`.
        """
        from algopy_testing.itxn import BaseInnerTransaction

        if not isinstance(itxn, BaseInnerTransaction):
            raise TypeError("Invalid base itxn type")

        self.inner_transactions.append(itxn)

    def any_account(
        self,
        address: str | None = None,
        opted_asset_balances: dict[algopy.UInt64, algopy.UInt64] | None = None,
        opted_apps: dict[algopy.UInt64, algopy.Application] | None = None,
        **account_fields: Unpack[AccountFields],
    ) -> algopy.Account:
        """
        Generate and add a new account with a random address to the test context.

        Returns:
            algopy.Account: The newly generated account.
        """
        from algopy import Account

        if address and not algosdk.encoding.is_valid_address(address):
            raise ValueError("Invalid Algorand address supplied!")

        if address in self.account_data:
            raise ValueError(
                "Account with such address already exists in testing context! "
                "Use `context.get_account_data(address)` to retrieve the existing account."
            )

        for key in account_fields:
            if key not in AccountFields.__annotations__:
                raise AttributeError(f"Invalid field '{key}' for Account")

        new_account_address = address or algosdk.account.generate_account()[1]
        new_account = Account(new_account_address)
        new_account_fields = AccountFields(**account_fields)
        new_account_data = AccountData(
            data=new_account_fields,
            opted_asset_balances=opted_asset_balances or {},
            opted_apps=opted_apps or {},
        )

        self.account_data[new_account_address] = new_account_data
        return new_account

    def any_asset(
        self, asset_id: int | None = None, **asset_fields: Unpack[AssetFields]
    ) -> algopy.Asset:
        """
        Generate and add a new asset with a unique ID to the test context.

        Returns:
            algopy.Asset: The newly generated asset.
        """
        from algopy import Asset

        if asset_id and asset_id in self.asset_data:
            raise ValueError("Asset with such ID already exists in testing context!")

        new_asset = Asset(asset_id or self._next_asset_id())
        self.asset_data[int(new_asset.id)] = AssetFields(**asset_fields)
        return new_asset

    def any_application(
        self, **application_fields: Unpack[ApplicationFields]
    ) -> algopy.Application:
        """
        Generate and add a new application with a unique ID to the test context.

        Returns:
            Application: The newly generated application.
        """
        from algopy import Application

        new_app = Application(self._next_app_id())
        self.application_data[int(new_app.id)] = ApplicationFields(**application_fields)
        return new_app

    def set_transaction_group(self, gtxn: list[algopy.gtxn.TransactionBase]) -> None:
        """
        Set the transaction group in the test context using a list of transactions.

        Args:
            gtxn (list[algopy.gtxn.TransactionBase]): The list of transactions to set.
        """
        self.gtxns = gtxn

    def get_transaction_group(self) -> list[algopy.gtxn.TransactionBase]:
        """
        Retrieve the current transaction group from the test context.

        Returns:
            list[algopy.gtxn.TransactionBase]: The current transaction group.
        """
        return self.gtxns

    def any_uint64(self, min_value: int = 0, max_value: int = MAX_UINT64) -> algopy.UInt64:
        """
        Generate a random UInt64 value within a specified range.

        Args:
            min_value (int, optional): Minimum value for the random generation. Defaults to 0.
            max_value (int, optional): Maximum value for the random generation.
            Defaults to MAX_UINT64.

        Returns:
            algopy.UInt64: The randomly generated UInt64 value.

        Raises:
            ValueError: If `max_value` exceeds MAX_UINT64 or `min_value` exceeds `max_value`.
        """
        from algopy import UInt64

        if max_value > MAX_UINT64:
            raise ValueError("max_value must be less than or equal to MAX_UINT64")
        if min_value > max_value:
            raise ValueError("min_value must be less than or equal to max_value")

        random_value = random.randint(min_value, max_value)  # noqa: S311
        return UInt64(random_value)

    def any_bytes(self, length: int = MAX_BYTES_SIZE) -> algopy.Bytes:
        """
        Generate a random byte sequence of a specified length.

        Args:
            length (int, optional): The length of the byte sequence. Defaults to MAX_BYTES_SIZE.

        Returns:
            algopy.Bytes: The randomly generated byte sequence.
        """
        from algopy import Bytes

        return Bytes(random.randbytes(length))  # noqa: S311

    def any_axfer_txn(self, **kwargs: Any) -> algopy.gtxn.AssetTransferTransaction:
        """
        Generate a new asset transfer transaction with specified fields.

        Args:
            **kwargs (Any): Fields to be set in the transaction.

        Returns:
            algopy.gtxn.AssetTransferTransaction: The newly generated asset transfer transaction.
        """
        from algopy import gtxn

        new_txn = gtxn.AssetTransferTransaction(0)

        for key, value in kwargs.items():
            setattr(new_txn, key, value)

        return new_txn

    def any_pay_txn(self, **kwargs: Any) -> algopy.gtxn.PaymentTransaction:
        """
        Generate a new payment transaction with specified fields.

        Args:
            **kwargs (Any): Fields to be set in the transaction.

        Returns:
            algopy.gtxn.PaymentTransaction: The newly generated payment transaction.
        """
        from algopy import gtxn

        new_txn = gtxn.PaymentTransaction(0)

        for key, value in kwargs.items():
            setattr(new_txn, key, value)

        return new_txn

    def clear_inner_transactions(self) -> None:
        """
        Clear all inner transactions from the test context.
        """
        self.inner_transactions.clear()

    def clear_transaction_group(self) -> None:
        """
        Clear the transaction group from the test context.
        """
        self.gtxns.clear()

    def clear_accounts(self) -> None:
        """
        Clear all accounts from the test context.
        """
        self.account_data.clear()

    def clear_applications(self) -> None:
        """
        Clear all applications from the test context.
        """
        self.application_data.clear()

    def clear_assets(self) -> None:
        """
        Clear all assets from the test context.
        """
        self.asset_data.clear()

    def clear_logs(self) -> None:
        """
        Clear all logs from the test context.
        """
        self.logs.clear()

    def clear(self) -> None:
        """
        Clear all data from the test context, including accounts, applications, assets,
        inner transactions, transaction groups, and logs.
        """
        self.clear_accounts()
        self.clear_applications()
        self.clear_assets()
        self.clear_inner_transactions()
        self.clear_transaction_group()
        self.clear_logs()

    def reset(self) -> None:
        """
        Reset the test context to its initial state, clearing all data and resetting ID counters.
        """
        self.account_data = {}
        self.application_data = {}
        self.asset_data = {}
        self.inner_transactions = []
        self.gtxns = []
        self.global_fields = {}
        self.txn_fields = {}
        self.itxn_fields = {}
        self.logs = []
        self._asset_id_count = 1
        self._app_id_count = 1


_var: ContextVar[AlgopyTestContext[Any]] = ContextVar("_var")


def get_test_context() -> AlgopyTestContext[Any]:
    return _var.get()


@contextmanager
def algopy_testing_context(
    contract_cls: type[Any] | None = None,
) -> Generator[AlgopyTestContext[Any], None, None]:
    token = _var.set(AlgopyTestContext[Any](contract_cls))
    try:
        yield _var.get()
    finally:
        _var.reset(token)
