import typing
from collections.abc import Sequence, Set

from puya import log
from puya.awst.nodes import (
    ABICall,
    Expression,
    MethodSignature,
    MethodSignatureString,
    SubmitInnerTransaction,
    VoidConstant,
)
from puya.awst.txn_fields import TxnField
from puya.awst.wtypes import WInnerTransactionFields
from puya.errors import CodeError
from puya.parse import SourceLocation
from puya.utils import StableSet
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb.arc4._base import ARC4FromLogBuilder
from puyapy.awst_build.eb.arc4_client import ARC4ClientMethodExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import InstanceBuilder, NodeBuilder
from puyapy.awst_build.eb.none import NoneExpressionBuilder
from puyapy.awst_build.eb.subroutine import BaseClassSubroutineInvokerExpressionBuilder
from puyapy.awst_build.eb.transaction.inner import InnerTransactionExpressionBuilder
from puyapy.awst_build.eb.transaction.inner_params import InnerTxnParamsExpressionBuilder
from puyapy.awst_build.eb.transaction.itxn_args import PYTHON_ITXN_ARGUMENTS
from puyapy.awst_build.eb.tuple import TupleLiteralBuilder
from puyapy.awst_build.utils import maybe_resolve_literal_as_native_type

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
            if result_type == pytypes.NoneType:
                return NoneExpressionBuilder(VoidConstant(location))

            expr = self.single_eval()
            assert isinstance(expr, InnerTransactionExpressionBuilder)

            last_log = expr.get_field_value(TxnField.LastLog, pytypes.BytesType, location)
            abi_result = ARC4FromLogBuilder.abi_expr_from_log(result_type, last_log, location)

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

    return_type: pytypes.PyType | None = None
    match method:
        case None:
            raise CodeError("missing required positional argument 'method'", location)
        case (
            ARC4ClientMethodExpressionBuilder(method=fmethod)
            | BaseClassSubroutineInvokerExpressionBuilder(method=fmethod)
        ):
            if fmethod.metadata is None:
                raise CodeError("method is not an ARC-4 method", location=location)

            abi_method_data = fmethod.metadata
            if isinstance(abi_method_data, models.ARC4ABIMethodData):
                name = abi_method_data.config.name
                arg_types = abi_method_data.argument_types
                return_type = abi_method_data.return_type
                resource_encoding = abi_method_data.config.resource_encoding
                allowed_completion_types = abi_method_data.config.allowed_completion_types
            else:
                name = fmethod.member_name
                arg_types = []
                return_type = pytypes.NoneType
                resource_encoding = "value"
                allowed_completion_types = []

            target: MethodSignatureString | MethodSignature = MethodSignature(
                name=name,
                arg_types=[t.checked_wtype(location) for t in arg_types],
                return_type=return_type.checked_wtype(location),
                resource_encoding=resource_encoding,
                allowed_completion_types=allowed_completion_types,
                source_location=args[0].source_location,
            )
        case _:
            method_str = expect.simple_string_literal(method, default=expect.default_raise)
            target = MethodSignatureString(
                value=method_str, source_location=method.source_location
            )

    field_nodes = {PYTHON_ITXN_ARGUMENTS[kwarg].field: node for kwarg, node in kwargs.items()}
    fields: dict[TxnField, Expression] = {}
    for field, field_node in field_nodes.items():
        params = _FIELD_TO_ITXN_ARGUMENT[field]
        if params is None:
            logger.error("unrecognised keyword argument", location=field_node.source_location)
        else:
            fields[field] = params.validate_and_convert(field_node).resolve()

    abi_call_args = [
        _maybe_resolve_literal(arg).resolve()
        for arg in [expect.instance_builder(arg, default=expect.default_raise) for arg in abi_args]
    ]

    if return_type_annotation is None:
        return_type_annotation = return_type or pytypes.NoneType

    pytype = pytypes.GenericABIApplicationCall.parameterise([return_type_annotation], location)

    abi_call_wtype = pytype.checked_wtype(location)
    assert isinstance(abi_call_wtype, WInnerTransactionFields)

    expr = ABICall(
        target=target,
        args=abi_call_args,
        fields=fields,
        wtype=abi_call_wtype,
        source_location=location,
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


def _maybe_resolve_literal(operand: InstanceBuilder) -> InstanceBuilder:
    if isinstance(operand, TupleLiteralBuilder):
        resolved_items = [_maybe_resolve_literal(elem) for elem in operand.iterate_static()]
        return TupleLiteralBuilder(resolved_items, operand.source_location)
    return maybe_resolve_literal_as_native_type(operand)
