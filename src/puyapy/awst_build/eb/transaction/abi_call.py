import typing
from collections.abc import Sequence, Set

from puya import log
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
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puyapy.awst_build.eb.subroutine import BaseClassSubroutineInvokerExpressionBuilder
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


class ABICallExpressionBuilder(FunctionBuilder):
    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        method, abi_args, kwargs = _get_method_abi_args_and_kwargs(
            args, arg_names, _get_python_kwargs(_ABI_CALL_TRANSACTION_FIELDS)
        )
        pytype = pytypes.ABIApplicationCall
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
            expect.instance_builder(arg, default=expect.default_raise).resolve()
            for arg in abi_args
        ]
        return builder_for_instance(
            pytype,
            ABICall(
                target=target,
                args=abi_call_args,
                fields=fields,
                source_location=location,
                wtype=pytype.wtype,
            ),
        )


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
