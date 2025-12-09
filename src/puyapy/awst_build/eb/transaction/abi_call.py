import typing
from collections.abc import Sequence, Set

from puya import log
from puya.avm import TransactionType
from puya.awst.nodes import ABICall, ContractMethod, Expression
from puya.awst.txn_fields import TxnField
from puya.errors import CodeError
from puya.parse import SourceLocation
from puya.utils import StableSet
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb.arc4_client import ARC4ClientMethodExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder, TypeBuilder
from puyapy.awst_build.eb.subroutine import BaseClassSubroutineInvokerExpressionBuilder
from puyapy.awst_build.eb.transaction.inner_params import InnerTxnParamsExpressionBuilder
from puyapy.awst_build.eb.transaction.itxn_args import PYTHON_ITXN_ARGUMENTS

logger = log.get_logger(__name__)

_ABI_CALL_TRANSACTION_FIELDS = [
    TxnField.ApplicationID,
    TxnField.OnCompletion,
    TxnField.Fee,
    TxnField.Sender,
    TxnField.Note,
    TxnField.RekeyTo,
    TxnField.RejectVersion,
]
_FIELD_TO_ITXN_ARGUMENT = {arg.field: arg for arg in PYTHON_ITXN_ARGUMENTS.values()}


class ABICallGenericTypeBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _abi_call(args, arg_names, location, return_type_annotation=pytypes.NoneType)


class ABICallTypeBuilder(FunctionBuilder):
    def __init__(self, typ: pytypes.PyType, location: SourceLocation):
        assert isinstance(typ, pytypes.PseudoGenericFunctionType)
        self._return_type_annotation = typ.return_type
        super().__init__(location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        return _abi_call(
            args, arg_names, location, return_type_annotation=self._return_type_annotation
        )


class ABIApplicationCallInnerTransactionTypeBuilder(TypeBuilder):
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        raise CodeError(
            "cannot directly instantiate ABIApplicationCallInnerTransaction; "
            "use itxn.abi_call(...) instead",
            location,
        )


# class ABIApplicationCallInnerTransactionExpressionBuilder(InnerTransactionExpressionBuilder):
#     def __init__(self, expr: Expression):
#         super().__init__(expr, pytypes.ABIApplicationCallInnerTransaction())

#     @typing.override
#     def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
#         return super().member_access(name, location)


class ABIApplicationCallExpressionBuilder(InnerTxnParamsExpressionBuilder):
    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        return super().member_access(name, location)


def _abi_call(
    args: Sequence[NodeBuilder],
    arg_names: list[str | None],
    location: SourceLocation,
    *,
    return_type_annotation: pytypes.PyType,
) -> InstanceBuilder:
    method, abi_args, kwargs = _get_method_abi_args_and_kwargs(
        args, arg_names, _get_python_kwargs(_ABI_CALL_TRANSACTION_FIELDS)
    )
    if return_type_annotation is pytypes.NoneType:
        pytype = pytypes.InnerTransactionFieldsetTypes[TransactionType.appl]
    else:
        pytype = pytypes.ABIApplicationCall(return_type=return_type_annotation)

    match method:
        case None:
            raise CodeError("missing required positional argument 'method'", location)
        case (
            ARC4ClientMethodExpressionBuilder(method=fmethod)
            | BaseClassSubroutineInvokerExpressionBuilder(method=fmethod)
        ):
            target: ContractMethod | str | None = fmethod.implementation
        case _:
            target = expect.simple_string_literal(method, default=expect.default_raise)

    if target is None:
        raise CodeError("ABI method target is not known at compile time", location)

    field_nodes = {PYTHON_ITXN_ARGUMENTS[kwarg].field: node for kwarg, node in kwargs.items()}
    fields: dict[TxnField, Expression] = {}
    for field, field_node in field_nodes.items():
        params = _FIELD_TO_ITXN_ARGUMENT[field]
        if params is None:
            logger.error("unrecognised keyword argument", location=field_node.source_location)
        else:
            fields[field] = params.validate_and_convert(field_node).resolve()

    abi_call_args = [
        expect.instance_builder(arg, default=expect.default_raise).resolve() for arg in abi_args
    ]
    expr = ABICall(
        target=target,
        args=abi_call_args,
        fields=fields,
        source_location=location,
        return_type=return_type_annotation.checked_wtype(location),
        wtype=pytype.wtype,
    )
    if return_type_annotation is pytypes.NoneType:
        return builder_for_instance(pytype, expr)
    else:
        return ABIApplicationCallExpressionBuilder(pytype, expr)


def _get_method_abi_args_and_kwargs(
    args: Sequence[NodeBuilder], arg_names: list[str | None], allowed_kwargs: Set[str]
) -> tuple[NodeBuilder | None, Sequence[NodeBuilder], dict[str, NodeBuilder]]:
    method: NodeBuilder | None = None
    abi_args = list[NodeBuilder]()
    kwargs = dict[str, NodeBuilder]()
    for idx, (arg_name, arg) in enumerate(zip(arg_names, args, strict=True)):
        if arg_name is None:
            if idx == 0:
                method = arg
            else:
                abi_args.append(arg)
        elif arg_name in allowed_kwargs:
            kwargs[arg_name] = arg
        else:
            logger.error("unrecognised keyword argument", location=arg.source_location)
    return method, abi_args, kwargs


def _get_python_kwargs(fields: Sequence[TxnField]) -> Set[str]:
    return StableSet.from_iter(
        arg for arg, param in PYTHON_ITXN_ARGUMENTS.items() if param.field in fields
    )
