from __future__ import annotations

import secrets
import string
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

# Define the union type
from typing import TYPE_CHECKING, TypeVar, Unpack, cast

import algosdk

from algopy_testing.constants import DEFAULT_GLOBAL_GENESIS_HASH, MAX_BYTES_SIZE, MAX_UINT64
from algopy_testing.models.account import AccountFields
from algopy_testing.models.application import ApplicationFields
from algopy_testing.models.asset import AssetFields
from algopy_testing.models.global_values import GlobalFields
from algopy_testing.models.txn import TxnFields

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    import algopy

    from algopy_testing.gtxn import (
        ApplicationCallFields,
        AssetTransferFields,
        PaymentFields,
        TransactionFields,
    )

    InnerTransactionResultType = (
        algopy.itxn.InnerTransactionResult
        | algopy.itxn.PaymentInnerTransaction
        | algopy.itxn.KeyRegistrationInnerTransaction
        | algopy.itxn.AssetConfigInnerTransaction
        | algopy.itxn.AssetTransferInnerTransaction
        | algopy.itxn.AssetFreezeInnerTransaction
        | algopy.itxn.ApplicationCallInnerTransaction
    )


T = TypeVar("T")


@dataclass
class AccountContextData:
    """
    Stores account-related information.

    Attributes:
        opted_asset_balances (dict[int, algopy.UInt64]): Mapping of asset IDs to balances.
        opted_apps (dict[int, algopy.UInt64]): Mapping of application IDs to instances.
        fields (AccountFields): Additional account fields.
    """

    opted_asset_balances: dict[algopy.UInt64, algopy.UInt64]
    opted_apps: dict[algopy.UInt64, algopy.Application]
    fields: AccountFields


@dataclass
class ContractContextData:
    """
    Stores contract-related information.

    Attributes:
        contract (algopy.Contract | algopy.ARC4Contract): Contract instance.
        app_id (algopy.UInt64): Application ID.
    """

    contract: algopy.Contract | algopy.ARC4Contract
    app_id: algopy.UInt64


