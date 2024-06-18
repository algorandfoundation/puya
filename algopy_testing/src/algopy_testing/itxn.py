from __future__ import annotations

import logging
import typing
from copy import deepcopy

import algosdk

from algopy_testing.constants import MAX_UINT64
from algopy_testing.context import get_test_context
from algopy_testing.models.transactions import (
    PaymentFields,
    _ApplicationCallBaseFields,
    _AssetConfigBaseFields,
    _AssetFreezeBaseFields,
    _AssetTransferBaseFields,
    _KeyRegistrationBaseFields,
    _PaymentBaseFields,
    _TransactionCoreFields,
    _TransactionFields,
)
from algopy_testing.utils import dummy_transaction_id, txn_type_to_bytes

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    import algopy


class _BaseInnerTransaction:
    fields: dict[str, typing.Any]

    def submit(self) -> object:
        import algopy.itxn

        context = get_test_context()

        if not context:
            raise RuntimeError("No test context found")

        result = algopy.itxn.InnerTransactionResult(**self.fields)
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


class InnerTransaction(_BaseInnerTransaction):
    def __init__(
        self,
        *,
        type: algopy.TransactionType,  # noqa: A002
        **kwargs: typing.Unpack[_TransactionCoreFields],
    ):
        self.fields = {
            "type": type,
            "type_bytes": txn_type_to_bytes(int(type)),
            **kwargs,
        }

    def set(self, **kwargs: typing.Unpack[_TransactionFields]) -> None:
        """Updates inner transaction parameter values"""
        self.fields.update(kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(_TransactionFields, name)


class Payment(_BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[_PaymentBaseFields]):
        import algopy

        self.fields = {**kwargs, "type": algopy.TransactionType.Payment}

    def set(self, **kwargs: typing.Unpack[_PaymentBaseFields]) -> None:
        """Updates inner transaction parameter values"""
        import algopy

        self.fields.update({**kwargs, "type": algopy.TransactionType.Payment})

    def __getattr__(self, name: str) -> object:
        return self.get_field(_PaymentBaseFields, name)


class KeyRegistration(_BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[_KeyRegistrationBaseFields]):
        import algopy

        self.fields = {**kwargs, "type": algopy.TransactionType.KeyRegistration}

    def set(self, **kwargs: typing.Unpack[_KeyRegistrationBaseFields]) -> None:
        """Updates inner transaction parameter values"""
        import algopy

        self.fields.update({**kwargs, "type": algopy.TransactionType.KeyRegistration})

    def __getattr__(self, name: str) -> object:
        return self.get_field(_KeyRegistrationBaseFields, name)


class AssetConfig(_BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[_AssetConfigBaseFields]):
        import algopy

        self.fields = {**kwargs, "type": algopy.TransactionType.AssetConfig}

    def set(self, **kwargs: typing.Unpack[_AssetConfigBaseFields]) -> None:
        """Updates inner transaction parameter values"""
        import algopy

        self.fields.update({**kwargs, "type": algopy.TransactionType.AssetConfig})

    def __getattr__(self, name: str) -> object:
        return self.get_field(_AssetConfigBaseFields, name)


class AssetTransfer(_BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[_AssetTransferBaseFields]):
        import algopy

        from algopy_testing import get_test_context

        context = get_test_context()
        self.fields = {
            "type": algopy.TransactionType.AssetTransfer,
            "asset_sender": context.default_application.address if context else None,
            "amount": 0,
            **kwargs,
        }

    def set(self, **kwargs: typing.Unpack[_AssetTransferBaseFields]) -> None:
        """Updates inner transaction parameter values"""
        import algopy

        self.fields.update({**kwargs, "type": algopy.TransactionType.AssetTransfer})

    def __getattr__(self, name: str) -> object:
        return self.get_field(_AssetTransferBaseFields, name)


class AssetFreeze(_BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[_AssetFreezeBaseFields]):
        import algopy

        self.fields = {**kwargs, "type": algopy.TransactionType.AssetFreeze}

    def set(self, **kwargs: typing.Unpack[_AssetFreezeBaseFields]) -> None:
        """Updates inner transaction parameter values"""
        import algopy

        self.fields.update({**kwargs, "type": algopy.TransactionType.AssetFreeze})

    def __getattr__(self, name: str) -> object:
        return self.get_field(_AssetFreezeBaseFields, name)


class ApplicationCall(_BaseInnerTransaction):
    def __init__(self, **kwargs: typing.Unpack[_ApplicationCallBaseFields]):
        import algopy

        self.fields = {**kwargs, "type": algopy.TransactionType.ApplicationCall}

    def set(self, **kwargs: typing.Unpack[_ApplicationCallBaseFields]) -> None:
        """Updates inner transaction parameter values"""
        import algopy

        self.fields.update({**kwargs, "type": algopy.TransactionType.ApplicationCall})

    def __getattr__(self, name: str) -> object:
        return self.get_field(_ApplicationCallBaseFields, name)


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
        self._parse_covariant_types()

    def get_field(self, type_dict: object, name: str) -> typing.Any:
        if name in type_dict.__annotations__:
            return self.fields.get(name)

        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    def _parse_covariant_types(
        self,
    ) -> None:
        import algopy

        for name, value in self.fields.items():
            if isinstance(value, int):
                self.fields[name] = algopy.UInt64(value)
            if isinstance(value, bytes):
                self.fields[name] = algopy.Bytes(value)
            if isinstance(value, str):
                self.fields[name] = algopy.Bytes(value.encode("utf-8"))


class PaymentInnerTransaction(_BaseInnerTransactionResult):
    def __init__(self, **kwargs: typing.Unpack[PaymentFields]):
        import algopy

        super().__init__(algopy.TransactionType.Payment, **kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(PaymentFields, name)


class KeyRegistrationInnerTransaction(_BaseInnerTransactionResult):
    def __init__(self, **kwargs: typing.Unpack[_KeyRegistrationBaseFields]):
        import algopy

        super().__init__(algopy.TransactionType.KeyRegistration, **kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(_KeyRegistrationBaseFields, name)


class AssetConfigInnerTransaction(_BaseInnerTransactionResult):
    def __init__(self, **kwargs: typing.Unpack[_AssetConfigBaseFields]):
        import algopy

        super().__init__(algopy.TransactionType.AssetConfig, **kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(_AssetConfigBaseFields, name)


class AssetTransferInnerTransaction(_BaseInnerTransactionResult):
    def __init__(self, **kwargs: typing.Unpack[_AssetTransferBaseFields]):
        import algopy

        super().__init__(algopy.TransactionType.AssetTransfer, **kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(_AssetTransferBaseFields, name)


class AssetFreezeInnerTransaction(_BaseInnerTransactionResult):
    def __init__(self, **kwargs: typing.Unpack[_AssetFreezeBaseFields]):
        import algopy

        super().__init__(algopy.TransactionType.AssetFreeze, **kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(_AssetFreezeBaseFields, name)


class ApplicationCallInnerTransaction(_BaseInnerTransactionResult):
    def __init__(self, **kwargs: typing.Unpack[_ApplicationCallBaseFields]):
        import algopy

        super().__init__(algopy.TransactionType.ApplicationCall, **kwargs)

    def __getattr__(self, name: str) -> object:
        return self.get_field(_ApplicationCallBaseFields, name)


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

__all__ = [
    "_BaseInnerTransaction",
    "_InnerTransactionsType",
    "InnerTransaction",
    "Payment",
    "KeyRegistration",
    "AssetConfig",
    "AssetTransfer",
    "AssetFreeze",
    "ApplicationCall",
    "PaymentInnerTransaction",
    "KeyRegistrationInnerTransaction",
    "AssetConfigInnerTransaction",
    "AssetTransferInnerTransaction",
    "AssetFreezeInnerTransaction",
    "ApplicationCallInnerTransaction",
    "InnerTransactionResult",
]
