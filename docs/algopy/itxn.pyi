# ruff: noqa: A001, E501, F403, PYI021, PYI034, W291
import typing

from algopy import (
    Account,
    Application,
    Asset,
    Bytes,
    OnCompleteAction,
    String,
    TransactionType,
    UInt64,
)

__all__ = [
    "PaymentInnerTransaction",
    "KeyRegistrationInnerTransaction",
    "AssetConfigInnerTransaction",
    "AssetTransferInnerTransaction",
    "AssetFreezeInnerTransaction",
    "ApplicationCallInnerTransaction",
    "InnerTransactionResult",
    "InnerTransaction",
    "Payment",
    "KeyRegistration",
    "AssetConfig",
    "AssetTransfer",
    "AssetFreeze",
    "ApplicationCall",
    "submit_txns",
]

class PaymentInnerTransaction:
    """Payment inner transaction"""
    @property
    def receiver(self) -> Account:
        """32 byte address"""
    @property
    def amount(self) -> UInt64:
        """microalgos"""
    @property
    def close_remainder_to(self) -> Account:
        """32 byte address"""
    @property
    def sender(self) -> Account:
        """32 byte address"""
    @property
    def fee(self) -> UInt64:
        """microalgos"""
    @property
    def first_valid(self) -> UInt64:
        """round number"""
    @property
    def first_valid_time(self) -> UInt64:
        """UNIX timestamp of block before txn.FirstValid. Fails if negative"""
    @property
    def last_valid(self) -> UInt64:
        """round number"""
    @property
    def note(self) -> Bytes:
        """Any data up to 1024 bytes"""
    @property
    def lease(self) -> Bytes:
        """32 byte lease value"""
    @property
    def type_bytes(self) -> Bytes:
        """Transaction type as bytes"""
    @property
    def type(self) -> TransactionType:
        """Transaction type as integer"""
    @property
    def group_index(self) -> UInt64:
        """Position of this transaction within an atomic transaction group.
        A stand-alone transaction is implicitly element 0 in a group of 1"""
    @property
    def txn_id(self) -> Bytes:
        """The computed ID for this transaction. 32 bytes."""
    @property
    def rekey_to(self) -> Account:
        """32 byte Sender's new AuthAddr"""

class KeyRegistrationInnerTransaction:
    """Key Registration inner transaction"""
    @property
    def vote_key(self) -> Bytes:
        """32 byte address"""
    @property
    def selection_key(self) -> Bytes:
        """32 byte address"""
    @property
    def vote_first(self) -> UInt64:
        """The first round that the participation key is valid."""
    @property
    def vote_last(self) -> UInt64:
        """The last round that the participation key is valid."""
    @property
    def vote_key_dilution(self) -> UInt64:
        """Dilution for the 2-level participation key"""
    @property
    def non_participation(self) -> bool:
        """Marks an account nonparticipating for rewards"""
    @property
    def state_proof_key(self) -> Bytes:
        """64 byte state proof public key"""
    @property
    def sender(self) -> Account:
        """32 byte address"""
    @property
    def fee(self) -> UInt64:
        """microalgos"""
    @property
    def first_valid(self) -> UInt64:
        """round number"""
    @property
    def first_valid_time(self) -> UInt64:
        """UNIX timestamp of block before txn.FirstValid. Fails if negative"""
    @property
    def last_valid(self) -> UInt64:
        """round number"""
    @property
    def note(self) -> Bytes:
        """Any data up to 1024 bytes"""
    @property
    def lease(self) -> Bytes:
        """32 byte lease value"""
    @property
    def type_bytes(self) -> Bytes:
        """Transaction type as bytes"""
    @property
    def type(self) -> TransactionType:
        """Transaction type as integer"""
    @property
    def group_index(self) -> UInt64:
        """Position of this transaction within an atomic transaction group.
        A stand-alone transaction is implicitly element 0 in a group of 1"""
    @property
    def txn_id(self) -> Bytes:
        """The computed ID for this transaction. 32 bytes."""
    @property
    def rekey_to(self) -> Account:
        """32 byte Sender's new AuthAddr"""

