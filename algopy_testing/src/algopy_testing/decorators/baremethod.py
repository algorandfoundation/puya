from __future__ import annotations

import functools
import typing

if typing.TYPE_CHECKING:
    import algopy

    from algopy_testing.context import AlgopyTestContext


_P = typing.ParamSpec("_P")
_R = typing.TypeVar("_R")


def _append_bare_txn_to_context(
    context: AlgopyTestContext,
) -> None:
    context.add_transactions(
        [
            context.any_application_call_transaction(
                sender=context.default_creator,
                app_id=context.default_application,
            ),
        ]
    )
    context.set_active_transaction_index(len(context.get_transaction_group()) - 1)


@typing.overload
def baremethod(fn: typing.Callable[_P, _R], /) -> typing.Callable[_P, _R]: ...


@typing.overload
def baremethod(
    *,
    create: typing.Literal["allow", "require", "disallow"] = "disallow",
    allow_actions: typing.Sequence[
        algopy.OnCompleteAction
        | typing.Literal[
            "NoOp",
            "OptIn",
            "CloseOut",
            "UpdateApplication",
            "DeleteApplication",
        ]
    ] = ("NoOp",),
) -> typing.Callable[[typing.Callable[_P, _R]], typing.Callable[_P, _R]]: ...


def baremethod(
    fn: typing.Callable[_P, _R] | None = None,
    *,
    create: typing.Literal["allow", "require", "disallow"] = "disallow",  # noqa: ARG001
    allow_actions: typing.Sequence[  # noqa: ARG001
        algopy.OnCompleteAction
        | typing.Literal[
            "NoOp",
            "OptIn",
            "CloseOut",
            "UpdateApplication",
            "DeleteApplication",
        ]
    ] = ("NoOp",),
) -> typing.Callable[[typing.Callable[_P, _R]], typing.Callable[_P, _R]] | typing.Callable[_P, _R]:
    def decorator(fn: typing.Callable[_P, _R]) -> typing.Callable[_P, _R]:
        @functools.wraps(fn)
        def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            from algopy_testing import get_test_context

            context = get_test_context()
            if context is None or context._active_transaction_index is not None:
                return fn(*args, **kwargs)

            # Custom logic for baremethod can be added here
            _append_bare_txn_to_context(context)
            return fn(*args, **kwargs)

        return wrapper

    if fn is not None:
        return decorator(fn)
    return decorator
