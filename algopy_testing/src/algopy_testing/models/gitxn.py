import typing
from collections.abc import Callable, Sequence


class _GITxn:
    def __getattr__(self, name: str) -> Callable[[int], typing.Any]:
        from algopy_testing.context import get_test_context

        context = get_test_context()
        if not context:
            raise ValueError(
                "Test context is not initialized! Use `with algopy_testing_context()` to access "
                "the context manager."
            )
        if not context._inner_transaction_groups:
            raise ValueError(
                "No inner transaction found in the context! Use `with algopy_testing_context()` "
                "to access the context manager."
            )
        last_itxn_group = context._inner_transaction_groups[-1]

        if not last_itxn_group:
            raise ValueError("No inner transaction found in the testing context!")

        return lambda index: self._get_value(last_itxn_group, name, index)

    # TODO: refine mapping
    def _map_fields(self, name: str) -> str:
        field_mapping = {"type": "type_bytes", "type_enum": "type", "application_args": "app_args"}
        return field_mapping.get(name, name)

    def _get_value(self, itxn_group: Sequence[typing.Any], name: str, index: int) -> object:
        if index >= len(itxn_group):
            raise IndexError("Transaction index out of range")
        itxn = itxn_group[index]
        value = getattr(itxn, self._map_fields(name))
        if value is None:
            raise ValueError(f"'{name}' is not defined for {type(itxn).__name__}")
        return value


GITxn = _GITxn()
