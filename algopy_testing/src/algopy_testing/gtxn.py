from __future__ import annotations

import typing
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from algopy_testing.models.transactions import (
    ApplicationCallFields,
    AssetConfigFields,
    AssetFreezeFields,
    AssetTransferFields,
    KeyRegistrationFields,
    PaymentFields,
    _ApplicationCallBaseFields,
    _AssetConfigBaseFields,
    _AssetFreezeBaseFields,
    _AssetTransferBaseFields,
    _KeyRegistrationBaseFields,
    _PaymentBaseFields,
    _TransactionBaseFields,
)
from algopy_testing.utils import txn_type_to_bytes

if TYPE_CHECKING:
    import algopy

# NOTE: The actual access by group_index is not used, its there to comply with stubs
# but user has no need to deal with that as we can reason on the index based
# on position in gtxn group
NULL_GTXN_GROUP_INDEX = -1


@dataclass
class _GroupTransaction:
    _fields: dict[str, typing.Any] = field(default_factory=dict)

    group_index: algopy.UInt64 | int = field(default=NULL_GTXN_GROUP_INDEX)

    def __init__(self, group_index: algopy.UInt64 | int) -> None:
        self.group_index = group_index
        self._fields = {}


class TransactionFields(
    _TransactionBaseFields,
    _AssetTransferBaseFields,
    _PaymentBaseFields,
    _ApplicationCallBaseFields,
    _KeyRegistrationBaseFields,
    _AssetConfigBaseFields,
    _AssetFreezeBaseFields,
    total=False,
):
    pass


@dataclass
class TransactionBase(_GroupTransaction):
    def __init__(
        self, group_index: algopy.UInt64 | int, **kwargs: typing.Unpack[_TransactionBaseFields]
    ):
        super().__init__(group_index=group_index)
        self._fields.update(kwargs)

    def set(self, **kwargs: typing.Unpack[_TransactionBaseFields]) -> None:
        """Updates inner transaction parameter values"""
        self._fields.update(kwargs)

    def __getattr__(self, name: str) -> object:
        from algopy_testing import get_test_context

        if name not in _TransactionBaseFields.__annotations__:
            raise AttributeError(f"'{type(self)}' object has no attribute '{name}'")

        if name == "group_index":
            context = get_test_context()
            return context.get_transaction_group().index(self)

        return self._fields.get(name)


@dataclass
class AssetTransferTransaction(TransactionBase):
    def __init__(
        self, group_index: algopy.UInt64 | int, **kwargs: typing.Unpack[AssetTransferFields]
    ):
        super().__init__(group_index=group_index)
        self._fields.update(kwargs)

    def set(self, **kwargs: typing.Unpack[AssetTransferFields]) -> None:
        """Updates inner transaction parameter values"""
        self._fields.update(kwargs)

    def __getattr__(self, name: str) -> typing.Any:
        if name in AssetTransferFields.__annotations__:
            return self._fields.get(name)

        raise AttributeError(f"'{type(self)}' object has no attribute '{name}'")


@dataclass
class PaymentTransaction(TransactionBase):
    def __init__(self, group_index: algopy.UInt64 | int, **kwargs: typing.Unpack[PaymentFields]):
        import algopy

        super().__init__(group_index=group_index)
        self._fields.update(
            {
                "type": algopy.TransactionType.Payment,
                "type_bytes": txn_type_to_bytes(int(algopy.TransactionType.Payment)),
                **kwargs,
            }
        )

    def __getattr__(self, name: str) -> typing.Any:
        if name in PaymentFields.__annotations__:
            return self._fields.get(name)

        raise AttributeError(f"'{type(self)}' object has no attribute '{name}'")


@dataclass
class ApplicationCallTransaction(TransactionBase):
    def __init__(
        self, group_index: algopy.UInt64 | int, **kwargs: typing.Unpack[ApplicationCallFields]
    ):
        import algopy

        super().__init__(group_index=group_index)
        self._fields.update(
            {
                "type": algopy.TransactionType.ApplicationCall,
                "type_bytes": txn_type_to_bytes(int(algopy.TransactionType.ApplicationCall)),
                **kwargs,
            }
        )

    def __getattr__(self, name: str) -> typing.Any:
        if name in ApplicationCallFields.__annotations__:
            return self._fields.get(name)

        raise AttributeError(f"'{type(self)}' object has no attribute '{name}'")


class KeyRegistrationTransaction(TransactionBase):
    def __init__(
        self, group_index: algopy.UInt64 | int, **kwargs: typing.Unpack[KeyRegistrationFields]
    ):
        import algopy

        super().__init__(group_index=group_index)
        self._fields.update(
            {
                "type": algopy.TransactionType.KeyRegistration,
                "type_bytes": txn_type_to_bytes(int(algopy.TransactionType.KeyRegistration)),
                **kwargs,
            }
        )

    def __getattr__(self, name: str) -> typing.Any:
        if name in KeyRegistrationFields.__annotations__:
            return self._fields.get(name)

        raise AttributeError(f"'{type(self)}' object has no attribute '{name}'")


@dataclass
class AssetConfigTransaction(TransactionBase):
    def __init__(
        self, group_index: algopy.UInt64 | int, **kwargs: typing.Unpack[AssetConfigFields]
    ):
        import algopy

        super().__init__(group_index=group_index)
        self._fields.update(
            {
                "type": algopy.TransactionType.AssetConfig,
                "type_bytes": txn_type_to_bytes(int(algopy.TransactionType.AssetConfig)),
                **kwargs,
            }
        )

    def __getattr__(self, name: str) -> typing.Any:
        if name in AssetConfigFields.__annotations__:
            return self._fields.get(name)

        raise AttributeError(f"'{type(self)}' object has no attribute '{name}'")


@dataclass
class AssetFreezeTransaction(TransactionBase):
    def __init__(
        self,
        group_index: algopy.UInt64 | int,
        **kwargs: typing.Unpack[AssetFreezeFields],
    ):
        import algopy

        super().__init__(group_index=group_index)
        self._fields.update(
            {
                "type": algopy.TransactionType.AssetFreeze,
                "type_bytes": txn_type_to_bytes(int(algopy.TransactionType.AssetFreeze)),
                **kwargs,
            }
        )

    def __getattr__(self, name: str) -> typing.Any:
        if name in AssetFreezeFields.__annotations__:
            return self._fields.get(name)

        raise AttributeError(f"'{type(self)}' object has no attribute '{name}'")


@dataclass
class Transaction(TransactionBase):
    def __init__(
        self,
        group_index: algopy.UInt64 | int,
        **kwargs: typing.Unpack[TransactionFields],
    ):
        if "type" not in kwargs:
            raise ValueError("Transaction 'type' field is required")

        super().__init__(group_index=group_index)
        self._fields.update(kwargs)

    def __getattr__(self, name: str) -> typing.Any:
        if name in TransactionFields.__annotations__:
            return self._fields.get(name)

        raise AttributeError(f"'{type(self)}' object has no attribute '{name}'")


__all__ = [
    "TransactionBase",
    "AssetTransferTransaction",
    "PaymentTransaction",
    "ApplicationCallTransaction",
    "KeyRegistrationTransaction",
    "AssetConfigTransaction",
    "AssetFreezeTransaction",
    "Transaction",
    "PaymentFields",
    "AssetTransferFields",
    "ApplicationCallFields",
    "KeyRegistrationFields",
    "AssetConfigFields",
    "AssetFreezeFields",
    "NULL_GTXN_GROUP_INDEX",
]
