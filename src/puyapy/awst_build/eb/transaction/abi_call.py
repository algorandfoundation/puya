import typing
from collections.abc import Mapping, Sequence, Set

from puya import log
from puya.avm import OnCompletionAction
from puya.awst.nodes import (
    ABICall,
    ARC4CreateOption,
    ARC4MethodConfig,
    Expression,
    IntegerConstant,
    MethodSignature,
    SubmitInnerTransaction,
    VoidConstant,
)
from puya.awst.txn_fields import TxnField
from puya.awst.wtypes import WInnerTransactionFields
from puya.errors import CodeError
from puya.ir.builder._utils import method_signature_to_abi_signature
from puya.parse import SourceLocation
from puya.utils import StableSet
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.arc4_utils import arc4_to_pytype
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb.arc4._base import ARC4FromLogBuilder
from puyapy.awst_build.eb.arc4._utils import split_arc4_signature
from puyapy.awst_build.eb.arc4_client import ARC4ClientMethodExpressionBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import InstanceBuilder, LiteralBuilder, NodeBuilder
from puyapy.awst_build.eb.none import NoneExpressionBuilder
from puyapy.awst_build.eb.subroutine import BaseClassSubroutineInvokerExpressionBuilder
from puyapy.awst_build.eb.transaction.inner import InnerTransactionExpressionBuilder
from puyapy.awst_build.eb.transaction.inner_params import InnerTxnParamsExpressionBuilder
from puyapy.awst_build.eb.transaction.itxn_args import PYTHON_ITXN_ARGUMENTS
from puyapy.awst_build.utils import maybe_resolve_literal

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
    method, pos_args, kwargs = _get_method_abi_args_and_kwargs(
        args, arg_names, _get_python_kwargs(_ABI_CALL_TRANSACTION_FIELDS)
    )

    abi_args = [expect.instance_builder(arg, default=expect.default_raise) for arg in pos_args]
    return_type: pytypes.PyType | None = None

    abi_config = None
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
            abi_config = abi_method_data.config
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

            target = MethodSignature(
                name=name,
                arg_types=[t.checked_wtype(location) for t in arg_types],
                return_type=return_type.checked_wtype(location),
                resource_encoding=resource_encoding,
                allowed_completion_types=allowed_completion_types,
                source_location=args[0].source_location,
            )
        case _:
            sig = split_arc4_signature(method)

            if sig.maybe_args is None:
                arg_types = [
                    _convert_literal_pytype(arg.pytype, arg.source_location) for arg in abi_args
                ]
            else:
                arg_types = [arc4_to_pytype(arg) for arg in sig.maybe_args]
            arg_wtypes = [t.checked_wtype(location) for t in arg_types]

            if return_type_annotation is not None and return_type_annotation != pytypes.NoneType:
                return_type = return_type_annotation
            elif sig.maybe_returns:
                return_type = arc4_to_pytype(sig.maybe_returns)
            else:
                return_type = pytypes.NoneType
            return_wtype = return_type.checked_wtype(location)

            target = MethodSignature(
                name=sig.name,
                arg_types=arg_wtypes,
                return_type=return_wtype,
                source_location=location,
                resource_encoding="index",
            )
            abi_signature = method_signature_to_abi_signature(target)
            if not abi_signature.startswith(sig.value):
                logger.error(
                    f"method selector from args '{abi_signature}' "
                    f"does not match provided method selector: '{sig.value}'",
                    location=method.source_location,
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
        _maybe_resolve_literal(arg, arg_type).resolve()
        for arg, arg_type in zip(abi_args, arg_types, strict=True)
    ]

    if return_type_annotation is None:
        return_type_annotation = return_type or pytypes.NoneType

    pytype = pytypes.GenericABIApplicationCall.parameterise([return_type_annotation], location)

    abi_call_wtype = pytype.checked_wtype(location)
    assert isinstance(abi_call_wtype, WInnerTransactionFields)

    _validate_transaction_kwargs(
        field_nodes,
        abi_config,
        method_location=target.source_location,
        call_location=location,
    )
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


