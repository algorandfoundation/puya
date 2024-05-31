from __future__ import annotations

import random
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Generic, TypeVar, Unpack

import algosdk

from algopy_testing.constants import MAX_BYTES_SIZE, MAX_UINT64
from algopy_testing.models.global_state import GlobalFields
from algopy_testing.models.itxn import ITxnFields
from algopy_testing.models.txn import TxnFields

if TYPE_CHECKING:
    from collections.abc import Generator

    import algopy

    from algopy_testing.itxn import BaseInnerTransaction


T = TypeVar("T")
U = TypeVar("U")


class AlgopyTestContext(Generic[T]):
    def __init__(self, contract_cls: type[T] | None = None) -> None:
        self._contract_cls = (
            contract_cls  # TODO: not utilized yet, just storing the reference for now
        )
        self.accounts: dict[str, algopy.Account] = {}
        self.applications: dict[int, algopy.Application] = {}
        self.assets: dict[int, algopy.Asset] = {}
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

    def set_global_fields(self, **txn_fields: Unpack[GlobalFields]) -> None:
        for key, value in txn_fields.items():
            if key in GlobalFields.__annotations__:
                self.global_fields[key] = value
            else:
                raise AttributeError(
                    f"`algopy.Global` has no attribute '{key}' to set in the test context!"
                )

    def set_txn_fields(self, **txn_fields: Unpack[TxnFields]) -> None:
        for key, value in txn_fields.items():
            if key in TxnFields.__annotations__:
                self.txn_fields[key] = value
            else:
                raise AttributeError(
                    f"`algopy.Txn` has no attribute '{key}' to set in the test context!"
                )

    def set_itxn_fields(self, **itxn_fields: Unpack[ITxnFields]) -> None:
        """
        Sets the inner transaction fields for the test context.

        This method initializes and sets the inner transaction fields using the provided `ITxn`
        object.
        Only the fields that are present in the `ITxn` class and have non-None values in `kwargs`
        will be set.

        Args:
            kwargs (algopy.op.ITxn): Object representing the inner transaction fields to be set.
        """
        for key, value in itxn_fields.items():
            if key in ITxnFields.__annotations__:
                self.itxn_fields[key] = value
            else:
                raise AttributeError(
                    f"`algopy.ITxn` has no attribute '{key}' to set in the test context!"
                )

    def add_account(self, account: algopy.Account) -> None:
        """
        Adds an account to the test context.

        This method adds the provided account to the test context's account dictionary.
        The account must be an instance of `Account` and must have a valid address.

        Args:
            account (algopy.Account): The account to be added.

        Raises:
            TypeError: If the account is not an instance of `Account`.
            ValueError: If the account does not have a valid address.
        """
        from algopy import Account

        if not isinstance(account, Account):
            raise TypeError("account must be an instance of Account")
        if not account.bytes:
            raise ValueError("Account address is required")
        self.accounts[str(account)] = account

    def get_account(self, address: str) -> algopy.Account:
        """
        Retrieves an account from the test context.

        This method retrieves the account associated with the provided address from the test
        context's account dictionary.

        Args:
            address (str): The address of the account to be retrieved.

        Returns:
            algopy.Account: The account associated with the provided address.
        """
        return self.accounts[address]

    def update_account(self, address: str, account: algopy.Account) -> None:
        """
        Updates an account in the test context.

        This method updates the account associated with the provided address in the test context's
        account dictionary.
        The account must be an instance of `Account`.

        Args:
            address (str): The address of the account to be updated.
            account (algopy.Account): The new account data.

        Raises:
            TypeError: If the account is not an instance of `Account`.
        """
        from algopy import Account

        if not isinstance(account, Account):
            raise TypeError("account must be an instance of Account")

        self.accounts[address] = account

    def add_asset(self, asset: algopy.Asset) -> None:
        """
        Adds an asset to the test context.

        This method adds the provided asset to the test context's asset dictionary.
        The asset must be an instance of `Asset` and must have a valid ID.

        Args:
            asset (algopy.Asset): The asset to be added.

        Raises:
            TypeError: If the asset is not an instance of `Asset`.
            ValueError: If the asset does not have a valid ID.
        """
        from algopy import Asset

        if not isinstance(asset, Asset):
            raise TypeError("asset must be an instance of Asset")

        if not asset.id:
            raise ValueError("Asset ID is required")

        self.assets[int(asset.id)] = asset

    def get_asset(self, asset_id: int) -> algopy.Asset:
        """
        Retrieves an asset from the test context.

        This method retrieves the asset associated with the provided asset ID from the test
        context's asset dictionary.

        Args:
            asset_id (int): The ID of the asset to be retrieved.

        Returns:
            algopy.Asset: The asset associated with the provided ID.
        """
        return self.assets[asset_id]

    def update_asset(self, asset_id: int, asset: algopy.Asset) -> None:
        """
        Updates an asset in the test context.

        This method updates the asset associated with the provided asset ID in the test context's
        asset dictionary.

        Args:
            asset_id (int): The ID of the asset to be updated.
            asset (algopy.Asset): The new asset data.
        """
        self.assets[asset_id] = asset

    def add_application(self, app: algopy.Application) -> None:
        """
        Adds an application to the test context.

        This method adds the provided application to the test context's application dictionary.
        The application must be an instance of `Application` and must have a valid ID.

        Args:
            app (algopy.Application): The application to be added.

        Raises:
            TypeError: If the application is not an instance of `Application`.
            ValueError: If the application does not have a valid ID.
        """
        from algopy import Application

        if not isinstance(app, Application):
            raise TypeError("app must be an instance of Application")
        if not app.id:
            raise ValueError("Application ID is required")

        self.applications[int(app.id)] = app

    def get_application(self, app_id: int) -> algopy.Application:
        """
        Retrieves an application from the test context.

        This method retrieves the application associated with the provided application ID from
        the test context's application dictionary.

        Args:
            app_id (int): The ID of the application to be retrieved.

        Returns:
            algopy.Application: The application associated with the provided ID.
        """
        return self.applications[app_id]

    def add_inner_transaction(self, itxn: BaseInnerTransaction) -> None:
        """
        Adds an inner transaction to the test context.

        This method adds the provided inner transaction to the test context's inner
        transaction list.
        The inner transaction must be an instance of `BaseInnerTransaction`.

        Args:
            itxn (BaseInnerTransaction): The inner transaction to be added.

        Raises:
            TypeError: If the inner transaction is not an instance of `BaseInnerTransaction`.
        """
        from algopy_testing.itxn import BaseInnerTransaction

        if not isinstance(itxn, BaseInnerTransaction):
            raise TypeError("Invalid base itxn type")

        self.inner_transactions.append(itxn)

    def any_account(self) -> algopy.Account:
        """
        Generates and adds a new account to the test context.

        This method generates a new account with a random address and adds it to
        the test context's account dictionary.

        Returns:
            algopy.Account: The newly generated account.
        """
        from algopy import Account

        new_account_address = algosdk.account.generate_account()[1]
        new_account = Account(new_account_address)
        self.add_account(new_account)
        return new_account

    def any_asset(self) -> algopy.Asset:
        """
        Generates and adds a new asset to the test context.

        This method generates a new asset with a unique ID and adds it to the test
        context's asset dictionary.

        Returns:
            algopy.Asset: The newly generated asset.
        """
        from algopy import Asset

        new_asset = Asset(self._next_asset_id())
        self.add_asset(new_asset)
        return new_asset

    def any_application(self) -> algopy.Application:
        """
        Generates and adds a new application to the test context.

        This method generates a new application with a unique ID and adds it to the
        test context's application dictionary.

        Returns:
            Application: The newly generated application.
        """
        from algopy import Application

        new_app = Application(self._next_app_id())
        self.add_application(new_app)
        return new_app

    def set_transaction_group(self, gtxn: list[algopy.gtxn.TransactionBase]) -> None:
        """
        Sets the transaction group for the test context.

        This method sets the transaction group using the provided list of transactions.

        Args:
            gtxn (list[algopy.gtxn.TransactionBase]): The list of transactions to be set as
            the transaction group.
        """
        self.gtxns = gtxn

    def get_transaction_group(self) -> list[algopy.gtxn.TransactionBase]:
        """
        Retrieves the transaction group from the test context.

        This method retrieves the current transaction group from the test context.

        Returns:
            list[algopy.gtxn.TransactionBase]: The current transaction group.
        """
        return self.gtxns

    def any_uint64(self, min_value: int = 0, max_value: int = MAX_UINT64) -> algopy.UInt64:
        """
        Generates a random UInt64 value within the specified range.

        This method generates a random UInt64 value between `min_value` and `max_value`.

        Args:
            min_value (int, optional): The minimum value for the random generation. Defaults to 0.
            max_value (int, optional): The maximum value for the random generation. Defaults
            to MAX_UINT64.

        Returns:
            algopy.UInt64: The randomly generated UInt64 value.

        Raises:
            ValueError: If `max_value` is greater than MAX_UINT64 or if `min_value` is greater
            than `max_value`.
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
        Generates a random byte sequence of the specified length.

        This method generates a random byte sequence with the specified length.

        Args:
            length (int, optional): The length of the byte sequence. Defaults to MAX_BYTES_SIZE.

        Returns:
            algopy.Bytes: The randomly generated byte sequence.
        """
        from algopy import Bytes

        return Bytes(random.randbytes(length))  # noqa: S311

    def any_axfer_txn(self, **kwargs: Any) -> algopy.gtxn.AssetTransferTransaction:
        """
        Generates a new asset transfer transaction with the specified fields.

        This method generates a new asset transfer transaction and sets its fields using the
        provided keyword arguments.

        Args:
            **kwargs (Any): Keyword arguments representing the fields to be set in the transaction.

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
        Generates a new payment transaction with the specified fields.

        Args:
            **kwargs (Any): Keyword arguments representing the fields to be set in the transaction.

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
        Clears all inner transactions from the test context.
        """
        self.inner_transactions = []

    def clear_transaction_group(self) -> None:
        """
        Clears the transaction group from the test context.
        """
        self.gtxns = []

    def clear_accounts(self) -> None:
        """
        Clears all accounts from the test context.
        """
        self.accounts = {}

    def clear_applications(self) -> None:
        """
        Clears all applications from the test context.
        """
        self.applications = {}

    def clear_assets(self) -> None:
        """
        Clears all assets from the test context.
        """
        self.assets = {}

    def clear_logs(self) -> None:
        """
        Clears all logs from the test context.
        """
        self.logs = []

    def clear(self) -> None:
        """
        Clears all data from the test context.

        This method removes all accounts, applications, assets, inner transactions,
        transaction groups, and logs from the test context.
        """
        self.clear_accounts()
        self.clear_applications()
        self.clear_assets()
        self.clear_inner_transactions()
        self.clear_transaction_group()
        self.clear_logs()

    def reset(self) -> None:
        """
        Resets the test context to its initial state.

        This method clears all data from the test context and resets the asset and
        application ID counters to their initial values.
        """
        self.accounts = {}
        self.applications = {}
        self.assets = {}
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