class AssetConfigInnerTransaction:
    """Asset Config inner transaction"""
    @property
    def config_asset(self) -> Asset:
        """Asset ID in asset config transaction"""
    @property
    def total(self) -> UInt64:
        """Total number of units of this asset created"""
    @property
    def decimals(self) -> UInt64:
        """Number of digits to display after the decimal place when displaying the asset"""
    @property
    def default_frozen(self) -> bool:
        """Whether the asset's slots are frozen by default or not, 0 or 1"""
    @property
    def unit_name(self) -> Bytes:
        """Unit name of the asset"""
    @property
    def asset_name(self) -> Bytes:
        """The asset name"""
    @property
    def url(self) -> Bytes:
        """URL"""
    @property
    def metadata_hash(self) -> Bytes:
        """32 byte commitment to unspecified asset metadata"""
    @property
    def manager(self) -> Account:
        """32 byte address"""
    @property
    def reserve(self) -> Account:
        """32 byte address"""
    @property
    def freeze(self) -> Account:
        """32 byte address"""
    @property
    def clawback(self) -> Account:
        """32 byte address"""
    @property
    def created_asset(self) -> Asset:
        """Asset ID allocated by the creation of an ASA"""
    @property
    def sender(self) -> Account:
        """32 byte address"""
    @property
    def fee(self) -> UInt64:
        """microalgos"""
    @property
    def first_valid(self) -> UInt64:
        """round number"""
    @property
    def first_valid_time(self) -> UInt64:
        """UNIX timestamp of block before txn.FirstValid. Fails if negative"""
    @property
    def last_valid(self) -> UInt64:
        """round number"""
    @property
    def note(self) -> Bytes:
        """Any data up to 1024 bytes"""
    @property
    def lease(self) -> Bytes:
        """32 byte lease value"""
    @property
    def type_bytes(self) -> Bytes:
        """Transaction type as bytes"""
    @property
    def type(self) -> TransactionType:
        """Transaction type as integer"""
    @property
    def group_index(self) -> UInt64:
        """Position of this transaction within an atomic transaction group.
        A stand-alone transaction is implicitly element 0 in a group of 1"""
    @property
    def txn_id(self) -> Bytes:
        """The computed ID for this transaction. 32 bytes."""
    @property
    def rekey_to(self) -> Account:
        """32 byte Sender's new AuthAddr"""

class AssetTransferInnerTransaction:
    """Asset Transfer inner transaction"""
    @property
    def xfer_asset(self) -> Asset:
        """Asset ID"""
    @property
    def asset_amount(self) -> UInt64:
        """value in Asset's units"""
    @property
    def asset_sender(self) -> Account:
        """32 byte address. Source of assets if Sender is the Asset's Clawback address."""
    @property
    def asset_receiver(self) -> Account:
        """32 byte address"""
    @property
    def asset_close_to(self) -> Account:
        """32 byte address"""
    @property
    def sender(self) -> Account:
        """32 byte address"""
    @property
    def fee(self) -> UInt64:
        """microalgos"""
    @property
    def first_valid(self) -> UInt64:
        """round number"""
    @property
    def first_valid_time(self) -> UInt64:
        """UNIX timestamp of block before txn.FirstValid. Fails if negative"""
    @property
    def last_valid(self) -> UInt64:
        """round number"""
    @property
    def note(self) -> Bytes:
        """Any data up to 1024 bytes"""
    @property
    def lease(self) -> Bytes:
        """32 byte lease value"""
    @property
    def type_bytes(self) -> Bytes:
        """Transaction type as bytes"""
    @property
    def type(self) -> TransactionType:
        """Transaction type as integer"""
    @property
    def group_index(self) -> UInt64:
        """Position of this transaction within an atomic transaction group.
        A stand-alone transaction is implicitly element 0 in a group of 1"""
    @property
    def txn_id(self) -> Bytes:
        """The computed ID for this transaction. 32 bytes."""
    @property
    def rekey_to(self) -> Account:
        """32 byte Sender's new AuthAddr"""

