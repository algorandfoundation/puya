from __future__ import annotations

import functools
import typing

import algosdk

from algopy_testing.constants import UINT64_SIZE
from algopy_testing.utils import (
    abi_return_type_annotation_for_arg,
    abi_type_name_for_arg,
    int_to_bytes,
)

if typing.TYPE_CHECKING:
    import algopy

    from algopy_testing.context import AlgopyTestContext


if typing.TYPE_CHECKING:
    import algopy


_P = typing.ParamSpec("_P")
_R = typing.TypeVar("_R")


def _generate_arc4_signature(
    fn: typing.Callable[_P, _R], args: tuple[typing.Any, ...]
) -> algopy.Bytes:
    import algopy

    args_without_txns = [
        arg
        for arg in args
        if not isinstance(arg, algopy.gtxn.TransactionBase)  # type: ignore[arg-type, unused-ignore]
    ]
    arg_types = [algosdk.abi.Argument(abi_type_name_for_arg(arg=arg)) for arg in args_without_txns]
    return_type = algosdk.abi.Returns(
        abi_return_type_annotation_for_arg(fn.__annotations__.get("return"))
    )
    method = algosdk.abi.Method(name=fn.__name__, args=arg_types, returns=return_type)
    return algopy.Bytes(method.get_selector())


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
                algopy.String()
                | algopy.BigUInt()
                | algopy.UInt64()
                | algopy.BigUInt()
                | algopy.arc4.Bool()
                | algopy.arc4.BigUIntN()
                | algopy.arc4.BigUFixedNxM()
                | algopy.arc4.StaticArray()
                | algopy.arc4.DynamicArray()
                | algopy.arc4.DynamicBytes()
                | algopy.arc4.Address()
                | algopy.arc4.String()
                | algopy.arc4.Byte()
                | algopy.arc4.UIntN()
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
    if isinstance(
        value,
        (
            algopy.String
            | algopy.BigUInt
            | algopy.arc4.Bool
            | algopy.arc4.BigUIntN
            | algopy.arc4.BigUFixedNxM
            | algopy.arc4.StaticArray
            | algopy.arc4.DynamicArray
            | algopy.arc4.DynamicBytes
            | algopy.arc4.Address
            | algopy.arc4.String
            | algopy.arc4.Byte
            | algopy.arc4.UIntN
        ),
    ):
        return value.bytes  # type: ignore[union-attr, unused-ignore]
    if isinstance(value, (algopy.UInt64 | int)):
        return algopy.Bytes(int_to_bytes(int(value), UINT64_SIZE))
    raise ValueError(f"Unsupported type: {type(value).__name__}")


def _extract_and_append_txn_to_context(
    context: AlgopyTestContext,
    args: tuple[typing.Any, ...],
    kwargs: dict[str, typing.Any],
    fn: typing.Callable[_P, _R],
) -> None:
    import algopy

    context.add_transactions(_extract_refs_from_args(args, kwargs, algopy.gtxn.TransactionBase))

    context.add_transactions(
        [
            context.any_application_call_transaction(
                sender=context.default_creator,
                app_id=context.default_application,
                accounts=_extract_refs_from_args(args, kwargs, algopy.Account),
                assets=_extract_refs_from_args(args, kwargs, algopy.Asset),
                apps=_extract_refs_from_args(args, kwargs, algopy.Application),
                app_args=[
                    _generate_arc4_signature(fn, args),
                    *_extract_refs_from_args(args, kwargs, algopy.Bytes),
                ],
                approval_program_pages=_extract_refs_from_args(args, kwargs, algopy.Bytes),
                clear_state_program_pages=_extract_refs_from_args(args, kwargs, algopy.Bytes),
            ),
        ]
    )
    new_active_txn_index = len(context.get_transaction_group()) - 1
    context.set_active_transaction_index(new_active_txn_index if new_active_txn_index > 0 else 0)


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

            _extract_and_append_txn_to_context(context, args[1:], kwargs, fn)
            return fn(*args, **kwargs)

        return wrapper

    if fn is not None:
        return decorator(fn)
    return decorator
