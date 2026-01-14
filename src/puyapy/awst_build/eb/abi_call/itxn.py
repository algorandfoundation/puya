import typing
from collections.abc import Mapping, Sequence

from puya import log
from puya.avm import OnCompletionAction
from puya.awst.nodes import (
    ABICall,
    ARC4CreateOption,
    ARC4MethodConfig,
    Expression,
    SubmitInnerTransaction,
    VoidConstant,
)
from puya.awst.txn_fields import TxnField
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._base import FunctionBuilder
from puyapy.awst_build.eb.abi_call._utils import (
    get_on_completion,
    is_creating,
    parse_abi_call_args,
)
from puyapy.awst_build.eb.arc4._base import ARC4FromLogBuilder
from puyapy.awst_build.eb.factories import builder_for_instance
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
)
from puyapy.awst_build.eb.none import NoneExpressionBuilder
from puyapy.awst_build.eb.transaction.inner import InnerTransactionExpressionBuilder
from puyapy.awst_build.eb.transaction.inner_params import InnerTxnParamsExpressionBuilder

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
        self._result_type = pytype.result_type
        super().__init__(pytype, expr)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name == "submit":
            return _Submit(self, self._result_type, location)

        return super().member_access(name, location)


class ABIApplicationCallInnerTransactionExpressionBuilder(InnerTransactionExpressionBuilder):
    def __init__(self, expr: Expression, pytype: pytypes.PyType):
        assert isinstance(pytype, pytypes.ABIApplicationCallInnerTransaction)
        self._result_type = pytype.result_type
        super().__init__(expr, pytype)

    @typing.override
    def member_access(self, name: str, location: SourceLocation) -> NodeBuilder:
        if name == "result":
            result_type = self._result_type
            if result_type == pytypes.NoneType:
                return NoneExpressionBuilder(VoidConstant(location))

            last_log = self.get_field_value(TxnField.LastLog, pytypes.BytesType, location)
            abi_result = ARC4FromLogBuilder.abi_expr_from_log(result_type, last_log, location)

            return builder_for_instance(result_type, abi_result)

        return super().member_access(name, location)


class _Submit(FunctionBuilder):
    def __init__(
        self,
        base: ABIApplicationCallExpressionBuilder,
        result_type: pytypes.PyType,
        location: SourceLocation,
    ) -> None:
        self.base = base
        self._result_type = result_type
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

        expr = self.base.resolve()

        result_transaction_type = pytypes.GenericABIApplicationCallInnerTransaction.parameterise(
            [self._result_type], location
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
    parsed = parse_abi_call_args(
        args,
        arg_names,
        _ABI_CALL_TRANSACTION_FIELDS,
        return_type_annotation,
        _validate_transaction_kwargs,
        location,
    )

    pytype = pytypes.GenericABIApplicationCall.parameterise(
        [parsed.declared_return_type], location
    )

    expr = ABICall(
        target=parsed.target,
        args=parsed.abi_call_args,
        fields=parsed.fields,
        wtype=pytype.wtype,
        source_location=location,
    )
    return builder_for_instance(pytype, expr)


def _validate_transaction_kwargs(
    field_nodes: Mapping[TxnField, NodeBuilder],
    arc4_config: ARC4MethodConfig | None,
    method_location: SourceLocation,
    call_location: SourceLocation,
) -> None:
    # note these values may be None which indicates their value is unknown at compile time
    on_completion = get_on_completion(field_nodes, arc4_config)
    is_update = on_completion == OnCompletionAction.UpdateApplication
    is_create = is_creating(field_nodes)

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
