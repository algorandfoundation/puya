import typing

from puyapy import Account, Application, Asset, Bytes, OnCompleteAction, TransactionType, UInt64
from puyapy._transaction import (
    ApplicationCallTransactionFields,
    AssetConfigTransactionFields,
    AssetFreezeTransactionFields,
    AssetTransferTransactionFields,
    KeyRegistrationTransactionFields,
    PaymentTransactionFields,
    SharedTransactionFields,
)

class PaymentInnerTransaction(PaymentTransactionFields, SharedTransactionFields, typing.Protocol):
    """Payment inner transaction"""

class KeyRegistrationInnerTransaction(
    KeyRegistrationTransactionFields, SharedTransactionFields, typing.Protocol
):
    """Key Registration inner transaction"""

class AssetConfigInnerTransaction(
    AssetConfigTransactionFields, SharedTransactionFields, typing.Protocol
):
    """Asset Config inner transaction"""

    @property
    def created_asset(self) -> Asset: ...

class AssetTransferInnerTransaction(
    AssetTransferTransactionFields, SharedTransactionFields, typing.Protocol
):
    """Asset Transfer inner transaction"""

class AssetFreezeInnerTransaction(
    AssetFreezeTransactionFields, SharedTransactionFields, typing.Protocol
):
    """Asset Freeze inner transaction"""

class ApplicationCallInnerTransaction(
    ApplicationCallTransactionFields, SharedTransactionFields, typing.Protocol
):
    """Application Call inner transaction"""

    def logs(self, index: UInt64 | int) -> Bytes:
        """Log messages emitted by an application call (inner transactions only)"""
    @property
    def num_logs(self) -> UInt64:
        """Number of logs (inner transactions only)"""
    @property
    def created_application(self) -> Application:
        """ApplicationID allocated by the creation of an application (inner transactions only)"""

class AnyInnerTransaction(
    PaymentInnerTransaction,
    KeyRegistrationInnerTransaction,
    AssetConfigInnerTransaction,
    AssetTransferInnerTransaction,
    AssetFreezeInnerTransaction,
    ApplicationCallInnerTransaction,
    SharedTransactionFields,
):
    """An inner transaction of any type"""

_TResult_co = typing.TypeVar(
    "_TResult_co",
    covariant=True,
)

class _InnerTransactionParams(typing.Protocol[_TResult_co]):
    def submit(self) -> _TResult_co:
        """Submits inner transaction parameters and returns the resulting inner transaction"""
    def copy(self) -> typing.Self:
        """Copies a set of inner transaction parameters"""

