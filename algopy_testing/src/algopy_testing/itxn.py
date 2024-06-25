from __future__ import annotations

import logging
import typing
from copy import deepcopy

import algosdk

from algopy_testing.constants import MAX_UINT64
from algopy_testing.context import get_test_context
from algopy_testing.models.transactions import (
    ApplicationCallFields,
    AssetConfigFields,
    AssetFreezeFields,
    AssetTransferFields,
    KeyRegistrationFields,
    PaymentFields,
    _ApplicationCallFields,
    _TransactionFields,
)
from algopy_testing.utils import dummy_transaction_id, txn_type_to_bytes

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    import algopy

    InnerTransactionResultType = (
        algopy.itxn.InnerTransactionResult
        | algopy.itxn.PaymentInnerTransaction
        | algopy.itxn.KeyRegistrationInnerTransaction
        | algopy.itxn.AssetConfigInnerTransaction
        | algopy.itxn.AssetTransferInnerTransaction
        | algopy.itxn.AssetFreezeInnerTransaction
        | algopy.itxn.ApplicationCallInnerTransaction
    )


def _create_inner_transaction_result(  # noqa: PLR0911
    txn: _BaseInnerTransaction,
) -> InnerTransactionResultType:
    import algopy

    match txn:
        case algopy.itxn.Payment():
            return algopy.itxn.PaymentInnerTransaction(**txn.fields)
        case algopy.itxn.KeyRegistration():
            return algopy.itxn.KeyRegistrationInnerTransaction(**txn.fields)
        case algopy.itxn.AssetConfig():
            return algopy.itxn.AssetConfigInnerTransaction(**txn.fields)
        case algopy.itxn.AssetTransfer():
            return algopy.itxn.AssetTransferInnerTransaction(**txn.fields)
        case algopy.itxn.AssetFreeze():
            return algopy.itxn.AssetFreezeInnerTransaction(**txn.fields)
        case algopy.itxn.ApplicationCall():
            return algopy.itxn.ApplicationCallInnerTransaction(**txn.fields)
        case algopy.itxn.InnerTransaction():
            return algopy.itxn.InnerTransactionResult(**txn.fields)
        case _:
            raise ValueError(f"Invalid inner transaction type: {type(txn)}")


class _BaseInnerTransaction:
    fields: dict[str, typing.Any]

    def submit(self) -> typing.Any:
        import algopy

        context = get_test_context()

        if not context:
            raise RuntimeError("No test context found")

        result = _create_inner_transaction_result(self)

        if not result:
            raise RuntimeError("Invalid inner transaction type")

        # if its an asset config then ensure to create an asset and add to context
        if isinstance(result, algopy.itxn.AssetConfigInnerTransaction):  # type: ignore[attr-defined, unused-ignore]
            # TODO: refine
            created_asset = context.any_asset(
                total=self.fields.get("total", None),
                decimals=self.fields.get("decimals", None),
                default_frozen=self.fields.get("default_frozen", None),
                unit_name=self.fields.get("unit_name", None),
                name=self.fields.get("asset_name", None),
                url=self.fields.get("url", b""),
                metadata_hash=self.fields.get("metadata_hash", ""),
                manager=self.fields.get("manager", algosdk.constants.ZERO_ADDRESS),
                reserve=self.fields.get("reserve", algosdk.constants.ZERO_ADDRESS),
                freeze=self.fields.get("freeze", algosdk.constants.ZERO_ADDRESS),
                clawback=self.fields.get("clawback", algosdk.constants.ZERO_ADDRESS),
                creator=self.fields.get("creator", algosdk.constants.ZERO_ADDRESS),
            )
            result.fields["xfer_asset"] = created_asset

        context._append_inner_transaction_group([result])
        return result

    def copy(self) -> typing.Self:
        return deepcopy(self)

    def get_field(self, type_dict: object, name: str) -> typing.Any:
        if name in type_dict.__annotations__:
            return self.fields.get(name)

        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _BaseInnerTransaction):
            return bool(self.fields == other.fields)
        return False

    def __hash__(self) -> int:
        return hash(self.fields)


