from __future__ import annotations

import functools
import typing

import algosdk

from algopy_testing.constants import UINT64_SIZE
from algopy_testing.utils import int_to_bytes

if typing.TYPE_CHECKING:
    import algopy

    from algopy_testing.context import AlgopyTestContext


if typing.TYPE_CHECKING:
    import algopy


_P = typing.ParamSpec("_P")
_R = typing.TypeVar("_R")


def _map_algopy_type_to_string(arg: typing.Any) -> str:  # noqa: PLR0911, C901, PLR0912
    import algopy

    if isinstance(arg, algopy.Bytes):
        return "byte[]"
    if isinstance(arg, algopy.arc4.Byte):
        return "byte"
    if isinstance(arg, algopy.arc4.Address):
        return "address"
    if isinstance(arg, algopy.arc4.Bool):
        return "bool"
    if isinstance(arg, algopy.String | algopy.arc4.String):
        return "string"
    if isinstance(arg, algopy.UInt64 | algopy.arc4.UInt64):
        return "uint64"
    if isinstance(arg, algopy.arc4.UInt16):
        return "uint16"
    if isinstance(arg, algopy.arc4.UInt32):
        return "uint32"
    if isinstance(arg, algopy.arc4.UInt64):
        return "uint64"
    if isinstance(arg, algopy.arc4.UInt128):
        return "uint128"
    if isinstance(arg, algopy.arc4.UInt256):
        return "uint256"
    if isinstance(arg, algopy.arc4.UInt512):
        return "uint512"
    if isinstance(arg, algopy.Account):
        return "address"
    if isinstance(arg, algopy.Asset):
        return "asset"
    if isinstance(arg, algopy.Application):
        return "application"
    if isinstance(arg, int):
        return "uint64"
    if isinstance(arg, algopy.arc4.StaticArray):
        item_type = arg._array_item_t
        if item_type is algopy.arc4.Byte:
            size = typing.get_args(arg.__class__)[1]
            return f"byte[{size}]"
    if isinstance(arg, algopy.arc4.DynamicArray | algopy.arc4.StaticArray):
        return f"byte[{arg.bytes.length}][]"  # TODO: fix size calculation
    if arg is None:
        return "void"
    raise ValueError(f"Unsupported type: {type(arg).__name__}")


def _generate_arc4_signature(
    fn: typing.Callable[_P, _R], args: tuple[typing.Any, ...]
) -> algopy.Bytes:
    import algopy

    args_without_txns = [
        arg
        for arg in args
        if not isinstance(arg, algopy.gtxn.TransactionBase)  # type: ignore[arg-type, unused-ignore]
    ]
    arg_types = [
        algosdk.abi.Argument(_map_algopy_type_to_string(arg)) for arg in args_without_txns
    ]
    return_type = algosdk.abi.Returns(_map_algopy_type_to_string(fn.__annotations__.get("return")))
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
                algopy.Bytes() | algopy.String() | algopy.BigUInt() | algopy.UInt64() | int()
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
    context.set_active_transaction_index(len(context.get_transaction_group()) - 1)


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
