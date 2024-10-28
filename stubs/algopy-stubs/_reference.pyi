import typing
from algopy import Bytes, BytesBacked, UInt64

@typing.final
class Account(BytesBacked):
    """An Account on the Algorand network.

    Note: must be an available resource to access properties other than `bytes`
    """

    __match_value__: str
    __match_args__ = ("__match_value__",)
    def __init__(self, value: str | Bytes = ..., /):
        """
        If `value` is a string, it should be a 58 character base32 string,
        ie a base32 string-encoded 32 bytes public key + 4 bytes checksum.
        If `value` is a Bytes, it's length checked to be 32 bytes - to avoid this
        check, use `Address.from_bytes(...)` instead.
        Defaults to the zero-address.
        """

    def __eq__(self, other: Account | str) -> bool:  # type: ignore[override]
        """Account equality is determined by the address of another `Account` or `str`"""

    def __ne__(self, other: Account | str) -> bool:  # type: ignore[override]
        """Account equality is determined by the address of another `Account` or `str`"""
    # truthiness
    def __bool__(self) -> bool:
        """Returns `True` if not equal to the zero-address"""

    @property
    def balance(self) -> UInt64:
        """Account balance in microalgos

        ```{note}
        Account must be an available resource
        ```
        """

    @property
    def min_balance(self) -> UInt64:
        """Minimum required balance for account, in microalgos

        ```{note}
        Account must be an available resource
        ```
        """

    @property
    def auth_address(self) -> Account:
        """Address the account is rekeyed to

        ```{note}
        Account must be an available resource
        ```
        """

    @property
    def total_num_uint(self) -> UInt64:
        """The total number of uint64 values allocated by this account in Global and Local States.

        ```{note}
        Account must be an available resource
        ```
        """

    @property
    def total_num_byte_slice(self) -> UInt64:
        """The total number of byte array values allocated by this account in Global and Local States.

        ```{note}
        Account must be an available resource
        ```
        """

    @property
    def total_extra_app_pages(self) -> UInt64:
        """The number of extra app code pages used by this account.

        ```{note}
        Account must be an available resource
        ```
        """

    @property
    def total_apps_created(self) -> UInt64:
        """The number of existing apps created by this account.

        ```{note}
        Account must be an available resource
        ```
        """

    @property
    def total_apps_opted_in(self) -> UInt64:
        """The number of apps this account is opted into.

        ```{note}
        Account must be an available resource
        ```
        """

    @property
    def total_assets_created(self) -> UInt64:
        """The number of existing ASAs created by this account.

        ```{note}
        Account must be an available resource
        ```
        """

    @property
    def total_assets(self) -> UInt64:
        """The numbers of ASAs held by this account (including ASAs this account created).

        ```{note}
        Account must be an available resource
        ```
        """

    @property
    def total_boxes(self) -> UInt64:
        """The number of existing boxes created by this account's app.

        ```{note}
        Account must be an available resource
        ```
        """

    @property
    def total_box_bytes(self) -> UInt64:
        """The total number of bytes used by this account's app's box keys and values.

        ```{note}
        Account must be an available resource
        ```
        """

    def is_opted_in(self, asset_or_app: Asset | Application, /) -> bool:
        """Returns true if this account is opted in to the specified Asset or Application.

        ```{note}
        Account and Asset/Application must be an available resource
        ```
        """