class _InnerTransactionInitFields(typing.TypedDict, total=False):
    type: algopy.TransactionType
    ## payment
    receiver: algopy.Account | str
    amount: algopy.UInt64 | int
    close_remainder_to: algopy.Account | str
    ## key registration
    vote_key: algopy.Bytes | bytes
    selection_key: algopy.Bytes | bytes
    vote_first: algopy.UInt64 | int
    vote_last: algopy.UInt64 | int
    vote_key_dilution: algopy.UInt64 | int
    non_participation: algopy.UInt64 | int | bool
    state_proof_key: algopy.Bytes | bytes
    ## asset config
    config_asset: algopy.Asset | algopy.UInt64 | int
    total: algopy.UInt64 | int
    unit_name: algopy.String | algopy.Bytes | str | bytes
    asset_name: algopy.String | algopy.Bytes | str | bytes
    decimals: algopy.UInt64 | int
    default_frozen: bool
    url: algopy.String | algopy.Bytes | bytes | str
    metadata_hash: algopy.Bytes | bytes
    manager: algopy.Account | str
    reserve: algopy.Account | str
    freeze: algopy.Account | str
    clawback: algopy.Account | str
    ## asset transfer
    xfer_asset: algopy.Asset | algopy.UInt64 | int
    asset_amount: algopy.UInt64 | int
    asset_sender: algopy.Account | str
    asset_receiver: algopy.Account | str
    asset_close_to: algopy.Account | str
    ## asset freeze
    freeze_asset: algopy.Asset | algopy.UInt64 | int
    freeze_account: algopy.Account | str
    frozen: bool
    ## application call
    app_id: algopy.Application | algopy.UInt64 | int
    approval_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...]
    clear_state_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...]
    on_completion: algopy.OnCompleteAction | algopy.UInt64 | int
    global_num_uint: algopy.UInt64 | int
    global_num_bytes: algopy.UInt64 | int
    local_num_uint: algopy.UInt64 | int
    local_num_bytes: algopy.UInt64 | int
    extra_program_pages: algopy.UInt64 | int
    app_args: tuple[algopy.Bytes, ...]
    accounts: tuple[algopy.Account, ...]
    assets: tuple[algopy.Asset, ...]
    apps: tuple[algopy.Application, ...]
    ## shared
    sender: algopy.Account | str
    fee: algopy.UInt64 | int
    note: algopy.String | algopy.Bytes | str | bytes
    rekey_to: algopy.Account | str


