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

        return lambda *args: self._handle_field(txn_group, name, *args)

    def _handle_field(
        self, txn_group: list[typing.Any], name: str, *args: typing.Any
    ) -> typing.Any:
        if len(args) == 1:
            return self._get_value(txn_group, name, args[0])
        elif len(args) == 2:
            return self._get_value(txn_group, name, args[0], args[1])
        else:
            raise ValueError(f"Invalid number of arguments for field '{name}'")

    # TODO: refine mapping
    def _map_fields(self, name: str) -> str:
        field_mapping = {"type": "type_bytes", "type_enum": "type", "application_args": "app_args"}
        return field_mapping.get(name, name)

    def _get_value(
        self, txn_group: list[typing.Any], name: str, index: int, second_arg: typing.Any = None
    ) -> object:
        if index >= len(txn_group):
            raise IndexError("Transaction index out of range")
        gtxn = txn_group[index]
        mapped_name = self._map_fields(name)
        value = getattr(gtxn, mapped_name)

        if callable(value) and second_arg is not None:
            return value(second_arg)
        elif value is None:
            raise ValueError(f"'{name}' is not defined for {type(gtxn).__name__}")
        return value


GTxn = _GTxn()