@typing.final
class Asset:
    """An Asset on the Algorand network."""

    def __init__(self, asset_id: UInt64 | int = 0, /):
        """Initialized with the id of an asset. Defaults to zero (an invalid ID)."""

    @property
    def id(self) -> UInt64:
        """Returns the id of the Asset"""

    def __eq__(self, other: Asset) -> bool:  # type: ignore[override]
        """Asset equality is determined by the equality of an Asset's id"""

    def __ne__(self, other: Asset) -> bool:  # type: ignore[override]
        """Asset equality is determined by the equality of an Asset's id"""
    # truthiness
    def __bool__(self) -> bool:
        """Returns `True` if `asset_id` is not `0`"""

    @property
    def total(self) -> UInt64:
        """Total number of units of this asset

        ```{note}
        Asset must be an available resource
        ```
        """

    @property
    def decimals(self) -> UInt64:
        """See AssetParams.Decimals

        ```{note}
        Asset must be an available resource
        ```
        """

    @property
    def default_frozen(self) -> bool:
        """Frozen by default or not

        ```{note}
        Asset must be an available resource
        ```
        """

    @property
    def unit_name(self) -> Bytes:
        """Asset unit name

        ```{note}
        Asset must be an available resource
        ```
        """

    @property
    def name(self) -> Bytes:
        """Asset name

        ```{note}
        Asset must be an available resource
        ```
        """

    @property
    def url(self) -> Bytes:
        """URL with additional info about the asset

        ```{note}
        Asset must be an available resource
        ```
        """

    @property
    def metadata_hash(self) -> Bytes:
        """Arbitrary commitment

        ```{note}
        Asset must be an available resource
        ```
        """

    @property
    def manager(self) -> Account:
        """Manager address

        ```{note}
        Asset must be an available resource
        ```
        """

    @property
    def reserve(self) -> Account:
        """Reserve address

        ```{note}
        Asset must be an available resource
        ```
        """

    @property
    def freeze(self) -> Account:
        """Freeze address

        ```{note}
        Asset must be an available resource
        ```
        """

    @property
    def clawback(self) -> Account:
        """Clawback address

        ```{note}
        Asset must be an available resource
        ```
        """

    @property
    def creator(self) -> Account:
        """Creator address

        ```{note}
        Asset must be an available resource
        ```
        """

    def balance(self, account: Account, /) -> UInt64:
        """Amount of the asset unit held by this account. Fails if the account has not
        opted in to the asset.

        ```{note}
        Asset and supplied Account must be an available resource
        ```
        """

    def frozen(self, account: Account, /) -> bool:
        """Is the asset frozen or not. Fails if the account has not
        opted in to the asset.

        ```{note}
        Asset and supplied Account must be an available resource
        ```
        """

@typing.final
class Application:
    """An Application on the Algorand network."""

    def __init__(self, application_id: UInt64 | int = 0, /):
        """Initialized with the id of an application. Defaults to zero (an invalid ID)."""

    @property
    def id(self) -> UInt64:
        """Returns the id of the application"""

    def __eq__(self, other: Application) -> bool:  # type: ignore[override]
        """Application equality is determined by the equality of an Application's id"""

    def __ne__(self, other: Application) -> bool:  # type: ignore[override]
        """Application equality is determined by the equality of an Application's id"""
    # truthiness
    def __bool__(self) -> bool:
        """Returns `True` if `application_id` is not `0`"""

    @property
    def approval_program(self) -> Bytes:
        """Bytecode of Approval Program

        ```{note}
        Application must be an available resource
        ```
        """

    @property
    def clear_state_program(self) -> Bytes:
        """Bytecode of Clear State Program

        ```{note}
        Application must be an available resource
        ```
        """

    @property
    def global_num_uint(self) -> UInt64:
        """Number of uint64 values allowed in Global State

        ```{note}
        Application must be an available resource
        ```
        """

    @property
    def global_num_bytes(self) -> UInt64:
        """Number of byte array values allowed in Global State

        ```{note}
        Application must be an available resource
        ```
        """

    @property
    def local_num_uint(self) -> UInt64:
        """Number of uint64 values allowed in Local State

        ```{note}
        Application must be an available resource
        ```
        """

    @property
    def local_num_bytes(self) -> UInt64:
        """Number of byte array values allowed in Local State

        ```{note}
        Application must be an available resource
        ```
        """

    @property
    def extra_program_pages(self) -> UInt64:
        """Number of Extra Program Pages of code space

        ```{note}
        Application must be an available resource
        ```
        """

    @property
    def creator(self) -> Account:
        """Creator address

        ```{note}
        Application must be an available resource
        ```
        """

    @property
    def address(self) -> Account:
        """Address for which this application has authority

        ```{note}
        Application must be an available resource
        ```
        """