class InnerTransaction(_BaseInnerTransaction):
    def __init__(
        self,
        **kwargs: typing.Unpack[_InnerTransactionInitFields],
    ):
        self.fields = {
            "type": kwargs["type"],
            "type_bytes": txn_type_to_bytes(int(kwargs["type"])),
            **kwargs,
        }

    def set(self, **kwargs: typing.Unpack[_InnerTransactionInitFields]) -> None:
        """Updates inner transaction parameter values"""
        self.fields.update(kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(_InnerTransactionInitFields, name)


class _PaymentInitFields(typing.TypedDict, total=False):
    receiver: algopy.Account | str
    amount: algopy.UInt64 | int
    close_remainder_to: algopy.Account | str
    sender: algopy.Account | str
    fee: algopy.UInt64 | int
    note: algopy.String | algopy.Bytes | str | bytes
    rekey_to: algopy.Account | str


class Payment(_BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[_PaymentInitFields]):
        import algopy

        self.fields = {**kwargs, "type": algopy.TransactionType.Payment}

    def set(self, **kwargs: typing.Unpack[_PaymentInitFields]) -> None:
        """Updates inner transaction parameter values"""
        import algopy

        self.fields.update({**kwargs, "type": algopy.TransactionType.Payment})

    def __getattr__(self, name: str) -> object:
        return self.get_field(_PaymentInitFields, name)


class _KeyRegistrationInitFields(typing.TypedDict, total=False):
    vote_key: algopy.Bytes | bytes
    selection_key: algopy.Bytes | bytes
    vote_first: algopy.UInt64 | int
    vote_last: algopy.UInt64 | int
    vote_key_dilution: algopy.UInt64 | int
    non_participation: algopy.UInt64 | int | bool
    state_proof_key: algopy.Bytes | bytes
    sender: algopy.Account | str
    fee: algopy.UInt64 | int
    note: algopy.String | algopy.Bytes | str | bytes
    rekey_to: algopy.Account | str


class KeyRegistration(_BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[_KeyRegistrationInitFields]):
        import algopy

        self.fields = {**kwargs, "type": algopy.TransactionType.KeyRegistration}

    def set(self, **kwargs: typing.Unpack[_KeyRegistrationInitFields]) -> None:
        """Updates inner transaction parameter values"""
        import algopy

        self.fields.update({**kwargs, "type": algopy.TransactionType.KeyRegistration})

    def __getattr__(self, name: str) -> object:
        return self.get_field(_KeyRegistrationInitFields, name)


class _AssetConfigInitFields(typing.TypedDict, total=False):
    config_asset: algopy.Asset | algopy.UInt64 | int
    total: algopy.UInt64 | int
    unit_name: algopy.String | algopy.Bytes | str | bytes
    asset_name: algopy.String | algopy.Bytes | str | bytes
    decimals: algopy.UInt64 | int
    default_frozen: bool
    url: algopy.String | algopy.Bytes | str | bytes
    metadata_hash: algopy.Bytes | bytes
    manager: algopy.Account | str
    reserve: algopy.Account | str
    freeze: algopy.Account | str
    clawback: algopy.Account | str
    sender: algopy.Account | str
    fee: algopy.UInt64 | int
    note: algopy.String | algopy.Bytes | str | bytes
    rekey_to: algopy.Account | str


class AssetConfig(_BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[_AssetConfigInitFields]):
        import algopy

        self.fields = {**kwargs, "type": algopy.TransactionType.AssetConfig}

    def set(self, **kwargs: typing.Unpack[_AssetConfigInitFields]) -> None:
        """Updates inner transaction parameter values"""
        import algopy

        self.fields.update({**kwargs, "type": algopy.TransactionType.AssetConfig})

    def __getattr__(self, name: str) -> object:
        return self.get_field(_AssetConfigInitFields, name)


class _AssetTransferInitFields(typing.TypedDict, total=False):
    xfer_asset: algopy.Asset | algopy.UInt64 | int
    asset_receiver: algopy.Account | str
    asset_amount: algopy.UInt64 | int
    asset_sender: algopy.Account | str
    asset_close_to: algopy.Account | str
    sender: algopy.Account | str
    fee: algopy.UInt64 | int
    note: algopy.String | algopy.Bytes | str | bytes
    rekey_to: algopy.Account | str


class AssetTransfer(_BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[_AssetTransferInitFields]):
        import algopy

        from algopy_testing import get_test_context

        context = get_test_context()
        self.fields = {
            "type": algopy.TransactionType.AssetTransfer,
            "asset_sender": context.default_application.address if context else None,
            "amount": 0,
            **kwargs,
        }

    def set(self, **kwargs: typing.Unpack[_AssetTransferInitFields]) -> None:
        """Updates inner transaction parameter values"""
        import algopy

        self.fields.update({**kwargs, "type": algopy.TransactionType.AssetTransfer})

    def __getattr__(self, name: str) -> object:
        return self.get_field(_AssetTransferInitFields, name)


class _AssetFreezeInitFields(typing.TypedDict, total=False):
    freeze_asset: algopy.Asset | algopy.UInt64 | int
    freeze_account: algopy.Account | str
    frozen: bool
    sender: algopy.Account | str
    fee: algopy.UInt64 | int
    note: algopy.String | algopy.Bytes | str | bytes
    rekey_to: algopy.Account | str


class AssetFreeze(_BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[_AssetFreezeInitFields]):
        import algopy

        self.fields = {**kwargs, "type": algopy.TransactionType.AssetFreeze}

    def set(self, **kwargs: typing.Unpack[_AssetFreezeInitFields]) -> None:
        """Updates inner transaction parameter values"""
        import algopy

        self.fields.update({**kwargs, "type": algopy.TransactionType.AssetFreeze})

    def __getattr__(self, name: str) -> object:
        return self.get_field(_AssetFreezeInitFields, name)


class _ApplicationCallInitFields(typing.TypedDict, total=False):
    app_id: algopy.Application | algopy.UInt64 | int
    approval_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...]
    clear_state_program: algopy.Bytes | bytes | tuple[algopy.Bytes, ...]
    on_completion: algopy.OnCompleteAction | algopy.UInt64 | int
    global_num_uint: algopy.UInt64 | int
    global_num_bytes: algopy.UInt64 | int
    local_num_uint: algopy.UInt64 | int
    local_num_bytes: algopy.UInt64 | int
    extra_program_pages: algopy.UInt64 | int
    app_args: tuple[algopy.Bytes | algopy.BytesBacked, ...]
    accounts: tuple[algopy.Account, ...]
    assets: tuple[algopy.Asset, ...]
    apps: tuple[algopy.Application, ...]
    sender: algopy.Account | str
    fee: algopy.UInt64 | int
    note: algopy.String | algopy.Bytes | str | bytes
    rekey_to: algopy.Account | str


