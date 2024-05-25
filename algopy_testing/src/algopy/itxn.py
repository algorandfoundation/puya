from __future__ import annotations

import typing
from unittest.mock import MagicMock

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


class _InnerTransaction:
    def submit(self) -> InnerTransactionResult:
        """Submits inner transaction parameters and returns the resulting inner transaction"""
        raise NotImplementedError(
            "The 'submit' method is being executed in a python testing context. "
            "Please mock this method in according to your python testing framework of choice."
        )

    def copy(self) -> typing.Self:
        """Copies a set of inner transaction parameters"""
        raise NotImplementedError(
            "The 'copy' method is being executed in a python testing context. "
            "Please mock this method in according to your python testing framework of choice."
        )


class PaymentInnerTransaction:
    pass


class KeyRegistrationInnerTransaction:
    pass


class AssetConfigInnerTransaction:
    @property
    def created_asset(self) -> Asset:
        return MagicMock(spec=Asset)


class AssetTransferInnerTransaction:
    pass


class AssetFreezeInnerTransaction:
    pass


class ApplicationCallInnerTransaction:
    """Application Call inner transaction"""

    def logs(self, _index: UInt64 | int) -> Bytes:
        return MagicMock(spec=Bytes)

    @property
    def num_logs(self) -> UInt64:
        return MagicMock(spec=UInt64)

    @property
    def created_app(self) -> Application:
        return MagicMock(spec=Application)


class InnerTransactionResult:
    """An inner transaction of any type"""


class InnerTransaction:
    """Creates a set of fields used to submit an inner transaction of any type"""

    def __init__(self, **kwargs: typing.Any):
        fields = {
            "type": TransactionType,
            "receiver": Account,
            "amount": UInt64,
            "close_remainder_to": Account,
            "vote_key": Bytes,
            "selection_key": Bytes,
            "vote_first": UInt64,
            "vote_last": UInt64,
            "vote_key_dilution": UInt64,
            "non_participation": UInt64,
            "state_proof_key": Bytes,
            "config_asset": Asset,
            "total": UInt64,
            "unit_name": String,
            "asset_name": String,
            "decimals": UInt64,
            "default_frozen": bool,
            "url": String,
            "metadata_hash": Bytes,
            "manager": Account,
            "reserve": Account,
            "freeze": Account,
            "clawback": Account,
            "xfer_asset": Asset,
            "asset_amount": UInt64,
            "asset_sender": Account,
            "asset_receiver": Account,
            "asset_close_to": Account,
            "freeze_asset": Asset,
            "freeze_account": Account,
            "frozen": bool,
            "app_id": Application,
            "approval_program": Bytes,
            "clear_state_program": Bytes,
            "on_completion": OnCompleteAction,
            "global_num_uint": UInt64,
            "global_num_bytes": UInt64,
            "local_num_uint": UInt64,
            "local_num_bytes": UInt64,
            "extra_program_pages": UInt64,
            "app_args": tuple,
            "accounts": tuple,
            "assets": tuple,
            "apps": tuple,
            "sender": Account,
            "fee": UInt64,
            "note": String,
            "rekey_to": Account,
        }

        for field, field_type in fields.items():
            setattr(self, field, kwargs.get(field, MagicMock(spec=field_type)))

    def set(self, **kwargs: typing.Any) -> None:
        """Updates inner transaction parameter values"""
        for key, value in kwargs.items():
            setattr(self, key, value)


class Payment(_InnerTransaction):
    """Creates a set of fields used to submit a Payment inner transaction"""

    def __init__(
        self,
        **kwargs: typing.Any,
    ):
        fields = {
            "receiver": Account,
            "amount": UInt64,
            "close_remainder_to": Account,
            "sender": Account,
            "fee": UInt64,
            "note": String,
            "rekey_to": Account,
        }
        for field, field_type in fields.items():
            setattr(self, field, kwargs.get(field, MagicMock(spec=field_type)))

    def set(self, **kwargs: typing.Any) -> None:
        """Updates inner transaction parameter values"""
        for key, value in kwargs.items():
            setattr(self, key, value)


