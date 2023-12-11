import typing

from puyapy import Account, Application, Asset, Bytes, OnCompleteAction, TransactionType, UInt64

class TransactionBase(typing.Protocol):
    def __init__(self, group_index: UInt64 | int): ...
    @property
    def sender(self) -> Account: ...
    @property
    def fee(self) -> UInt64: ...
    @property
    def first_valid(self) -> UInt64: ...
    @property
    def first_valid_time(self) -> UInt64: ...
    @property
    def last_valid(self) -> UInt64: ...
    @property
    def note(self) -> Bytes: ...
    @property
    def lease(self) -> Bytes: ...
    @property
    def type_bytes(self) -> Bytes: ...
    @property
    def type(self) -> TransactionType: ...
    @property
    def group_index(self) -> UInt64: ...
    @property
    def txn_id(self) -> Bytes: ...
    @property
    def rekey_to(self) -> Account: ...

class PaymentTransaction(TransactionBase):
    @property
    def receiver(self) -> Account: ...
    @property
    def amount(self) -> UInt64: ...
    @property
    def close_remainder_to(self) -> Account: ...

class KeyRegistrationTransaction(TransactionBase):
    @property
    def vote_key(self) -> Bytes: ...
    @property
    def selection_key(self) -> Bytes: ...
    @property
    def vote_first(self) -> UInt64: ...
    @property
    def vote_last(self) -> UInt64: ...
    @property
    def vote_key_dilution(self) -> UInt64: ...
    @property
    def non_participation(self) -> bool: ...
    @property
    def state_proof_key(self) -> Bytes: ...

class AssetConfigTransaction(TransactionBase):
    @property
    def config_asset(self) -> UInt64: ...
    @property
    def total(self) -> UInt64: ...
    @property
    def decimals(self) -> UInt64: ...
    @property
    def default_frozen(self) -> bool: ...
    @property
    def unit_name(self) -> Bytes: ...
    @property
    def asset_name(self) -> Bytes: ...
    @property
    def url(self) -> Bytes: ...
    @property
    def metadata_hash(self) -> Bytes: ...
    @property
    def manager(self) -> Account: ...
    @property
    def reserve(self) -> Account: ...
    @property
    def freeze(self) -> Account: ...
    @property
    def clawback(self) -> Account: ...

class AssetTransferTransaction(TransactionBase):
    @property
    def xfer_asset(self) -> Asset: ...
    @property
    def asset_amount(self) -> UInt64: ...
    @property
    def asset_sender(self) -> Account: ...
    @property
    def asset_receiver(self) -> Account: ...
    @property
    def asset_close_to(self) -> Account: ...

class AssetFreezeTransaction(TransactionBase):
    @property
    def freeze_asset(self) -> Asset: ...
    @property
    def freeze_account(self) -> Account: ...
    @property
    def frozen(self) -> bool: ...

class ApplicationCallTransaction(TransactionBase):
    @property
    def application_id(self) -> UInt64:
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
    def num_applications(self) -> UInt64:
        """Number of Applications"""
    @property
    def global_num_uint(self) -> UInt64:
        """Number of global state integers in ApplicationCall"""
    @property
    def global_num_byte_slice(self) -> UInt64:
        """Number of global state byteslices in ApplicationCall"""
    @property
    def local_num_uint(self) -> UInt64:
        """Number of local state integers in ApplicationCall"""
    @property
    def local_num_byte_slice(self) -> UInt64:
        """Number of local state byteslices in ApplicationCall"""
    @property
    def extra_program_pages(self) -> UInt64:
        """Number of additional pages for each of the application's approval and clear state programs. An ExtraProgramPages of 1 means 2048 more total bytes, or 1024 for each program."""
    @property
    def last_log(self) -> Bytes:
        """The last message emitted. Empty bytes if none were emitted. Application mode only"""
    @property
    def num_approval_program_pages(self) -> UInt64:
        """Number of Approval Program pages"""
    @property
    def num_clear_state_program_pages(self) -> UInt64:
        """Number of Clear State Program pages"""
    # TODO: make the following sequences instead?
    def application_args(self, index: UInt64 | int) -> Bytes:
        """Arguments passed to the application in the ApplicationCall transaction"""
    def accounts(self, index: UInt64 | int) -> Account:
        """Accounts listed in the ApplicationCall transaction"""
    def assets(self, index: UInt64 | int) -> Asset:
        """Foreign Assets listed in the ApplicationCall transaction"""
    def applications(self, index: UInt64 | int) -> Application:
        """Foreign Apps listed in the ApplicationCall transaction"""
    def approval_program_pages(self, index: UInt64 | int) -> Bytes:
        """Approval Program as an array of pages"""
    def clear_state_program_pages(self, index: UInt64 | int) -> Bytes:
        """Clear State Program as an array of pages"""

# TODO: inner transactions
# 58	Logs	[]byte	v5	Log messages emitted by an application call (only with itxn in v5). Application mode only
# 59	NumLogs	uint64	v5	Number of Logs (only with itxn in v5). Application mode only
# 60	CreatedAssetID	uint64	v5	Asset ID allocated by the creation of an ASA (only with itxn in v5). Application mode only
# 61	CreatedApplicationID	uint64	v5	ApplicationID allocated by the creation of an application (only with itxn in v5). Application mode only
