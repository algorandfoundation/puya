import typing
from collections.abc import Callable


class _GTxn:
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

    # TODO: refine mapping
    def _map_fields(self, name: str) -> str:
        field_mapping = {"type": "type_bytes", "type_enum": "type", "application_args": "app_args"}
        return field_mapping.get(name, name)

    def _get_value(self, txn_group: list[typing.Any], name: str, index: int) -> object:
        if index >= len(txn_group):
            raise IndexError("Transaction index out of range")
        gtxn = txn_group[index]
        value = getattr(gtxn, self._map_fields(name))
        if value is None:
            raise ValueError(f"'{name}' is not defined for {type(gtxn).__name__}")
        return value


GTxn = _GTxn()
