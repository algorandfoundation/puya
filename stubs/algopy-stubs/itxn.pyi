import typing

from algopy import (
    Account,
    Application,
    Asset,
    Bytes,
    OnCompleteAction,
    TransactionType,
    UInt64,
    String,
)
from algopy._transaction import (
    _ApplicationProtocol,
    _AssetConfigProtocol,
    _AssetFreezeProtocol,
    _AssetTransferProtocol,
    _KeyRegistrationProtocol,
    _PaymentProtocol,
    _TransactionBaseProtocol,
)

class PaymentInnerTransaction(_PaymentProtocol, _TransactionBaseProtocol, typing.Protocol):
    """Payment inner transaction"""

class KeyRegistrationInnerTransaction(
    _KeyRegistrationProtocol, _TransactionBaseProtocol, typing.Protocol
):
    """Key Registration inner transaction"""

class AssetConfigInnerTransaction(_AssetConfigProtocol, _TransactionBaseProtocol, typing.Protocol):
    """Asset Config inner transaction"""

class AssetTransferInnerTransaction(
    _AssetTransferProtocol, _TransactionBaseProtocol, typing.Protocol
):
    """Asset Transfer inner transaction"""

class AssetFreezeInnerTransaction(_AssetFreezeProtocol, _TransactionBaseProtocol, typing.Protocol):
    """Asset Freeze inner transaction"""

class ApplicationCallInnerTransaction(
    _ApplicationProtocol, _TransactionBaseProtocol, typing.Protocol
):
    """Application Call inner transaction"""

class InnerTransactionResult(
    PaymentInnerTransaction,
    KeyRegistrationInnerTransaction,
    AssetConfigInnerTransaction,
    AssetTransferInnerTransaction,
    AssetFreezeInnerTransaction,
    ApplicationCallInnerTransaction,
    _TransactionBaseProtocol,
):
    """An inner transaction of any type"""

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