class AlgopyTestContext:
    def __init__(
        self,
        *,
        default_creator: algopy.Account | None = None,
        default_application: algopy.Application | None = None,
    ) -> None:
        import algopy

        self._asset_id = iter(range(1001, 2**64))
        self._app_id = iter(range(1001, 2**64))

        self.contracts: list[algopy.Contract | algopy.ARC4Contract] = []
        self.txn_fields: TxnFields = {}
        self.gtxns: list[algopy.gtxn.TransactionBase] = []
        self.active_transaction_index: int | None = None
        self.account_data: dict[str, AccountContextData] = {}
        self.application_data: dict[int, ApplicationFields] = {}
        self.asset_data: dict[int, AssetFields] = {}
        self.inner_transaction_groups: list[Sequence[InnerTransactionResultType]] = []
        self.logs: list[str] = []
        self.default_creator = default_creator or algopy.Account(
            algosdk.account.generate_account()[1]
        )

        default_application_address = (
            self.any_account() if default_application is None else default_application.address
        )
        self.default_application = default_application or self.any_application(
            address=default_application_address
        )
        self.global_fields: GlobalFields = {
            "min_txn_fee": algopy.UInt64(algosdk.constants.MIN_TXN_FEE),
            "min_balance": algopy.UInt64(100_000),
            "max_txn_life": algopy.UInt64(1_000),
            "zero_address": algopy.Account(algosdk.constants.ZERO_ADDRESS),
            "creator_address": self.default_creator,
            "current_application_address": default_application_address,
            "asset_create_min_balance": algopy.UInt64(100_000),
            "asset_opt_in_min_balance": algopy.UInt64(10_000),
            "genesis_hash": algopy.Bytes(DEFAULT_GLOBAL_GENESIS_HASH),
        }

    def patch_global_fields(self, **global_fields: Unpack[GlobalFields]) -> None:
        """
        Patch 'Global' fields in the test context.

        Args:
            **global_fields: Key-value pairs for global fields.

        Raises:
            AttributeError: If a key is invalid.
        """
        invalid_keys = global_fields.keys() - GlobalFields.__annotations__.keys()

        if invalid_keys:
            raise AttributeError(
                f"Invalid field(s) found during patch for `Global`: {', '.join(invalid_keys)}"
            )

        self.global_fields.update(global_fields)

    def patch_txn_fields(self, **txn_fields: Unpack[TxnFields]) -> None:
        """
        Patch 'algopy.Txn' fields in the test context.

        Args:
            **txn_fields: Key-value pairs for transaction fields.

        Raises:
            AttributeError: If a key is invalid.
        """
        invalid_keys = txn_fields.keys() - TxnFields.__annotations__.keys()
        if invalid_keys:
            raise AttributeError(
                f"Invalid field(s) found during patch for `Txn`: {', '.join(invalid_keys)}"
            )

        self.txn_fields.update(txn_fields)

    def get_account(self, address: str) -> algopy.Account:
        """
        Retrieve an account by address.

        Args:
            address (str): Account address.

        Returns:
            algopy.Account: The account associated with the address.
        """
        import algopy

        if address not in self.account_data:
            raise ValueError("Account not found in testing context!")

        return algopy.Account(address)

    def update_account(self, address: str, **account_fields: Unpack[AccountFields]) -> None:
        """
        Update an existing account.

        Args:
            address (str): Account address.
            **account_fields: New account data.

        Raises:
            TypeError: If the provided object is not an instance of `Account`.
        """

        if address not in self.account_data:
            raise ValueError("Account not found")

        self.account_data[address].fields.update(account_fields)

    def get_opted_asset_balance(
        self, account: algopy.Account, asset_id: algopy.UInt64
    ) -> algopy.UInt64 | None:
        """
        Retrieve the opted asset balance for an account and asset ID.

        Args:
            account (algopy.Account): Account to retrieve the balance for.
            asset_id (algopy.UInt64): Asset ID.

        Returns:
            algopy.UInt64 | None: The opted asset balance or None if not opted in.
        """

        response = self.account_data.get(
            str(account),
            AccountContextData(fields=AccountFields(), opted_asset_balances={}, opted_apps={}),
        ).opted_asset_balances.get(asset_id, None)

        return response

    def get_asset(self, asset_id: algopy.UInt64 | int) -> algopy.Asset:
        """
        Retrieve an asset by ID.

        Args:
            asset_id (int): Asset ID.

        Returns:
            algopy.Asset: The asset associated with the ID.
        """
        import algopy

        asset_id = int(asset_id) if isinstance(asset_id, algopy.UInt64) else asset_id

        if asset_id not in self.asset_data:
            raise ValueError("Asset not found in testing context!")

        return algopy.Asset(asset_id)

    def update_asset(self, asset_id: int, **asset_fields: Unpack[AssetFields]) -> None:
        """
        Update an existing asset.

        Args:
            asset_id (int): Asset ID.
            **asset_fields: New asset data.
        """
        if asset_id not in self.asset_data:
            raise ValueError("Asset not found in testing context!")

        self.asset_data[asset_id].update(asset_fields)

    def get_application(self, app_id: algopy.UInt64 | int) -> algopy.Application:
        """
        Retrieve an application by ID.

        Args:
            app_id (int): Application ID.

        Returns:
            algopy.Application: The application associated with the ID.
        """
        import algopy

        app_id = int(app_id) if isinstance(app_id, algopy.UInt64) else app_id

        if app_id not in self.application_data:
            raise ValueError("Application not found in testing context!")

        return algopy.Application(app_id)

    def update_application(
        self, app_id: int, **application_fields: Unpack[ApplicationFields]
    ) -> None:
        """
        Update an existing application.

        Args:
            app_id (int): Application ID.
            **application_fields: New application data.
        """
        if app_id not in self.application_data:
            raise ValueError("Application not found in testing context!")

        self.application_data[app_id].update(application_fields)

    def add_contract(
        self,
        contract: algopy.Contract | algopy.ARC4Contract,
    ) -> None:
        """
        Add a contract to the context.

        Args:
            contract (algopy.Contract | algopy.ARC4Contract): The contract to add.
        """
        self.contracts.append(contract)

    def append_inner_transaction_group(
        self,
        itxn: Sequence[InnerTransactionResultType],
    ) -> None:
        """
        Append a group of inner transactions to the context.

        Args:
            itxn (Sequence[InnerTransactionResultType]): The group of inner transactions to append.
        """

        self.inner_transaction_groups.append(itxn)

    def get_last_inner_transaction_group(self) -> Sequence[InnerTransactionResultType]:
        """
        Retrieve the last group of inner transactions.

        Returns:
            Sequence[InnerTransactionResultType]: The last group of inner transactions.

        Raises:
            ValueError: If no inner transaction groups have been submitted yet.
        """

        if not self.inner_transaction_groups:
            raise ValueError("No inner transaction groups submitted yet!")
        return self.inner_transaction_groups[-1]

    def get_last_submitted_inner_transaction(self) -> InnerTransactionResultType:
        """
        Retrieve the last submitted inner transaction.

        Returns:
            InnerTransactionResultType: The last submitted inner transaction.

        Raises:
            ValueError: If no inner transactions exist in the last inner transaction group.
        """

        inner_transaction_group = self.get_last_inner_transaction_group()
        if not inner_transaction_group:
            raise ValueError("No inner transactions in the last inner transaction group!")
        return inner_transaction_group[-1]

    def any_account(
        self,
        address: str | None = None,
        opted_asset_balances: dict[algopy.UInt64, algopy.UInt64] | None = None,
        opted_apps: dict[algopy.UInt64, algopy.Application] | None = None,
        **account_fields: Unpack[AccountFields],
    ) -> algopy.Account:
        """
        Generate and add a new account with a random address.

        Returns:
            algopy.Account: The newly generated account.
        """
        import algopy

        if address and not algosdk.encoding.is_valid_address(address):
            raise ValueError("Invalid Algorand address supplied!")

        if address in self.account_data:
            raise ValueError(
                "Account with such address already exists in testing context! "
                "Use `context.get_account(address)` to retrieve the existing account."
            )

        for key in account_fields:
            if key not in AccountFields.__annotations__:
                raise AttributeError(f"Invalid field '{key}' for Account")

        new_account_address = address or algosdk.account.generate_account()[1]
        new_account = algopy.Account(new_account_address)
        new_account_fields = AccountFields(**account_fields)
        new_account_data = AccountContextData(
            fields=new_account_fields,
            opted_asset_balances=opted_asset_balances or {},
            opted_apps=opted_apps or {},
        )

        self.account_data[new_account_address] = new_account_data

        return new_account

    def any_asset(
        self, asset_id: int | None = None, **asset_fields: Unpack[AssetFields]
    ) -> algopy.Asset:
        """
        Generate and add a new asset with a unique ID.

        Returns:
            algopy.Asset: The newly generated asset.
        """
        import algopy

        if asset_id and asset_id in self.asset_data:
            raise ValueError("Asset with such ID already exists in testing context!")

        new_asset = algopy.Asset(asset_id or next(self._asset_id))
        self.asset_data[int(new_asset.id)] = AssetFields(**asset_fields)
        return new_asset

    def any_application(
        self, **application_fields: Unpack[ApplicationFields]
    ) -> algopy.Application:
        """
        Generate and add a new application with a unique ID.

        Returns:
            Application: The newly generated application.
        """
        import algopy

        new_app = algopy.Application(next(self._app_id))
        self.application_data[int(new_app.id)] = ApplicationFields(**application_fields)
        return new_app

    def set_transaction_group(
        self, gtxn: list[algopy.gtxn.TransactionBase], active_transaction_index: int | None = None
    ) -> None:
        """
        Set the transaction group using a list of transactions.

        Args:
            gtxn (list[algopy.gtxn.TransactionBase]): List of transactions.
            active_transaction_index (int, optional): Index of the active transaction.
            Defaults to None.
        """
        self.gtxns = gtxn

        if active_transaction_index is not None:
            self.set_active_transaction_index(active_transaction_index)

    def add_transactions(
        self,
        gtxns: list[algopy.gtxn.TransactionBase],
    ) -> None:
        """
        Add transactions to the current transaction group.

        Args:
            gtxns (list[algopy.gtxn.TransactionBase]): List of transactions to add.

        Raises:
            ValueError: If any transaction is not an instance of TransactionBase or if the total
            number of transactions exceeds the group limit.
        """
        # ensure that new len after append is at most 16 txns in a group
        import algopy.gtxn

        if not all(isinstance(txn, algopy.gtxn.TransactionBase) for txn in gtxns):  # type: ignore[arg-type, unused-ignore]
            raise ValueError("All transactions must be instances of TransactionBase")

        if len(self.gtxns) + len(gtxns) > algosdk.constants.TX_GROUP_LIMIT:
            raise ValueError(
                f"Transaction group can have at most {algosdk.constants.TX_GROUP_LIMIT} "
                "transactions, as per AVM limits."
            )

        self.gtxns.extend(gtxns)

    def get_transaction_group(self) -> list[algopy.gtxn.TransactionBase]:
        """
        Retrieve the current transaction group.

        Returns:
            list[algopy.gtxn.TransactionBase]: The current transaction group.
        """
        return self.gtxns

    def set_active_transaction_index(self, index: int) -> None:
        """
        Set the index of the active transaction.

        Args:
            index (int): The index of the active transaction.
        """
        self.active_transaction_index = index

    def get_active_transaction(
        self,
    ) -> algopy.gtxn.Transaction | None:
        """
        Retrieve the active transaction of a specified type.

        Args:
            _txn_type (type[T]): The type of the active transaction.

        Returns:
            T | None: The active transaction if it exists, otherwise None.
        """
        import algopy

        if self.active_transaction_index is None:
            return None
        active_txn = self.gtxns[self.active_transaction_index]
        return cast(algopy.gtxn.Transaction, active_txn) if active_txn else None

    def any_uint64(self, min_value: int = 0, max_value: int = MAX_UINT64) -> algopy.UInt64:
        """
        Generate a random UInt64 value within a specified range.

        Args:
            min_value (int, optional): Minimum value. Defaults to 0.
            max_value (int, optional): Maximum value. Defaults to MAX_UINT64.

        Returns:
            algopy.UInt64: The randomly generated UInt64 value.

        Raises:
            ValueError: If `max_value` exceeds MAX_UINT64 or `min_value` exceeds `max_value`.
        """
        import algopy

        if max_value > MAX_UINT64:
            raise ValueError("max_value must be less than or equal to MAX_UINT64")
        if min_value > max_value:
            raise ValueError("min_value must be less than or equal to max_value")

        random_value = secrets.randbelow(max_value - min_value) + min_value
        return algopy.UInt64(random_value)

    def any_bytes(self, length: int = MAX_BYTES_SIZE) -> algopy.Bytes:
        """
        Generate a random byte sequence of a specified length.

        Args:
            length (int, optional): Length of the byte sequence. Defaults to MAX_BYTES_SIZE.

        Returns:
            algopy.Bytes: The randomly generated byte sequence.
        """
        import algopy

        return algopy.Bytes(secrets.token_bytes(length))

    def any_string(self, length: int = MAX_BYTES_SIZE) -> algopy.String:
        """
        Generate a random string of a specified length.
        """
        import algopy

        return algopy.String(
            "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(length))
        )

    def any_app_call_txn(
        self, group_index: int, **kwargs: Unpack[ApplicationCallFields]
    ) -> algopy.gtxn.ApplicationCallTransaction:
        """
        Generate a new application call transaction with specified fields.

        Args:
            group_index (int): Position index in the transaction group.
            **kwargs (Unpack[ApplicationCallFields]): Fields to be set in the transaction.

        Returns:
            algopy.gtxn.ApplicationCallTransaction: The newly generated application
            call transaction.
        """
        import algopy.gtxn

        new_txn = algopy.gtxn.ApplicationCallTransaction(group_index)

        for key, value in kwargs.items():
            setattr(new_txn, key, value)

        return new_txn

    def any_axfer_txn(
        self, group_index: int, **kwargs: Unpack[AssetTransferFields]
    ) -> algopy.gtxn.AssetTransferTransaction:
        """
        Generate a new asset transfer transaction with specified fields.

        Args:
            group_index (int): Position index in the transaction group.
            **kwargs (Unpack[AssetTransferFields]): Fields to be set in the transaction.

        Returns:
            algopy.gtxn.AssetTransferTransaction: The newly generated asset transfer transaction.
        """
        import algopy.gtxn

        new_txn = algopy.gtxn.AssetTransferTransaction(group_index)

        for key, value in kwargs.items():
            setattr(new_txn, key, value)

        return new_txn

    def any_pay_txn(
        self, group_index: int, **kwargs: Unpack[PaymentFields]
    ) -> algopy.gtxn.PaymentTransaction:
        """
        Generate a new payment transaction with specified fields.

        Args:
            group_index (int): Position index in the transaction group.
            **kwargs (Unpack[PaymentFields]): Fields to be set in the transaction.

        Returns:
            algopy.gtxn.PaymentTransaction: The newly generated payment transaction.
        """
        import algopy.gtxn

        new_txn = algopy.gtxn.PaymentTransaction(group_index)

        for key, value in kwargs.items():
            setattr(new_txn, key, value)

        return new_txn

    def any_transaction(  # type: ignore[misc]
        self,
        group_index: int,
        type: algopy.TransactionType,  # noqa: A002
        **kwargs: Unpack[TransactionFields],
    ) -> algopy.gtxn.Transaction:
        """
        Generate a new transaction with specified fields.

        Args:
            group_index (int): Position index in the transaction group.
            type (algopy.TransactionType): Transaction type.
            **kwargs (Unpack[TransactionFields]): Fields to be set in the transaction.

        Returns:
            algopy.gtxn.Transaction: The newly generated transaction.
        """
        import algopy.gtxn

        new_txn = algopy.gtxn.Transaction(group_index, type=type)  # type: ignore[arg-type, unused-ignore]

        for key, value in kwargs.items():
            setattr(new_txn, key, value)

        return new_txn

    def clear_inner_transaction_groups(self) -> None:
        """
        Clear all inner transactions.
        """
        self.inner_transaction_groups.clear()

    def clear_transaction_group(self) -> None:
        """
        Clear the transaction group.
        """
        self.gtxns.clear()

    def clear_accounts(self) -> None:
        """
        Clear all accounts.
        """
        self.account_data.clear()

    def clear_applications(self) -> None:
        """
        Clear all applications.
        """
        self.application_data.clear()

    def clear_assets(self) -> None:
        """
        Clear all assets.
        """
        self.asset_data.clear()

    def clear_logs(self) -> None:
        """
        Clear all logs.
        """
        self.logs.clear()

    def clear(self) -> None:
        """
        Clear all data, including accounts, applications, assets, inner transactions,
        transaction groups, and logs.
        """
        self.clear_accounts()
        self.clear_applications()
        self.clear_assets()
        self.clear_inner_transaction_groups()
        self.clear_transaction_group()
        self.clear_logs()

    def reset(self) -> None:
        """
        Reset the test context to its initial state, clearing all data and resetting ID counters.
        """
        self.account_data = {}
        self.application_data = {}
        self.asset_data = {}
        self.inner_transaction_groups = []
        self.gtxns = []
        self.global_fields = {}
        self.txn_fields = {}
        self.logs = []
        self._asset_id = iter(range(1, 2**64))
        self._app_id = iter(range(1, 2**64))


_var: ContextVar[AlgopyTestContext] = ContextVar("_var")


def get_test_context() -> AlgopyTestContext:
    return _var.get()


@contextmanager
def algopy_testing_context(
    *,
    default_creator: algopy.Account | None = None,
) -> Generator[AlgopyTestContext, None, None]:
    token = _var.set(
        AlgopyTestContext(
            default_creator=default_creator,
        )
    )
    try:
        yield _var.get()
    finally:
        _var.reset(token)
