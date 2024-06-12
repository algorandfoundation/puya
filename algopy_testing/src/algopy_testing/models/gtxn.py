import typing
from collections.abc import Callable

import algopy


class _Gtxn:
    def __getattr__(self, name: str) -> Callable[[int], typing.Any]:
        from algopy_testing.context import get_test_context

        context = get_test_context()
        if not context:
            raise ValueError(
                "Test context is not initialized! Use `with algopy_testing_context()` to access "
                "the context manager."
            )

        txn_group = context.get_transaction_group()
        if not txn_group:
            raise ValueError(
                "No group transactions found in the context! Use `with algopy_testing_context()` "
                "to access the context manager."
            )

        return lambda index: self._get_value(txn_group, name, index)

    def _get_value(
        self, txn_group: list[algopy.gtxn.TransactionBase], name: str, index: int
    ) -> object:
        if index >= len(txn_group):
            raise IndexError("Transaction index out of range")
        gtxn = txn_group[index]
        value = getattr(gtxn, name)
        if value is None:
            raise ValueError(f"'{name}' is not defined for {type(gtxn).__name__}")
        return value


Gtxn = _Gtxn()