class ApplicationCall(_BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[_ApplicationCallInitFields]):
        import algopy

        self.fields = {**kwargs, "type": algopy.TransactionType.ApplicationCall}

    def set(self, **kwargs: typing.Unpack[_ApplicationCallInitFields]) -> None:
        """Updates inner transaction parameter values"""
        import algopy

        self.fields.update({**kwargs, "type": algopy.TransactionType.ApplicationCall})

    def __getattr__(self, name: str) -> object:
        return self.get_field(_ApplicationCallInitFields, name)


# ==== Inner Transaction Results  ====
# These are used to represent finalized transactions submitted to the network
# and are created by the `submit` method of each inner transaction class


class _BaseInnerTransactionResult:
    fields: dict[str, typing.Any]

    @typing.overload
    def __init__(
        self,
        txn_type: algopy.TransactionType,
        **kwargs: typing.Unpack[_TransactionFields],
    ): ...

    @typing.overload
    def __init__(
        self,
        **kwargs: typing.Unpack[_TransactionFields],
    ): ...

    def __init__(
        self,
        txn_type: algopy.TransactionType | None = None,
        **kwargs: typing.Unpack[_TransactionFields],
    ):
        import algopy

        if txn_type is None and kwargs.get("type") is None:
            raise ValueError("No transaction type provided to `algopy.itxn.InnerTransaction`")

        txn_type = txn_type if txn_type is not None else kwargs.get("type")
        txn_type_bytes = txn_type_to_bytes(int(txn_type))  # type: ignore[arg-type]

        assert txn_type is not None

        self.fields = {
            "type": txn_type,
            "type_bytes": txn_type_bytes,
            "first_valid": algopy.UInt64(0),
            "first_valid_time": algopy.UInt64(0),
            "last_valid": algopy.UInt64(MAX_UINT64),
            "note": algopy.Bytes(b""),
            "lease": algopy.Bytes(bytes(algosdk.constants.ZERO_ADDRESS, encoding="utf-8")),
            "close_remainder_to": algopy.Bytes(
                bytes(algosdk.constants.ZERO_ADDRESS, encoding="utf-8")
            ),
            "txn_id": algopy.Bytes(dummy_transaction_id()),
            **kwargs,
        }
        self._parse_covariant_types(txn_type)

    def get_field(self, type_dict: object, name: str) -> typing.Any:
        if name in type_dict.__annotations__ or name in _TransactionFields.__annotations__:
            return self.fields.get(name)

        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    def _parse_covariant_types(
        self,
        txn_type: algopy.TransactionType,
    ) -> None:
        import algopy

        # Define the covariant fields for each transaction type
        covariant_fields = {
            algopy.TransactionType.Payment: ["receiver", "close_remainder_to", "sender"],
            algopy.TransactionType.KeyRegistration: [
                "vote_key",
                "selection_key",
                "state_proof_key",
                "sender",
            ],
            algopy.TransactionType.AssetConfig: [
                "config_asset",
                "unit_name",
                "asset_name",
                "url",
                "metadata_hash",
                "manager",
                "reserve",
                "freeze",
                "clawback",
                "sender",
            ],
            algopy.TransactionType.AssetTransfer: [
                "xfer_asset",
                "asset_sender",
                "asset_receiver",
                "asset_close_to",
                "sender",
            ],
            algopy.TransactionType.AssetFreeze: ["freeze_asset", "freeze_account", "sender"],
            algopy.TransactionType.ApplicationCall: [
                "app_id",
                "approval_program",
                "clear_state_program",
                "app_args",
                "accounts",
                "assets",
                "apps",
                "sender",
            ],
        }

        # Get the relevant fields for the given transaction type
        relevant_fields = covariant_fields.get(txn_type, [])

        for name, value in self.fields.items():
            if name in relevant_fields:
                if isinstance(value, int):
                    self.fields[name] = algopy.UInt64(value)
                elif isinstance(value, bytes):
                    self.fields[name] = algopy.Bytes(value)
                elif isinstance(value, str):
                    self.fields[name] = algopy.Bytes(value.encode("utf-8"))
                elif isinstance(value, tuple):
                    # Convert each element in the tuple to algopy.Bytes
                    self.fields[name] = tuple(
                        (
                            algopy.Bytes(item)
                            if isinstance(item, bytes)
                            else (
                                algopy.Bytes(item.encode("utf-8"))
                                if isinstance(item, str)
                                else item
                            )
                        )
                        for item in value
                    )
                elif isinstance(value, tuple) and all(
                    isinstance(
                        v,
                        algopy.Account
                        | algopy.String
                        | algopy.BigUInt
                        | algopy.arc4.String
                        | algopy.arc4.Bool
                        | algopy.arc4.Address,
                    )
                    for v in value
                ):
                    self.fields[name] = [v.bytes() for v in value]