class AnyTransactionParams(_InnerTransactionParams[AnyInnerTransaction]):
    """Parameters for an inner transaction of any type"""

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
        asset: Asset | UInt64 | int = ...,
        total: UInt64 | int = ...,
        unit_name: Bytes | bytes = ...,
        asset_name: Bytes | bytes = ...,
        decimals: UInt64 | int = ...,
        default_frozen: bool = ...,
        url: Bytes | bytes = ...,
        metadata_hash: Bytes | bytes = ...,
        manager: Account | str = ...,
        reserve: Account | str = ...,
        freeze: Account | str = ...,
        clawback: Account | str = ...,
        ## asset transfer
        xfer_asset: Asset | UInt64 | int = ...,
        asset_amount: UInt64 | int = ...,
        asset_receiver: Account | str = ...,
        asset_close_to: Account | str = ...,
        ## asset freeze
        freeze_asset: Asset | UInt64 | int = ...,
        freeze_account: Account | str = ...,
        frozen: bool = ...,
        ## application call
        application_id: Application | UInt64 | int = ...,
        approval_program: Bytes | bytes = ...,
        clear_state_program: Bytes | bytes = ...,
        on_completion: OnCompleteAction | UInt64 | int = ...,
        global_num_uint: UInt64 | int = ...,
        global_num_byte_slice: UInt64 | int = ...,
        local_num_uint: UInt64 | int = ...,
        local_num_byte_slice: UInt64 | int = ...,
        extra_program_pages: UInt64 | int = ...,
        application_args: tuple[Bytes, ...] = ...,
        accounts: tuple[Account, ...] = ...,
        assets: tuple[Asset, ...] = ...,
        applications: tuple[Application, ...] = ...,
        ## shared
        sender: Account | str = ...,
        fee: UInt64 | int = ...,
        note: Bytes | bytes = ...,
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
        asset: Asset | UInt64 | int = ...,
        total: UInt64 | int = ...,
        unit_name: Bytes | bytes = ...,
        asset_name: Bytes | bytes = ...,
        decimals: UInt64 | int = ...,
        default_frozen: bool = ...,
        url: Bytes | bytes = ...,
        metadata_hash: Bytes | bytes = ...,
        manager: Account | str = ...,
        reserve: Account | str = ...,
        freeze: Account | str = ...,
        clawback: Account | str = ...,
        ## asset transfer
        xfer_asset: Asset | UInt64 | int = ...,
        asset_amount: UInt64 | int = ...,
        asset_receiver: Account | str = ...,
        asset_close_to: Account | str = ...,
        ## asset freeze
        freeze_asset: Asset | UInt64 | int = ...,
        freeze_account: Account | str = ...,
        frozen: bool = ...,
        ## application call
        application_id: Application | UInt64 | int = ...,
        approval_program: Bytes | bytes = ...,
        clear_state_program: Bytes | bytes = ...,
        on_completion: OnCompleteAction | UInt64 | int = ...,
        global_num_uint: UInt64 | int = ...,
        global_num_byte_slice: UInt64 | int = ...,
        local_num_uint: UInt64 | int = ...,
        local_num_byte_slice: UInt64 | int = ...,
        extra_program_pages: UInt64 | int = ...,
        application_args: tuple[Bytes, ...] = ...,
        accounts: tuple[Account, ...] = ...,
        assets: tuple[Asset, ...] = ...,
        applications: tuple[Application, ...] = ...,
        ## shared
        sender: Account | str = ...,
        fee: UInt64 | int = ...,
        note: Bytes | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None:
        """Updates inner transaction parameter values"""