class AssetFreezeInnerTransaction:
    """Asset Freeze inner transaction"""
    @property
    def freeze_asset(self) -> Asset:
        """Asset ID being frozen or un-frozen"""
    @property
    def freeze_account(self) -> Account:
        """32 byte address of the account whose asset slot is being frozen or un-frozen"""
    @property
    def frozen(self) -> bool:
        """The new frozen value, 0 or 1"""
    @property
    def sender(self) -> Account:
        """32 byte address"""
    @property
    def fee(self) -> UInt64:
        """microalgos"""
    @property
    def first_valid(self) -> UInt64:
        """round number"""
    @property
    def first_valid_time(self) -> UInt64:
        """UNIX timestamp of block before txn.FirstValid. Fails if negative"""
    @property
    def last_valid(self) -> UInt64:
        """round number"""
    @property
    def note(self) -> Bytes:
        """Any data up to 1024 bytes"""
    @property
    def lease(self) -> Bytes:
        """32 byte lease value"""
    @property
    def type_bytes(self) -> Bytes:
        """Transaction type as bytes"""
    @property
    def type(self) -> TransactionType:
        """Transaction type as integer"""
    @property
    def group_index(self) -> UInt64:
        """Position of this transaction within an atomic transaction group.
        A stand-alone transaction is implicitly element 0 in a group of 1"""
    @property
    def txn_id(self) -> Bytes:
        """The computed ID for this transaction. 32 bytes."""
    @property
    def rekey_to(self) -> Account:
        """32 byte Sender's new AuthAddr"""

class ApplicationCallInnerTransaction:
    """Application Call inner transaction"""
    @property
    def app_id(self) -> Application:
        """ApplicationID from ApplicationCall transaction"""
    @property
    def on_completion(self) -> OnCompleteAction:
        """ApplicationCall transaction on completion action"""
    @property
    def num_app_args(self) -> UInt64:
        """Number of ApplicationArgs"""
    @property
    def num_accounts(self) -> UInt64:
        """Number of ApplicationArgs"""
    @property
    def approval_program(self) -> Bytes:
        """Approval program"""
    @property
    def clear_state_program(self) -> Bytes:
        """Clear State program"""
    @property
    def num_assets(self) -> UInt64:
        """Number of Assets"""
    @property
    def num_apps(self) -> UInt64:
        """Number of Applications"""
    @property
    def global_num_uint(self) -> UInt64:
        """Number of global state integers in ApplicationCall"""
    @property
    def global_num_bytes(self) -> UInt64:
        """Number of global state byteslices in ApplicationCall"""
    @property
    def local_num_uint(self) -> UInt64:
        """Number of local state integers in ApplicationCall"""
    @property
    def local_num_bytes(self) -> UInt64:
        """Number of local state byteslices in ApplicationCall"""
    @property
    def extra_program_pages(self) -> UInt64:
        """Number of additional pages for each of the application's approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program."""
    @property
    def last_log(self) -> Bytes:
        """The last message emitted. Empty bytes if none were emitted. Application mode only"""
    def logs(self, index: UInt64 | int) -> Bytes:
        """Log messages emitted by an application call"""
    @property
    def num_logs(self) -> UInt64:
        """Number of logs"""
    @property
    def created_app(self) -> Application:
        """ApplicationID allocated by the creation of an application"""
    @property
    def num_approval_program_pages(self) -> UInt64:
        """Number of Approval Program pages"""
    @property
    def num_clear_state_program_pages(self) -> UInt64:
        """Number of Clear State Program pages"""
    def app_args(self, index: UInt64 | int, /) -> Bytes:
        """Arguments passed to the application in the ApplicationCall transaction"""
    def accounts(self, index: UInt64 | int, /) -> Account:
        """Accounts listed in the ApplicationCall transaction"""
    def assets(self, index: UInt64 | int, /) -> Asset:
        """Foreign Assets listed in the ApplicationCall transaction"""
    def apps(self, index: UInt64 | int, /) -> Application:
        """Foreign Apps listed in the ApplicationCall transaction"""
    def approval_program_pages(self, index: UInt64 | int, /) -> Bytes:
        """Approval Program as an array of pages"""
    def clear_state_program_pages(self, index: UInt64 | int, /) -> Bytes:
        """Clear State Program as an array of pages"""
    @property
    def sender(self) -> Account:
        """32 byte address"""
    @property
    def fee(self) -> UInt64:
        """microalgos"""
    @property
    def first_valid(self) -> UInt64:
        """round number"""
    @property
    def first_valid_time(self) -> UInt64:
        """UNIX timestamp of block before txn.FirstValid. Fails if negative"""
    @property
    def last_valid(self) -> UInt64:
        """round number"""
    @property
    def note(self) -> Bytes:
        """Any data up to 1024 bytes"""
    @property
    def lease(self) -> Bytes:
        """32 byte lease value"""
    @property
    def type_bytes(self) -> Bytes:
        """Transaction type as bytes"""
    @property
    def type(self) -> TransactionType:
        """Transaction type as integer"""
    @property
    def group_index(self) -> UInt64:
        """Position of this transaction within an atomic transaction group.
        A stand-alone transaction is implicitly element 0 in a group of 1"""
    @property
    def txn_id(self) -> Bytes:
        """The computed ID for this transaction. 32 bytes."""
    @property
    def rekey_to(self) -> Account:
        """32 byte Sender's new AuthAddr"""

