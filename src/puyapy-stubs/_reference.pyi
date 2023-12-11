import typing as t

from puyapy import Bytes, UInt64

class Account:
    def __init__(self, address: t.LiteralString):
        """
        `value` should be a 58 character base32 string,
         ie a base32 string-encoded 32 bytes public key + 4 bytes checksum
        """
    def __eq__(self, other: Account | t.LiteralString) -> bool: ...  # type: ignore[override]
    def __ne__(self, other: Account | t.LiteralString) -> bool: ...  # type: ignore[override]
    # truthiness
    def __bool__(self) -> bool: ...  # returns True iff not equal to the zero address
    @property
    def bytes(self) -> Bytes:
        """Get the byte[] backing this value. Note that Bytes is immutable"""
    @staticmethod
    def from_bytes(value: Bytes) -> Account:
        """no validation happens here wrt length"""
    @property
    def balance(self) -> UInt64:
        """Account balance in microalgos"""
    @property
    def min_balance(self) -> UInt64:
        """Minimum required balance for account, in microalgos"""
    @property
    def auth_address(self) -> Account:
        """Address the account is rekeyed to"""
    @property
    def total_num_uint(self) -> UInt64:
        """The total number of uint64 values allocated by this account in Global and Local States."""
    @property
    def total_num_byte_slice(self) -> Bytes:
        """The total number of byte array values allocated by this account in Global and Local States."""
    @property
    def total_extra_app_pages(self) -> UInt64:
        """The number of extra app code pages used by this account."""
    @property
    def total_apps_created(self) -> UInt64:
        """The number of existing apps created by this account."""
    @property
    def total_apps_opted_in(self) -> UInt64:
        """The number of apps this account is opted into."""
    @property
    def total_assets_created(self) -> UInt64:
        """The number of existing ASAs created by this account."""
    @property
    def total_assets(self) -> UInt64:
        """The numbers of ASAs held by this account (including ASAs this account created)."""
    @property
    def total_boxes(self) -> UInt64:
        """The number of existing boxes created by this account's app."""
    @property
    def total_box_bytes(self) -> UInt64:
        """The total number of bytes used by this account's app's box keys and values."""

class Asset:
    def __init__(self, asset_id: UInt64 | int): ...
    @property
    def asset_id(self) -> UInt64: ...
    def __eq__(self, other: Asset) -> bool: ...  # type: ignore[override]
    def __ne__(self, other: Asset) -> bool: ...  # type: ignore[override]

    # truthiness
    def __bool__(self) -> bool: ...  # returns True iff asset_id > 0
    @property
    def total(self) -> UInt64:
        """Total number of units of this asset"""
    @property
    def decimals(self) -> UInt64:
        """See AssetParams.Decimals"""
    @property
    def default_frozen(self) -> bool:
        """Frozen by default or not"""
    @property
    def unit_name(self) -> Bytes:
        """Asset unit name"""
    @property
    def name(self) -> Bytes:
        """Asset name"""
    @property
    def url(self) -> Bytes:
        """URL with additional info about the asset"""
    @property
    def metadata_hash(self) -> Bytes:
        """Arbitrary commitment"""
    @property
    def manager(self) -> Account:
        """Manager address"""
    @property
    def reserve(self) -> Account:
        """Reserve address"""
    @property
    def freeze(self) -> Account:
        """Freeze address"""
    @property
    def clawback(self) -> Account:
        """Clawback address"""
    @property
    def creator(self) -> Account:
        """Creator address"""
    def balance(self, account: Account) -> UInt64:
        """Amount of the asset unit held by this account"""
    def frozen(self, account: Account) -> bool:
        """Is the asset frozen or not"""

class Application:
    def __init__(self, application_id: UInt64 | int): ...
    @property
    def application_id(self) -> UInt64: ...
    def __eq__(self, other: Application) -> bool: ...  # type: ignore[override]
    def __ne__(self, other: Application) -> bool: ...  # type: ignore[override]

    # truthiness
    def __bool__(self) -> bool: ...  # returns True iff application_id > 0
    @property
    def approval_program(self) -> Bytes:
        """Bytecode of Approval Program"""
    @property
    def clear_state_program(self) -> Bytes:
        """Bytecode of Clear State Program"""
    @property
    def global_num_uint(self) -> UInt64:
        """Number of uint64 values allowed in Global State"""
    @property
    def global_num_byte_slice(self) -> UInt64:
        """Number of byte array values allowed in Global State"""
    @property
    def local_num_uint(self) -> UInt64:
        """Number of uint64 values allowed in Local State"""
    @property
    def local_num_byte_slice(self) -> UInt64:
        """Number of byte array values allowed in Local State"""
    @property
    def extra_program_pages(self) -> UInt64:
        """Number of Extra Program Pages of code space"""
    @property
    def creator(self) -> Account:
        """Creator address"""
    @property
    def address(self) -> Account:
        """Address for which this application has authority"""