class PaymentTransactionParams(_InnerTransactionParams[PaymentInnerTransaction]):
    """Parameters for a Payment inner transaction"""

    def __init__(
        self,
        *,
        receiver: Account | str,
        amount: UInt64 | int = ...,
        close_remainder_to: Account | str = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = ...,
        note: Bytes | bytes = ...,
        rekey_to: Account | str = ...,
    ): ...
    def set(
        self,
        *,
        receiver: Account | str = ...,
        amount: UInt64 | int = ...,
        close_remainder_to: Account | str = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = ...,
        note: Bytes | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None:
        """Updates inner transaction parameter values"""

class KeyRegistrationTransactionParams(_InnerTransactionParams[KeyRegistrationInnerTransaction]):
    """Parameters for a Key Registration inner transaction"""

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
        fee: UInt64 | int = ...,
        note: Bytes | bytes = ...,
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
        fee: UInt64 | int = ...,
        note: Bytes | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None:
        """Updates inner transaction parameter values"""

class AssetConfigTransactionParams(_InnerTransactionParams[AssetConfigInnerTransaction]):
    """Parameters for an Asset Config inner transaction"""

    def __init__(
        self,
        *,
        asset: Asset | UInt64 | int = ...,
        total: UInt64 | int = ...,
        unit_name: Bytes | bytes = ...,
        asset_name: Bytes | bytes = ...,
        decimals: UInt64 | int = ...,
        default_frozen: bool = ...,
        url: Bytes | bytes = ...,
        metadata_hash: Bytes | bytes = ...,
        manager: Account | str = ...,
        reserve: Account | str = ...,
        freeze: Account | str = ...,
        clawback: Account | str = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = ...,
        note: Bytes | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None: ...
    def set(
        self,
        *,
        asset: Asset | UInt64 | int = ...,
        total: UInt64 | int = ...,
        unit_name: Bytes | bytes = ...,
        asset_name: Bytes | bytes = ...,
        decimals: UInt64 | int = ...,
        default_frozen: bool = ...,
        url: Bytes | bytes = ...,
        metadata_hash: Bytes | bytes = ...,
        manager: Account | str = ...,
        reserve: Account | str = ...,
        freeze: Account | str = ...,
        clawback: Account | str = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = ...,
        note: Bytes | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None:
        """Updates inner transaction parameter values"""

class AssetTransferTransactionParams(_InnerTransactionParams[AssetTransferInnerTransaction]):
    """Parameters for an Asset Transfer inner transaction"""

    def __init__(
        self,
        *,
        xfer_asset: Asset | UInt64 | int,
        asset_receiver: Account | str,
        asset_amount: UInt64 | int = ...,
        asset_close_to: Account | str = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = ...,
        note: Bytes | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None: ...
    def set(
        self,
        *,
        xfer_asset: Asset | UInt64 | int = ...,
        asset_amount: UInt64 | int = ...,
        asset_receiver: Account | str = ...,
        asset_close_to: Account | str = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = ...,
        note: Bytes | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None:
        """Updates transaction parameter values"""

class AssetFreezeTransactionParams(_InnerTransactionParams[AssetFreezeInnerTransaction]):
    """Parameters for an Asset Freeze inner transaction"""

    def __init__(
        self,
        *,
        freeze_asset: Asset | UInt64 | int,
        freeze_account: Account | str,
        frozen: bool,
        sender: Account | str = ...,
        fee: UInt64 | int = ...,
        note: Bytes | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None: ...
    def set(
        self,
        *,
        freeze_asset: Asset | UInt64 | int = ...,
        freeze_account: Account | str = ...,
        frozen: bool = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = ...,
        note: Bytes | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None:
        """Updates inner transaction parameter values"""

class ApplicationCallTransactionParams(_InnerTransactionParams[ApplicationCallInnerTransaction]):
    """Parameters for an Application Call inner transaction"""

    def __init__(
        self,
        *,
        application_id: Application | UInt64 | int = ...,
        approval_program: Bytes | bytes | tuple[Bytes, ...] = ...,
        clear_state_program: Bytes | bytes | tuple[Bytes, ...] = ...,
        on_completion: OnCompleteAction | UInt64 | int = ...,
        global_num_uint: UInt64 | int = ...,
        global_num_byte_slice: UInt64 | int = ...,
        local_num_uint: UInt64 | int = ...,
        local_num_byte_slice: UInt64 | int = ...,
        extra_program_pages: UInt64 | int = ...,
        application_args: tuple[Bytes, ...] = ...,
        accounts: tuple[Account, ...] = ...,
        assets: tuple[Asset, ...] = ...,
        applications: tuple[Application, ...] = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = ...,
        note: Bytes | bytes = ...,
        rekey_to: Account | str = ...,
    ) -> None: ...
    def set(
        self,
        *,
        application_id: Application | UInt64 | int = ...,
        approval_program: Bytes | bytes | tuple[Bytes, ...] = ...,
        clear_state_program: Bytes | bytes | tuple[Bytes, ...] = ...,
        on_completion: OnCompleteAction | UInt64 | int = ...,
        global_num_uint: UInt64 | int = ...,
        global_num_byte_slice: UInt64 | int = ...,
        local_num_uint: UInt64 | int = ...,
        local_num_byte_slice: UInt64 | int = ...,
        extra_program_pages: UInt64 | int = ...,
        application_args: tuple[Bytes, ...] = ...,
        accounts: tuple[Account, ...] = ...,
        assets: tuple[Asset, ...] = ...,
        applications: tuple[Application, ...] = ...,
        sender: Account | str = ...,
        fee: UInt64 | int = ...,
        note: Bytes | bytes = ...,
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
    _t1: _InnerTransactionParams[_T1], _t2: _InnerTransactionParams[_T2], /
) -> tuple[_T1, _T2]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransactionParams[_T1],
    _t2: _InnerTransactionParams[_T2],
    _t3: _InnerTransactionParams[_T3],
    /,
) -> tuple[_T1, _T2, _T3]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransactionParams[_T1],
    _t2: _InnerTransactionParams[_T2],
    _t3: _InnerTransactionParams[_T3],
    _t4: _InnerTransactionParams[_T4],
    /,
) -> tuple[_T1, _T2, _T3, _T4]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransactionParams[_T1],
    _t2: _InnerTransactionParams[_T2],
    _t3: _InnerTransactionParams[_T3],
    _t4: _InnerTransactionParams[_T4],
    _t5: _InnerTransactionParams[_T5],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransactionParams[_T1],
    _t2: _InnerTransactionParams[_T2],
    _t3: _InnerTransactionParams[_T3],
    _t4: _InnerTransactionParams[_T4],
    _t5: _InnerTransactionParams[_T5],
    _t6: _InnerTransactionParams[_T6],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransactionParams[_T1],
    _t2: _InnerTransactionParams[_T2],
    _t3: _InnerTransactionParams[_T3],
    _t4: _InnerTransactionParams[_T4],
    _t5: _InnerTransactionParams[_T5],
    _t6: _InnerTransactionParams[_T6],
    _t7: _InnerTransactionParams[_T7],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransactionParams[_T1],
    _t2: _InnerTransactionParams[_T2],
    _t3: _InnerTransactionParams[_T3],
    _t4: _InnerTransactionParams[_T4],
    _t5: _InnerTransactionParams[_T5],
    _t6: _InnerTransactionParams[_T6],
    _t7: _InnerTransactionParams[_T7],
    _t8: _InnerTransactionParams[_T8],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransactionParams[_T1],
    _t2: _InnerTransactionParams[_T2],
    _t3: _InnerTransactionParams[_T3],
    _t4: _InnerTransactionParams[_T4],
    _t5: _InnerTransactionParams[_T5],
    _t6: _InnerTransactionParams[_T6],
    _t7: _InnerTransactionParams[_T7],
    _t8: _InnerTransactionParams[_T8],
    _t9: _InnerTransactionParams[_T9],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8, _T9]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransactionParams[_T1],
    _t2: _InnerTransactionParams[_T2],
    _t3: _InnerTransactionParams[_T3],
    _t4: _InnerTransactionParams[_T4],
    _t5: _InnerTransactionParams[_T5],
    _t6: _InnerTransactionParams[_T6],
    _t7: _InnerTransactionParams[_T7],
    _t8: _InnerTransactionParams[_T8],
    _t9: _InnerTransactionParams[_T9],
    _t10: _InnerTransactionParams[_T10],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8, _T9, _T10]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransactionParams[_T1],
    _t2: _InnerTransactionParams[_T2],
    _t3: _InnerTransactionParams[_T3],
    _t4: _InnerTransactionParams[_T4],
    _t5: _InnerTransactionParams[_T5],
    _t6: _InnerTransactionParams[_T6],
    _t7: _InnerTransactionParams[_T7],
    _t8: _InnerTransactionParams[_T8],
    _t9: _InnerTransactionParams[_T9],
    _t10: _InnerTransactionParams[_T10],
    _t11: _InnerTransactionParams[_T11],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8, _T9, _T10, _T11]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransactionParams[_T1],
    _t2: _InnerTransactionParams[_T2],
    _t3: _InnerTransactionParams[_T3],
    _t4: _InnerTransactionParams[_T4],
    _t5: _InnerTransactionParams[_T5],
    _t6: _InnerTransactionParams[_T6],
    _t7: _InnerTransactionParams[_T7],
    _t8: _InnerTransactionParams[_T8],
    _t9: _InnerTransactionParams[_T9],
    _t10: _InnerTransactionParams[_T10],
    _t11: _InnerTransactionParams[_T11],
    _t12: _InnerTransactionParams[_T12],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8, _T9, _T10, _T11, _T12]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransactionParams[_T1],
    _t2: _InnerTransactionParams[_T2],
    _t3: _InnerTransactionParams[_T3],
    _t4: _InnerTransactionParams[_T4],
    _t5: _InnerTransactionParams[_T5],
    _t6: _InnerTransactionParams[_T6],
    _t7: _InnerTransactionParams[_T7],
    _t8: _InnerTransactionParams[_T8],
    _t9: _InnerTransactionParams[_T9],
    _t10: _InnerTransactionParams[_T10],
    _t11: _InnerTransactionParams[_T11],
    _t12: _InnerTransactionParams[_T12],
    _t13: _InnerTransactionParams[_T13],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8, _T9, _T10, _T11, _T12, _T13]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransactionParams[_T1],
    _t2: _InnerTransactionParams[_T2],
    _t3: _InnerTransactionParams[_T3],
    _t4: _InnerTransactionParams[_T4],
    _t5: _InnerTransactionParams[_T5],
    _t6: _InnerTransactionParams[_T6],
    _t7: _InnerTransactionParams[_T7],
    _t8: _InnerTransactionParams[_T8],
    _t9: _InnerTransactionParams[_T9],
    _t10: _InnerTransactionParams[_T10],
    _t11: _InnerTransactionParams[_T11],
    _t12: _InnerTransactionParams[_T12],
    _t13: _InnerTransactionParams[_T13],
    _t14: _InnerTransactionParams[_T14],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8, _T9, _T10, _T11, _T12, _T13, _T14]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransactionParams[_T1],
    _t2: _InnerTransactionParams[_T2],
    _t3: _InnerTransactionParams[_T3],
    _t4: _InnerTransactionParams[_T4],
    _t5: _InnerTransactionParams[_T5],
    _t6: _InnerTransactionParams[_T6],
    _t7: _InnerTransactionParams[_T7],
    _t8: _InnerTransactionParams[_T8],
    _t9: _InnerTransactionParams[_T9],
    _t10: _InnerTransactionParams[_T10],
    _t11: _InnerTransactionParams[_T11],
    _t12: _InnerTransactionParams[_T12],
    _t13: _InnerTransactionParams[_T13],
    _t14: _InnerTransactionParams[_T14],
    _t15: _InnerTransactionParams[_T15],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8, _T9, _T10, _T11, _T12, _T13, _T14, _T15]: ...
@typing.overload
def submit_txns(
    _t1: _InnerTransactionParams[_T1],
    _t2: _InnerTransactionParams[_T2],
    _t3: _InnerTransactionParams[_T3],
    _t4: _InnerTransactionParams[_T4],
    _t5: _InnerTransactionParams[_T5],
    _t6: _InnerTransactionParams[_T6],
    _t7: _InnerTransactionParams[_T7],
    _t8: _InnerTransactionParams[_T8],
    _t9: _InnerTransactionParams[_T9],
    _t10: _InnerTransactionParams[_T10],
    _t11: _InnerTransactionParams[_T11],
    _t12: _InnerTransactionParams[_T12],
    _t13: _InnerTransactionParams[_T13],
    _t14: _InnerTransactionParams[_T14],
    _t15: _InnerTransactionParams[_T15],
    _t16: _InnerTransactionParams[_T16],
    /,
) -> tuple[_T1, _T2, _T3, _T4, _T5, _T6, _T7, _T8, _T9, _T10, _T11, _T12, _T13, _T14, _T15, _T16]:
    """Submits a group of up to 16 inner transactions parameters

    :returns: A tuple of the resulting inner transactions"""
