from __future__ import annotations

import functools
import typing

from algopy_testing.constants import UINT64_SIZE
from algopy_testing.utils import int_to_bytes

if typing.TYPE_CHECKING:
    import algopy

    from algopy_testing.context import AlgopyTestContext


if typing.TYPE_CHECKING:
    import algopy


_P = typing.ParamSpec("_P")
_R = typing.TypeVar("_R")


def _extract_refs_from_args(
    args: tuple[typing.Any, ...], kwargs: dict[str, typing.Any], ref_type: type
) -> list[typing.Any]:
    import algopy

    refs: list[typing.Any] = []
    for arg in list(args) + list(kwargs.values()):
        match arg:
            case algopy.gtxn.TransactionBase() if ref_type is algopy.gtxn.TransactionBase:
                refs.append(arg)
            case algopy.Account() if ref_type is algopy.Account:
                refs.append(arg)
            case algopy.Asset() if ref_type is algopy.Asset:
                refs.append(arg)
            case algopy.Application() if ref_type is algopy.Application:
                refs.append(arg)
            case (
                algopy.Bytes()
                | algopy.String()
                | algopy.BigUInt()
                | algopy.UInt64()
                | int()
            ) if ref_type is algopy.Bytes:
                refs.append(_extract_bytes(arg))
            case _:
                continue
    return refs


def _extract_bytes(value: object) -> algopy.Bytes:
    import algopy

    if isinstance(value, algopy.Bytes):
        return value
    if isinstance(value, (algopy.String | algopy.BigUInt)):
        return value.bytes
    if isinstance(value, (algopy.UInt64 | int)):
        return algopy.Bytes(int_to_bytes(int(value), UINT64_SIZE))
    raise ValueError(f"Unsupported type: {type(value).__name__}")


def _extract_and_append_txn_to_context(
    context: AlgopyTestContext, args: tuple[typing.Any, ...], kwargs: dict[str, typing.Any]
) -> None:
    import algopy

    context.add_transactions(_extract_refs_from_args(args, kwargs, algopy.gtxn.TransactionBase))
    existing_indexes = {int(txn.group_index) for txn in context.get_transaction_group()}
    new_group_txn_index = max(existing_indexes, default=-1) + 1

    context.add_transactions(
        [
            context.any_app_call_txn(
                group_index=1,
                sender=context.default_creator,
                app_id=context.default_application,
                accounts=_extract_refs_from_args(args, kwargs, algopy.Account),
                assets=_extract_refs_from_args(args, kwargs, algopy.Asset),
                apps=_extract_refs_from_args(args, kwargs, algopy.Application),
                app_args=_extract_refs_from_args(args, kwargs, algopy.Bytes),
                approval_program_pages=_extract_refs_from_args(args, kwargs, algopy.Bytes),
                clear_state_program_pages=_extract_refs_from_args(args, kwargs, algopy.Bytes),
            ),
        ]
    )
    context.set_active_transaction_index(new_group_txn_index)


@typing.overload
def abimethod(fn: typing.Callable[_P, _R], /) -> typing.Callable[_P, _R]: ...


@typing.overload
def abimethod(
    *,
    name: str | None = None,
    create: typing.Literal["allow", "require", "disallow"] = "disallow",
    allow_actions: typing.Sequence[
        algopy.OnCompleteAction
        | typing.Literal[
            "NoOp",
            "OptIn",
            "CloseOut",
            # ClearState has its own program, so is not considered as part of ARC4 routing
            "UpdateApplication",
            "DeleteApplication",
        ]
    ] = ("NoOp",),
    readonly: bool = False,
    default_args: typing.Mapping[str, str | object] = {},
) -> typing.Callable[[typing.Callable[_P, _R]], typing.Callable[_P, _R]]: ...


def abimethod(  # noqa: PLR0913
    fn: typing.Callable[_P, _R] | None = None,
    *,
    name: str | None = None,  # noqa: ARG001
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
    readonly: bool = False,  # noqa: ARG001
    default_args: typing.Mapping[str, str | object] | None = None,  # noqa: ARG001
) -> typing.Callable[[typing.Callable[_P, _R]], typing.Callable[_P, _R]] | typing.Callable[_P, _R]:
    def decorator(fn: typing.Callable[_P, _R]) -> typing.Callable[_P, _R]:
        @functools.wraps(fn)
        def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            from algopy_testing import get_test_context

            context = get_test_context()
            if context is None or context._active_transaction_index is not None:
                return fn(*args, **kwargs)

            _extract_and_append_txn_to_context(context, args, kwargs)
            return fn(*args, **kwargs)

        return wrapper

    if fn is not None:
        return decorator(fn)
    return decorator
