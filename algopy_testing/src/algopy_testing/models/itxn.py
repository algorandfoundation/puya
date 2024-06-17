import typing
from collections.abc import Callable


class _ITxn:
    def __getattr__(self, name: str) -> Callable[[], typing.Any]:
        from algopy_testing.context import get_test_context

        context = get_test_context()
        if not context:
            raise ValueError(
                "Test context is not initialized! Use `with algopy_testing_context()` to access "
                "the context manager."
            )
        if not context.inner_transaction_groups:
            raise ValueError(
                "No inner transaction found in the context! Use `with algopy_testing_context()` "
                "to access the context manager."
            )
        last_itxn_group = context.inner_transaction_groups[-1]

        if not last_itxn_group:
            raise ValueError("No inner transaction found in the testing context!")

        last_itxn = last_itxn_group[-1]

        value = getattr(last_itxn, name)
        if value is None:
            raise ValueError(f"'{name}' is not defined for {type(last_itxn).__name__} ")
        # mimic the static functions on ITxn with a lambda
        return lambda: value


ITxn = _ITxn()
