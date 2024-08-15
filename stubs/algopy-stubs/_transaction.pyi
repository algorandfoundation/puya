import typing

from algopy import Account, Application, Asset, Bytes, OnCompleteAction, TransactionType, UInt64

class _TransactionBaseProtocol(typing.Protocol):
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

class _PaymentProtocol(typing.Protocol):
    @property
    def receiver(self) -> Account:
        """32 byte address"""

    @property
    def amount(self) -> UInt64:
        """microalgos"""

    @property
    def close_remainder_to(self) -> Account:
        """32 byte address"""

class _KeyRegistrationProtocol(typing.Protocol):
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

class _AssetConfigProtocol(typing.Protocol):
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

class _AssetTransferProtocol(typing.Protocol):
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

class _AssetFreezeProtocol(typing.Protocol):
    @property
    def freeze_asset(self) -> Asset:
        """Asset ID being frozen or un-frozen"""

    @property
    def freeze_account(self) -> Account:
        """32 byte address of the account whose asset slot is being frozen or un-frozen"""

    @property
    def frozen(self) -> bool:
        """The new frozen value, 0 or 1"""

class _ApplicationProtocol(typing.Protocol):
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
    # TODO: make the following sequences instead?
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