class InnerTransactionResult(
    PaymentInnerTransaction,
    KeyRegistrationInnerTransaction,
    AssetConfigInnerTransaction,
    AssetTransferInnerTransaction,
    AssetFreezeInnerTransaction,
    ApplicationCallInnerTransaction,
):
    """An inner transaction of any type"""
    @property
    def sender(self) -> Account:
        """32 byte address"""
    @property
    def fee(self) -> UInt64:
        """microalgos"""
    @property
    def first_valid(self) -> UInt64:
        """round number"""
    @property
    def first_valid_time(self) -> UInt64:
        """UNIX timestamp of block before txn.FirstValid. Fails if negative"""
    @property
    def last_valid(self) -> UInt64:
        """round number"""
    @property
    def note(self) -> Bytes:
        """Any data up to 1024 bytes"""
    @property
    def lease(self) -> Bytes:
        """32 byte lease value"""
    @property
    def type_bytes(self) -> Bytes:
        """Transaction type as bytes"""
    @property
    def type(self) -> TransactionType:
        """Transaction type as integer"""
    @property
    def group_index(self) -> UInt64:
        """Position of this transaction within an atomic transaction group.
        A stand-alone transaction is implicitly element 0 in a group of 1"""
    @property
    def txn_id(self) -> Bytes:
        """The computed ID for this transaction. 32 bytes."""
    @property
    def rekey_to(self) -> Account:
        """32 byte Sender's new AuthAddr"""

_TResult_co = typing.TypeVar(
    "_TResult_co",
    covariant=True,
)

class _InnerTransaction(typing.Protocol[_TResult_co]):
    def submit(self) -> _TResult_co:
        """Submits inner transaction parameters and returns the resulting inner transaction"""

    def copy(self) -> typing.Self:
        """Copies a set of inner transaction parameters"""