class KeyRegistration(_InnerTransaction):
    """Creates a set of fields used to submit a Key Registration inner transaction"""

    def __init__(self, **kwargs: typing.Any):
        fields = {
            "vote_key": Bytes,
            "selection_key": Bytes,
            "vote_first": UInt64,
            "vote_last": UInt64,
            "vote_key_dilution": UInt64,
            "non_participation": UInt64,
            "state_proof_key": Bytes,
            "sender": Account,
            "fee": UInt64,
            "note": String,
            "rekey_to": Account,
        }
        for field, field_type in fields.items():
            setattr(self, field, kwargs.get(field, MagicMock(spec=field_type)))

    def set(self, **kwargs: typing.Any) -> None:
        """Updates inner transaction parameter values"""
        for key, value in kwargs.items():
            setattr(self, key, value)


class AssetConfig(_InnerTransaction):
    """Creates a set of fields used to submit an Asset Config inner transaction"""

    def __init__(
        self,
        **kwargs: typing.Any,
    ) -> None:
        fields = {
            "config_asset": Asset,
            "total": UInt64,
            "unit_name": String,
            "asset_name": String,
            "decimals": UInt64,
            "default_frozen": bool,
            "url": String,
            "metadata_hash": Bytes,
            "manager": Account,
            "reserve": Account,
            "freeze": Account,
            "clawback": Account,
            "sender": Account,
            "fee": UInt64,
            "note": String,
            "rekey_to": Account,
        }
        for field, field_type in fields.items():
            setattr(self, field, kwargs.get(field, MagicMock(spec=field_type)))

    def set(self, **kwargs: typing.Any) -> None:
        """Updates inner transaction parameter values"""
        for key, value in kwargs.items():
            setattr(self, key, value)


class AssetTransfer(_InnerTransaction):
    """Creates a set of fields used to submit an Asset Transfer inner transaction"""

    def __init__(
        self,
        **kwargs: typing.Any,
    ) -> None:
        fields = {
            "xfer_asset": Asset,
            "asset_amount": UInt64,
            "asset_sender": Account,
            "asset_receiver": Account,
            "asset_close_to": Account,
            "sender": Account,
            "fee": UInt64,
            "note": String,
            "rekey_to": Account,
        }
        for field, field_type in fields.items():
            setattr(self, field, kwargs.get(field, MagicMock(spec=field_type)))

    def set(self, **kwargs: typing.Any) -> None:
        """Updates inner transaction parameter values"""
        for key, value in kwargs.items():
            setattr(self, key, value)


class AssetFreeze(_InnerTransaction):
    """Creates a set of fields used to submit a Asset Freeze inner transaction"""

    def __init__(
        self,
        **kwargs: typing.Any,
    ) -> None:
        fields = {
            "freeze_asset": Asset,
            "freeze_account": Account,
            "frozen": bool,
            "sender": Account,
            "fee": UInt64,
            "note": String,
            "rekey_to": Account,
        }

        for field, field_type in fields.items():
            setattr(self, field, kwargs.get(field, MagicMock(spec=field_type)))

    def set(self, **kwargs: typing.Any) -> None:
        """Updates inner transaction parameter values"""
        for key, value in kwargs.items():
            setattr(self, key, value)


class ApplicationCall(_InnerTransaction):
    """Creates a set of fields used to submit an Application Call inner transaction"""

    def __init__(
        self,
        **kwargs: typing.Any,
    ) -> None:
        fields = {
            "app_id": Application,
            "approval_program": Bytes,
            "clear_state_program": Bytes,
            "on_completion": OnCompleteAction,
            "global_num_uint": UInt64,
            "global_num_bytes": UInt64,
            "local_num_uint": UInt64,
            "local_num_bytes": UInt64,
            "extra_program_pages": UInt64,
            "app_args": tuple[Bytes, ...],
            "accounts": tuple[Account, ...],
            "assets": tuple[Asset, ...],
            "apps": tuple[Application, ...],
            "sender": Account,
            "fee": UInt64,
            "note": String,
            "rekey_to": Account,
        }
        for field, field_type in fields.items():
            setattr(self, field, kwargs.get(field, MagicMock(spec=field_type)))

    def set(self, **kwargs: typing.Any) -> None:
        """Updates inner transaction parameter values"""
        for key, value in kwargs.items():
            setattr(self, key, value)


def submit_txns(*_args: typing.Any, **_kwargs: typing.Any) -> None:
    raise NotImplementedError(
        "The 'submit_txns' method is being executed in a python testing context. "
        "Please mock this method in according to your python testing framework of choice."
    )
