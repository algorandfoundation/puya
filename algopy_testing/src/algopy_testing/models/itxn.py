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
        if not context.inner_transactions:
            raise ValueError(
                "No inner transaction found in the context! Use `with algopy_testing_context()` "
                "to access the context manager."
            )
        itxn = context.inner_transactions[-1]

        if name not in itxn.__dict__:
            raise AttributeError(
                f"'Txn' object has no value set for attribute named '{name}'. "
                f"Use `context.patch_itxn_fields({name}=your_value)` to set the value "
                "in your test setup."
            )
        value = itxn.__dict__[name]
        return lambda: value


ITxn = _ITxn()
