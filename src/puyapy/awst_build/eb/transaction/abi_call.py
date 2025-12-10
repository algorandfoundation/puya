import typing
from collections.abc import Sequence, Set

from puya import log
from puya.avm import TransactionType
from puya.awst.nodes import (
    ABICall,
    ARC4Decode,
    ContractMethod,
    Expression,
    SubmitInnerTransaction,
)
from puya.awst.txn_fields import TxnField
from puya.errors import CodeError
from puya.parse import SourceLocation
from puya.utils import StableSet
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.arc4_utils import pytype_to_arc4_pytype
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb.arc4._base import ARC4FromLogBuilder
from puyapy.awst_build.eb.arc4_client import ARC4ClientMethodExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puyapy.awst_build.eb.subroutine import BaseClassSubroutineInvokerExpressionBuilder
from puyapy.awst_build.eb.transaction.inner import InnerTransactionExpressionBuilder
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
        return _abi_call(args, arg_names, location)


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


class ABIApplicationCallExpressionBuilder(InnerTxnParamsExpressionBuilder):
    def __init__(self, expr: Expression, pytype: pytypes.PyType):
        assert isinstance(pytype, pytypes.ABIApplicationCall)
        super().__init__(pytype, expr)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name == "submit":
            assert isinstance(self.pytype, pytypes.ABIApplicationCall)
            return _Submit(self, location)

        return super().member_access(name, location)


class ABIApplicationCallInnerTransactionExpressionBuilder(InnerTransactionExpressionBuilder):
    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name == "result":
            assert isinstance(self.pytype, pytypes.ABIApplicationCallInnerTransaction)
            result_type = self.pytype.result_type
            assert result_type is not None

            expr = self.single_eval()
            assert isinstance(expr, InnerTransactionExpressionBuilder)

            def on_error(bad_type: pytypes.PyType, loc_: SourceLocation | None) -> typing.Never:
                raise CodeError(
                    f"not an ARC-4 type or native equivalent: {bad_type}",
                    loc_,
                )

            arc4_return_type = pytype_to_arc4_pytype(
                result_type,
                on_error=on_error,
                encode_resource_types=True,
                source_location=location,
            )
            last_log = expr.get_field_value(TxnField.LastLog, pytypes.BytesType, location)
            abi_result = ARC4FromLogBuilder.abi_expr_from_log(arc4_return_type, last_log, location)

            if result_type != arc4_return_type:
                abi_result = ARC4Decode(
                    value=abi_result,
                    wtype=result_type.checked_wtype(location),
                    source_location=location,
                )
            return builder_for_instance(result_type, abi_result)

        return super().member_access(name, location)


class _Submit(FunctionBuilder):
    def __init__(
        self,
        base: ABIApplicationCallExpressionBuilder,
        location: SourceLocation,
    ) -> None:
        self.base = base
        super().__init__(location)

    @typing.override
    def call(
        self,
        args: Sequence[NodeBuilder],
        arg_kinds: list[models.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
    ) -> InstanceBuilder:
        expect.no_args(args, location)

        assert isinstance(self.base.pytype, pytypes.ABIApplicationCall)
        expr = self.base.resolve()

        result_type = self.base.pytype.result_type
        result_transaction_type = pytypes.GenericABIApplicationCallInnerTransaction.parameterise(
            [result_type], location
        )

        return builder_for_instance(
            result_transaction_type,
            SubmitInnerTransaction(itxns=[expr], source_location=location),
        )


def _abi_call(
    args: Sequence[NodeBuilder],
    arg_names: list[str | None],
    location: SourceLocation,
    *,
    return_type_annotation: pytypes.PyType | None = None,
) -> InstanceBuilder:
    method, abi_args, kwargs = _get_method_abi_args_and_kwargs(
        args, arg_names, _get_python_kwargs(_ABI_CALL_TRANSACTION_FIELDS)
    )

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

    if return_type_annotation is None:
        if (
            isinstance(method, ARC4ClientMethodExpressionBuilder)
            and isinstance(method.method.metadata, models.ARC4ABIMethodData)
            or isinstance(method, BaseClassSubroutineInvokerExpressionBuilder)
            and isinstance(method.method.metadata, models.ARC4ABIMethodData)
        ):
            return_type_annotation = method.method.metadata.return_type
        else:
            return_type_annotation = pytypes.NoneType

    if return_type_annotation is pytypes.NoneType:
        pytype = pytypes.InnerTransactionFieldsetTypes[TransactionType.appl]
    else:
        pytype = pytypes.GenericABIApplicationCall.parameterise([return_type_annotation], location)

    expr = ABICall(
        target=target,
        args=abi_call_args,
        fields=fields,
        source_location=location,
        result_type=return_type_annotation.checked_wtype(location),
        wtype=pytype.wtype,
    )
    return builder_for_instance(pytype, expr)


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