class InnerTransaction(_InnerTransaction[InnerTransactionResult]):
    """Creates a set of fields used to submit an inner transaction of any type"""

    def __init__(
        self,
        *,
        type: TransactionType,  # noqa: A002
        ## payment
        receiver: Account | str = ...,
        amount: UInt64 | int = ...,
        close_remainder_to: Account | str = ...,
        ## key registration
        vote_key: Bytes | bytes = ...,
        selection_key: Bytes | bytes = ...,
        vote_first: UInt64 | int = ...,
        vote_last: UInt64 | int = ...,
        vote_key_dilution: UInt64 | int = ...,
        non_participation: UInt64 | int | bool = ...,
        state_proof_key: Bytes | bytes = ...,
        ## asset config
        config_asset: Asset | UInt64 | int = ...,
        total: UInt64 | int = ...,
        unit_name: String | Bytes | str | bytes = ...,
        asset_name: String | Bytes | str | bytes = ...,
        decimals: UInt64 | int = ...,
        default_frozen: bool = ...,
        url: String | Bytes | bytes | str = ...,
        metadata_hash: Bytes | bytes = ...,
        manager: Account | str = ...,
        reserve: Account | str = ...,
        freeze: Account | str = ...,
        clawback: Account | str = ...,
        ## asset transfer
        xfer_asset: Asset | UInt64 | int = ...,
        asset_amount: UInt64 | int = ...,
        asset_sender: Account | str = ...,
        asset_receiver: Account | str = ...,
        asset_close_to: Account | str = ...,
        ## asset freeze
        freeze_asset: Asset | UInt64 | int = ...,
        freeze_account: Account | str = ...,
        frozen: bool = ...,
        ## application call
        app_id: Application | UInt64 | int = ...,
        approval_program: Bytes | bytes | tuple[Bytes, ...] = ...,
        clear_state_program: Bytes | bytes | tuple[Bytes, ...] = ...,
        on_completion: OnCompleteAction | UInt64 | int = ...,
        global_num_uint: UInt64 | int = ...,
        global_num_bytes: UInt64 | int = ...,
        local_num_uint: UInt64 | int = ...,
        local_num_bytes: UInt64 | int = ...,
        extra_program_pages: UInt64 | int = ...,
        app_args: tuple[object, ...] = ...,
        accounts: tuple[Account, ...] = ...,
        assets: tuple[Asset, ...] = ...,
        apps: tuple[Application, ...] = ...,
        ## shared
        sender: Account | str = ...,
        fee: UInt64 | int = 0,
        note: String | Bytes | str | bytes = ...,
        rekey_to: Account | str = ...,
    ): ...
    def set(
        self,
        *,
        type: TransactionType = ...,  # noqa: A002
        ## payment
        receiver: Account | str = ...,
        amount: UInt64 | int = ...,
        close_remainder_to: Account | str = ...,
        ## key registration
        vote_key: Bytes | bytes = ...,
        selection_key: Bytes | bytes = ...,
        vote_first: UInt64 | int = ...,
        vote_last: UInt64 | int = ...,
        vote_key_dilution: UInt64 | int = ...,
        non_participation: UInt64 | int | bool = ...,
        state_proof_key: Bytes | bytes = ...,
        ## asset config
        config_asset: Asset | UInt64 | int = ...,
        total: UInt64 | int = ...,
        unit_name: String | Bytes | str | bytes = ...,
        asset_name: String | Bytes | str | bytes = ...,
        decimals: UInt64 | int = ...,
        default_frozen: bool = ...,
        url: String | Bytes | bytes | str = ...,
        metadata_hash: Bytes | bytes = ...,
        manager: Account | str = ...,
        reserve: Account | str = ...,
        freeze: Account | str = ...,
        clawback: Account | str = ...,
        ## asset transfer
        xfer_asset: Asset | UInt64 | int = ...,
        asset_amount: UInt64 | int = ...,
        asset_sender: Account | str = ...,
        asset_receiver: Account | str = ...,
        asset_close_to: Account | str = ...,
        ## asset freeze
        freeze_asset: Asset | UInt64 | int = ...,
        freeze_account: Account | str = ...,
        frozen: bool = ...,
        ## application call
        app_id: Application | UInt64 | int = ...,
        approval_program: Bytes | bytes | tuple[Bytes, ...] = ...,
        clear_state_program: Bytes | bytes | tuple[Bytes, ...] = ...,
        on_completion: OnCompleteAction | UInt64 | int = ...,
        global_num_uint: UInt64 | int = ...,
        global_num_bytes: UInt64 | int = ...,
        local_num_uint: UInt64 | int = ...,
        local_num_bytes: UInt64 | int = ...,
        extra_program_pages: UInt64 | int = ...,
        app_args: tuple[object, ...] = ...,
        accounts: tuple[Account, ...] = ...,
        assets: tuple[Asset, ...] = ...,
        apps: tuple[Application, ...] = ...,
        ## shared
        sender: Account | str = ...,
        fee: UInt64 | int = 0,
        note: String | Bytes | str | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None:
        """Updates inner transaction parameter values"""

class Payment(_InnerTransaction[PaymentInnerTransaction]):
    """Creates a set of fields used to submit a Payment inner transaction"""

    def __init__(
        self,
        *,
        receiver: Account | str,
        amount: UInt64 | int = ...,
        close_remainder_to: Account | str = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = 0,
        note: String | Bytes | str | bytes = ...,
        rekey_to: Account | str = ...,
    ): ...
    def set(
        self,
        *,
        receiver: Account | str = ...,
        amount: UInt64 | int = ...,
        close_remainder_to: Account | str = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = 0,
        note: String | Bytes | str | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None:
        """Updates inner transaction parameter values"""

class KeyRegistration(_InnerTransaction[KeyRegistrationInnerTransaction]):
    """Creates a set of fields used to submit a Key Registration inner transaction"""

    def __init__(
        self,
        *,
        vote_key: Bytes | bytes,
        selection_key: Bytes | bytes,
        vote_first: UInt64 | int,
        vote_last: UInt64 | int,
        vote_key_dilution: UInt64 | int,
        non_participation: UInt64 | int | bool = ...,
        state_proof_key: Bytes | bytes = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = 0,
        note: String | Bytes | str | bytes = ...,
        rekey_to: Account | str = ...,
    ): ...
    def set(
        self,
        *,
        vote_key: Bytes | bytes = ...,
        selection_key: Bytes | bytes = ...,
        vote_first: UInt64 | int = ...,
        vote_last: UInt64 | int = ...,
        vote_key_dilution: UInt64 | int = ...,
        non_participation: UInt64 | int | bool = ...,
        state_proof_key: Bytes | bytes = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = 0,
        note: String | Bytes | str | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None:
        """Updates inner transaction parameter values"""

class AssetConfig(_InnerTransaction[AssetConfigInnerTransaction]):
    """Creates a set of fields used to submit an Asset Config inner transaction"""

    def __init__(
        self,
        *,
        config_asset: Asset | UInt64 | int = ...,
        total: UInt64 | int = ...,
        unit_name: String | Bytes | str | bytes = ...,
        asset_name: String | Bytes | str | bytes = ...,
        decimals: UInt64 | int = ...,
        default_frozen: bool = ...,
        url: String | Bytes | str | bytes = ...,
        metadata_hash: Bytes | bytes = ...,
        manager: Account | str = ...,
        reserve: Account | str = ...,
        freeze: Account | str = ...,
        clawback: Account | str = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = 0,
        note: String | Bytes | str | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None: ...
    def set(
        self,
        *,
        config_asset: Asset | UInt64 | int = ...,
        total: UInt64 | int = ...,
        unit_name: String | Bytes | str | bytes = ...,
        asset_name: String | Bytes | str | bytes = ...,
        decimals: UInt64 | int = ...,
        default_frozen: bool = ...,
        url: String | Bytes | str | bytes = ...,
        metadata_hash: Bytes | bytes = ...,
        manager: Account | str = ...,
        reserve: Account | str = ...,
        freeze: Account | str = ...,
        clawback: Account | str = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = 0,
        note: String | Bytes | str | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None:
        """Updates inner transaction parameter values"""

class AssetTransfer(_InnerTransaction[AssetTransferInnerTransaction]):
    """Creates a set of fields used to submit an Asset Transfer inner transaction"""

    def __init__(
        self,
        *,
        xfer_asset: Asset | UInt64 | int,
        asset_receiver: Account | str,
        asset_amount: UInt64 | int = ...,
        asset_sender: Account | str = ...,
        asset_close_to: Account | str = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = 0,
        note: String | Bytes | str | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None: ...
    def set(
        self,
        *,
        xfer_asset: Asset | UInt64 | int = ...,
        asset_amount: UInt64 | int = ...,
        asset_sender: Account | str = ...,
        asset_receiver: Account | str = ...,
        asset_close_to: Account | str = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = 0,
        note: String | Bytes | str | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None:
        """Updates transaction parameter values"""

class AssetFreeze(_InnerTransaction[AssetFreezeInnerTransaction]):
    """Creates a set of fields used to submit a Asset Freeze inner transaction"""

    def __init__(
        self,
        *,
        freeze_asset: Asset | UInt64 | int,
        freeze_account: Account | str,
        frozen: bool,
        sender: Account | str = ...,
        fee: UInt64 | int = 0,
        note: String | Bytes | str | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None: ...
    def set(
        self,
        *,
        freeze_asset: Asset | UInt64 | int = ...,
        freeze_account: Account | str = ...,
        frozen: bool = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = 0,
        note: String | Bytes | str | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None:
        """Updates inner transaction parameter values"""

class ApplicationCall(_InnerTransaction[ApplicationCallInnerTransaction]):
    """Creates a set of fields used to submit an Application Call inner transaction"""

    def __init__(
        self,
        *,
        app_id: Application | UInt64 | int = ...,
        approval_program: Bytes | bytes | tuple[Bytes, ...] = ...,
        clear_state_program: Bytes | bytes | tuple[Bytes, ...] = ...,
        on_completion: OnCompleteAction | UInt64 | int = ...,
        global_num_uint: UInt64 | int = ...,
        global_num_bytes: UInt64 | int = ...,
        local_num_uint: UInt64 | int = ...,
        local_num_bytes: UInt64 | int = ...,
        extra_program_pages: UInt64 | int = ...,
        app_args: tuple[object, ...] = ...,
        accounts: tuple[Account, ...] = ...,
        assets: tuple[Asset, ...] = ...,
        apps: tuple[Application, ...] = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = 0,
        note: String | Bytes | str | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None: ...
    def set(
        self,
        *,
        app_id: Application | UInt64 | int = ...,
        approval_program: Bytes | bytes | tuple[Bytes, ...] = ...,
        clear_state_program: Bytes | bytes | tuple[Bytes, ...] = ...,
        on_completion: OnCompleteAction | UInt64 | int = ...,
        global_num_uint: UInt64 | int = ...,
        global_num_bytes: UInt64 | int = ...,
        local_num_uint: UInt64 | int = ...,
        local_num_bytes: UInt64 | int = ...,
        extra_program_pages: UInt64 | int = ...,
        app_args: tuple[object, ...] = ...,
        accounts: tuple[Account, ...] = ...,
        assets: tuple[Asset, ...] = ...,
        apps: tuple[Application, ...] = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = 0,
        note: String | Bytes | str | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None:
        """Updates inner transaction parameter values"""

_T1 = typing.TypeVar("_T1")
_T2 = typing.TypeVar("_T2")
_T3 = typing.TypeVar("_T3")
_T4 = typing.TypeVar("_T4")
_T5 = typing.TypeVar("_T5")
_T6 = typing.TypeVar("_T6")
_T7 = typing.TypeVar("_T7")
_T8 = typing.TypeVar("_T8")
_T9 = typing.TypeVar("_T9")
_T10 = typing.TypeVar("_T10")
_T11 = typing.TypeVar("_T11")
_T12 = typing.TypeVar("_T12")
_T13 = typing.TypeVar("_T13")
_T14 = typing.TypeVar("_T14")
_T15 = typing.TypeVar("_T15")
_T16 = typing.TypeVar("_T16")

@typing.overload
def submit_txns(
    _t1: _InnerTransaction[_T1], _t2: _InnerTransaction[_T2], /
) -> tuple[_T1, _T2]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransaction[_T1],
    _t2: _InnerTransaction[_T2],
    _t3: _InnerTransaction[_T3],
    /,
) -> tuple[_T1, _T2, _T3]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransaction[_T1],
    _t2: _InnerTransaction[_T2],
    _t3: _InnerTransaction[_T3],
    _t4: _InnerTransaction[_T4],
    /,
) -> tuple[_T1, _T2, _T3, _T4]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransaction[_T1],
    _t2: _InnerTransaction[_T2],
    _t3: _InnerTransaction[_T3],
    _t4: _InnerTransaction[_T4],
    _t5: _InnerTransaction[_T5],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransaction[_T1],
    _t2: _InnerTransaction[_T2],
    _t3: _InnerTransaction[_T3],
    _t4: _InnerTransaction[_T4],
    _t5: _InnerTransaction[_T5],
    _t6: _InnerTransaction[_T6],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransaction[_T1],
    _t2: _InnerTransaction[_T2],
    _t3: _InnerTransaction[_T3],
    _t4: _InnerTransaction[_T4],
    _t5: _InnerTransaction[_T5],
    _t6: _InnerTransaction[_T6],
    _t7: _InnerTransaction[_T7],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransaction[_T1],
    _t2: _InnerTransaction[_T2],
    _t3: _InnerTransaction[_T3],
    _t4: _InnerTransaction[_T4],
    _t5: _InnerTransaction[_T5],
    _t6: _InnerTransaction[_T6],
    _t7: _InnerTransaction[_T7],
    _t8: _InnerTransaction[_T8],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransaction[_T1],
    _t2: _InnerTransaction[_T2],
    _t3: _InnerTransaction[_T3],
    _t4: _InnerTransaction[_T4],
    _t5: _InnerTransaction[_T5],
    _t6: _InnerTransaction[_T6],
    _t7: _InnerTransaction[_T7],
    _t8: _InnerTransaction[_T8],
    _t9: _InnerTransaction[_T9],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8, _T9]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransaction[_T1],
    _t2: _InnerTransaction[_T2],
    _t3: _InnerTransaction[_T3],
    _t4: _InnerTransaction[_T4],
    _t5: _InnerTransaction[_T5],
    _t6: _InnerTransaction[_T6],
    _t7: _InnerTransaction[_T7],
    _t8: _InnerTransaction[_T8],
    _t9: _InnerTransaction[_T9],
    _t10: _InnerTransaction[_T10],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8, _T9, _T10]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransaction[_T1],
    _t2: _InnerTransaction[_T2],
    _t3: _InnerTransaction[_T3],
    _t4: _InnerTransaction[_T4],
    _t5: _InnerTransaction[_T5],
    _t6: _InnerTransaction[_T6],
    _t7: _InnerTransaction[_T7],
    _t8: _InnerTransaction[_T8],
    _t9: _InnerTransaction[_T9],
    _t10: _InnerTransaction[_T10],
    _t11: _InnerTransaction[_T11],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8, _T9, _T10, _T11]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransaction[_T1],
    _t2: _InnerTransaction[_T2],
    _t3: _InnerTransaction[_T3],
    _t4: _InnerTransaction[_T4],
    _t5: _InnerTransaction[_T5],
    _t6: _InnerTransaction[_T6],
    _t7: _InnerTransaction[_T7],
    _t8: _InnerTransaction[_T8],
    _t9: _InnerTransaction[_T9],
    _t10: _InnerTransaction[_T10],
    _t11: _InnerTransaction[_T11],
    _t12: _InnerTransaction[_T12],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8, _T9, _T10, _T11, _T12]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransaction[_T1],
    _t2: _InnerTransaction[_T2],
    _t3: _InnerTransaction[_T3],
    _t4: _InnerTransaction[_T4],
    _t5: _InnerTransaction[_T5],
    _t6: _InnerTransaction[_T6],
    _t7: _InnerTransaction[_T7],
    _t8: _InnerTransaction[_T8],
    _t9: _InnerTransaction[_T9],
    _t10: _InnerTransaction[_T10],
    _t11: _InnerTransaction[_T11],
    _t12: _InnerTransaction[_T12],
    _t13: _InnerTransaction[_T13],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8, _T9, _T10, _T11, _T12, _T13]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransaction[_T1],
    _t2: _InnerTransaction[_T2],
    _t3: _InnerTransaction[_T3],
    _t4: _InnerTransaction[_T4],
    _t5: _InnerTransaction[_T5],
    _t6: _InnerTransaction[_T6],
    _t7: _InnerTransaction[_T7],
    _t8: _InnerTransaction[_T8],
    _t9: _InnerTransaction[_T9],
    _t10: _InnerTransaction[_T10],
    _t11: _InnerTransaction[_T11],
    _t12: _InnerTransaction[_T12],
    _t13: _InnerTransaction[_T13],
    _t14: _InnerTransaction[_T14],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8, _T9, _T10, _T11, _T12, _T13, _T14]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransaction[_T1],
    _t2: _InnerTransaction[_T2],
    _t3: _InnerTransaction[_T3],
    _t4: _InnerTransaction[_T4],
    _t5: _InnerTransaction[_T5],
    _t6: _InnerTransaction[_T6],
    _t7: _InnerTransaction[_T7],
    _t8: _InnerTransaction[_T8],
    _t9: _InnerTransaction[_T9],
    _t10: _InnerTransaction[_T10],
    _t11: _InnerTransaction[_T11],
    _t12: _InnerTransaction[_T12],
    _t13: _InnerTransaction[_T13],
    _t14: _InnerTransaction[_T14],
    _t15: _InnerTransaction[_T15],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8, _T9, _T10, _T11, _T12, _T13, _T14, _T15]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransaction[_T1],
    _t2: _InnerTransaction[_T2],
    _t3: _InnerTransaction[_T3],
    _t4: _InnerTransaction[_T4],
    _t5: _InnerTransaction[_T5],
    _t6: _InnerTransaction[_T6],
    _t7: _InnerTransaction[_T7],
    _t8: _InnerTransaction[_T8],
    _t9: _InnerTransaction[_T9],
    _t10: _InnerTransaction[_T10],
    _t11: _InnerTransaction[_T11],
    _t12: _InnerTransaction[_T12],
    _t13: _InnerTransaction[_T13],
    _t14: _InnerTransaction[_T14],
    _t15: _InnerTransaction[_T15],
    _t16: _InnerTransaction[_T16],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8, _T9, _T10, _T11, _T12, _T13, _T14, _T15, _T16]:
    """Submits a group of up to 16 inner transactions parameters

    :returns: A tuple of the resulting inner transactions"""