def _convert_literal_pytype(typ: pytypes.PyType, location: SourceLocation) -> pytypes.PyType:
    match typ:
        case pytypes.StrLiteralType:
            return pytypes.StringType
        case pytypes.BytesLiteralType:
            return pytypes.BytesType
        case pytypes.IntLiteralType:
            return pytypes.UInt64Type
        case pytypes.TupleType:
            return pytypes.GenericTupleType.parameterise(
                [_convert_literal_pytype(t, location) for t in typ.items],
                source_location=location,
            )
        case _:
            return typ


def _maybe_resolve_literal(
    operand: InstanceBuilder, target_type: pytypes.PyType
) -> InstanceBuilder:
    """Handles special case of resolving a literal tuple into an arc4 tuple"""
    from puyapy.awst_build.eb.tuple import TupleLiteralBuilder

    if isinstance(operand, TupleLiteralBuilder) and isinstance(target_type, pytypes.TupleLikeType):
        resolved_items = [
            _maybe_resolve_literal(elem, elem_type)
            for elem, elem_type in zip(operand.iterate_static(), target_type.items, strict=True)
        ]
        return TupleLiteralBuilder(resolved_items, operand.source_location)
    return maybe_resolve_literal(operand, target_type)


def _validate_transaction_kwargs(
    field_nodes: Mapping[TxnField, NodeBuilder],
    arc4_config: ARC4MethodConfig | None,
    *,
    method_location: SourceLocation,
    call_location: SourceLocation,
) -> None:
    # note these values may be None which indicates their value is unknown at compile time
    on_completion = _get_on_completion(field_nodes, arc4_config)
    is_update = on_completion == OnCompletionAction.UpdateApplication
    is_create = _is_creating(field_nodes)

    if is_create:
        # app_id not provided but method doesn't support creating
        if arc4_config and arc4_config.create == ARC4CreateOption.disallow:
            logger.error("method cannot be used to create application", location=method_location)
        # required args for creation missing
        else:
            logger.error(
                "use 'arc4.arc4_create' or 'arc4.abi_call' to create application",
                location=call_location,
            )
    if is_update:
        if arc4_config and (
            OnCompletionAction.UpdateApplication not in arc4_config.allowed_completion_types
        ):
            logger.error("method cannot be used to update application", location=method_location)
        else:
            logger.error(
                "use 'arc4.arc4_update' or 'arc4.abi_call' to update application",
                location=call_location,
            )
    # on_completion not valid for arc4_config
    elif (
        on_completion is not None
        and arc4_config
        and on_completion not in arc4_config.allowed_completion_types
    ):
        arg = field_nodes[TxnField.OnCompletion]
        logger.error(
            "on completion action is not supported by ARC-4 method being called",
            location=arg.source_location,
        )
        logger.info("method ARC-4 configuration", location=arc4_config.source_location)


def _get_on_completion(
    field_nodes: Mapping[TxnField, NodeBuilder], arc4_config: ARC4MethodConfig | None
) -> OnCompletionAction | None:
    """
    Returns OnCompletionAction if it is statically known, otherwise returns None
    """
    match field_nodes.get(TxnField.OnCompletion):
        case None:
            if arc4_config:
                return arc4_config.allowed_completion_types[0]
            return OnCompletionAction.NoOp
        case InstanceBuilder(pytype=pytypes.OnCompleteActionType) as eb:
            value = eb.resolve()
            if isinstance(value, IntegerConstant):
                return OnCompletionAction(value.value)
    return None


def _is_creating(field_nodes: Mapping[TxnField, NodeBuilder]) -> bool | None:
    """
    Returns app_id == 0 if app_id is statically known, otherwise returns None
    """
    match field_nodes.get(TxnField.ApplicationID):
        case None:
            return True
        case LiteralBuilder(value=int(app_id)):
            return app_id == 0
    return None