class PaymentInnerTransaction(_BaseInnerTransactionResult):
    def __init__(self, **kwargs: typing.Unpack[PaymentFields]):
        import algopy

        super().__init__(algopy.TransactionType.Payment, **kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(PaymentFields, name)


class KeyRegistrationInnerTransaction(_BaseInnerTransactionResult):
    def __init__(self, **kwargs: typing.Unpack[KeyRegistrationFields]):
        import algopy

        super().__init__(algopy.TransactionType.KeyRegistration, **kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(KeyRegistrationFields, name)


class AssetConfigInnerTransaction(_BaseInnerTransactionResult):
    def __init__(self, **kwargs: typing.Unpack[AssetConfigFields]):
        import algopy

        super().__init__(algopy.TransactionType.AssetConfig, **kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(AssetConfigFields, name)

    @property
    def created_asset(self) -> algopy.Asset:
        # forward xfer asset that is auto set by submit()
        # for the asset config itxn type
        import algopy

        created_asset = self.fields["xfer_asset"]
        if not created_asset:
            raise ValueError("No created asset found")
        return typing.cast(algopy.Asset, created_asset)


class AssetTransferInnerTransaction(_BaseInnerTransactionResult):
    def __init__(self, **kwargs: typing.Unpack[AssetTransferFields]):
        import algopy

        super().__init__(algopy.TransactionType.AssetTransfer, **kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(AssetTransferFields, name)


class AssetFreezeInnerTransaction(_BaseInnerTransactionResult):
    def __init__(self, **kwargs: typing.Unpack[AssetFreezeFields]):
        import algopy

        super().__init__(algopy.TransactionType.AssetFreeze, **kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(AssetFreezeFields, name)


class ApplicationCallInnerTransaction(_BaseInnerTransactionResult):
    def __init__(self, **kwargs: typing.Unpack[ApplicationCallFields]):
        import algopy

        super().__init__(algopy.TransactionType.ApplicationCall, **kwargs)

    def __getattr__(self, name: str) -> object:
        from algopy_testing import get_test_context

        context = get_test_context()

        if name == "last_log" and context:
            return context.get_application_logs(self.get_field(_ApplicationCallFields, "app_id"))[
                -1
            ]

        return self.get_field(_ApplicationCallFields, name)


class InnerTransactionResult(_BaseInnerTransactionResult):
    def __init__(self, **kwargs: typing.Unpack[_TransactionFields]):
        super().__init__(**kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(_TransactionFields, name)


_InnerTransactionsType = (
    InnerTransactionResult
    | PaymentInnerTransaction
    | KeyRegistrationInnerTransaction
    | AssetConfigInnerTransaction
    | AssetTransferInnerTransaction
    | AssetFreezeInnerTransaction
    | ApplicationCallInnerTransaction
)


def submit_txns(transactions: list[_BaseInnerTransaction]) -> tuple[InnerTransactionResultType]:
    """Submits a group of up to 16 inner transactions parameters

    :returns: A tuple of the resulting inner transactions
    """
    from algopy_testing import get_test_context

    context = get_test_context()

    if len(transactions) > algosdk.constants.TX_GROUP_LIMIT:
        raise ValueError("Cannot submit more than 16 inner transactions at once")

    results = tuple(_create_inner_transaction_result(tx) for tx in transactions)
    context._append_inner_transaction_group(results)

    return results  # type: ignore[return-value]


__all__ = [
    "ApplicationCall",
    "ApplicationCallInnerTransaction",
    "AssetConfig",
    "AssetConfigInnerTransaction",
    "AssetFreeze",
    "AssetFreezeInnerTransaction",
    "AssetTransfer",
    "AssetTransferInnerTransaction",
    "InnerTransaction",
    "InnerTransactionResult",
    "KeyRegistration",
    "KeyRegistrationInnerTransaction",
    "Payment",
    "PaymentInnerTransaction",
    "_BaseInnerTransaction",
    "_InnerTransactionsType",
    "submit_txns",
]
