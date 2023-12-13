from __future__ import annotations

import abc
import typing

import attrs

from puya.awst import wtypes
from puya.awst.nodes import (
    CheckedMaybe,
    CreateInnerTransaction,
    Expression,
    IntrinsicCall,
    Literal,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
    TupleExpression,
    UInt64Constant,
)
from puya.awst_build import constants
from puya.awst_build.eb.base import (
    ExpressionBuilder,
    IntermediateExpressionBuilder,
    TypeClassExpressionBuilder,
    ValueExpressionBuilder,
)
from puya.awst_build.eb.var_factory import var_expression
from puya.awst_build.utils import create_temporary_assignment, expect_operand_wtype
from puya.errors import CodeError

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    import mypy.nodes

    from puya.parse import SourceLocation


@attrs.define
class TxnField:
    python_name: str
    wtype: wtypes.WType
    immediate: str = attrs.field()

    @immediate.default
    def _immediate_factory(self) -> str:
        return "".join(part.capitalize() for part in self.python_name.split("_"))


MemberTypeMap = dict[str, TxnField]

COMMON_CREATE_TRANSACTION_FIELDS = [
    TxnField("sender", wtypes.account_wtype),
    TxnField("fee", wtypes.uint64_wtype),
    TxnField("note", wtypes.bytes_wtype),
    TxnField("rekey_to", wtypes.account_wtype),
]

COMMON_TRANSACTION_FIELDS = [
    *COMMON_CREATE_TRANSACTION_FIELDS,
    TxnField("first_valid", wtypes.uint64_wtype),
    TxnField("first_valid_time", wtypes.uint64_wtype),
    TxnField("last_valid", wtypes.uint64_wtype),
    TxnField("lease", wtypes.bytes_wtype),
    TxnField("type_bytes", wtypes.bytes_wtype, immediate="Type"),
    TxnField("type", wtypes.uint64_wtype, immediate="TypeEnum"),
    TxnField("group_index", wtypes.uint64_wtype),
    TxnField("txn_id", wtypes.bytes_wtype, immediate="TxID"),
]


def _to_map(*fields: TxnField) -> MemberTypeMap:
    return {f.python_name: f for f in fields}


class _TransactionExpressionBuilder(ValueExpressionBuilder, abc.ABC):
    transaction_fields_mapping: typing.ClassVar[MemberTypeMap]

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        try:
            field = self.transaction_fields_mapping[name]
        except KeyError:
            pass
        else:
            return self.gtxns(field.immediate, field.wtype, location)
        return super().member_access(name, location)

    def gtxns(
        self, immediate: str, wtype: wtypes.WType, location: SourceLocation
    ) -> ExpressionBuilder:
        return var_expression(
            IntrinsicCall(
                source_location=location,
                wtype=wtype,
                op_code="gtxns",
                immediates=[immediate],
                stack_args=[self.expr],
            )
        )


def check_transaction_type(
    transaction_index: Expression,
    expected_transaction_type: wtypes.WTransaction,
    location: SourceLocation,
) -> Expression:
    if expected_transaction_type.transaction_type is None:
        return transaction_index
    transaction_index_tmp = create_temporary_assignment(
        transaction_index,
        location,
    )
    return ReinterpretCast(
        source_location=location,
        wtype=expected_transaction_type,
        expr=CheckedMaybe(
            TupleExpression.from_items(
                (
                    transaction_index_tmp.define,
                    NumericComparisonExpression(
                        lhs=IntrinsicCall(
                            op_code="gtxns",
                            immediates=["TypeEnum"],
                            stack_args=[transaction_index_tmp.read],
                            wtype=wtypes.uint64_wtype,
                            source_location=location,
                        ),
                        operator=NumericComparison.eq,
                        rhs=UInt64Constant(
                            value=expected_transaction_type.transaction_type.value,
                            teal_alias=expected_transaction_type.transaction_type.name,
                            source_location=location,
                        ),
                        source_location=location,
                    ),
                ),
                location,
            ),
            comment=f"transaction type is {expected_transaction_type.transaction_type.name}",
        ),
    )


class _TransactionClassExpressionBuilder(TypeClassExpressionBuilder, abc.ABC):
    expression_builder_type: type[_TransactionExpressionBuilder]

    @property
    def wtype(self) -> wtypes.WType:
        return self.expression_builder_type.wtype

    def produces(self) -> wtypes.WType:
        return self.wtype

    def call(
        self,
        args: typing.Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [ExpressionBuilder() as eb]:
                group_index = expect_operand_wtype(eb, wtypes.uint64_wtype)
            case [Literal(value=int(int_value), source_location=loc)]:
                group_index = UInt64Constant(value=int_value, source_location=loc)
            case _:
                raise CodeError("Invalid/unhandled arguments", location)
        wtype = self.wtype
        txn = (
            check_transaction_type(group_index, wtype, location)
            if isinstance(wtype, wtypes.WTransaction)
            else group_index
        )
        return self.expression_builder_type(txn)


class _TypedTransactionExpressionBuilder(_TransactionExpressionBuilder, abc.ABC):
    wtype: wtypes.WTransaction


class _TypedTransactionClassExpressionBuilder(_TransactionClassExpressionBuilder):
    expression_builder_type: type[_TypedTransactionExpressionBuilder]


class TransactionBaseExpressionBuilder(_TransactionExpressionBuilder):
    wtype: wtypes.WType = wtypes.transaction_base_wtype
    transaction_fields_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_TRANSACTION_FIELDS
    )


class TransactionBaseClassExpressionBuilder(_TransactionClassExpressionBuilder):
    expression_builder_type = TransactionBaseExpressionBuilder


PAYMENT_INNER_TRANSACTION_FIELDS = [
    TxnField("receiver", wtypes.account_wtype),
    TxnField("amount", wtypes.uint64_wtype),
    TxnField("close_remainder_to", wtypes.account_wtype),
]


class PaymentTransactionExpressionBuilder(_TypedTransactionExpressionBuilder):
    wtype = wtypes.payment_wtype
    transaction_fields_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_TRANSACTION_FIELDS,
        *PAYMENT_INNER_TRANSACTION_FIELDS,
    )


class PaymentTransactionClassExpressionBuilder(_TransactionClassExpressionBuilder):
    expression_builder_type = PaymentTransactionExpressionBuilder


class KeyRegistrationTransactionExpressionBuilder(_TypedTransactionExpressionBuilder):
    wtype = wtypes.key_registration_wtype
    transaction_fields_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_TRANSACTION_FIELDS,
        TxnField("vote_key", wtypes.account_wtype, immediate="VotePK"),
        TxnField("selection_key", wtypes.account_wtype, immediate="SelectionPK"),
        TxnField("vote_first", wtypes.uint64_wtype),
        TxnField("vote_last", wtypes.uint64_wtype),
        TxnField("vote_key_dilution", wtypes.uint64_wtype),
        TxnField("non_participation", wtypes.bool_wtype, immediate="Nonparticipation"),
        TxnField("state_proof_key", wtypes.bytes_wtype, immediate="StateProofPK"),
    )


class KeyRegistrationTransactionClassExpressionBuilder(_TransactionClassExpressionBuilder):
    expression_builder_type = KeyRegistrationTransactionExpressionBuilder


ASSET_CONFIG_INNER_TRANSACTION_FIELDS = [
    TxnField("manager", wtypes.account_wtype, immediate="ConfigAssetManager"),
    TxnField("reserve", wtypes.account_wtype, immediate="ConfigAssetReserve"),
    TxnField("freeze", wtypes.account_wtype, immediate="ConfigAssetFreeze"),
    TxnField("clawback", wtypes.account_wtype, immediate="ConfigAssetClawback"),
]

ASSET_CREATE_INNER_TRANSACTION_FIELDS = [
    TxnField("total", wtypes.uint64_wtype, immediate="ConfigAssetTotal"),
    TxnField("decimals", wtypes.uint64_wtype, immediate="ConfigAssetDecimals"),
    TxnField("default_frozen", wtypes.bool_wtype, immediate="ConfigAssetDefaultFrozen"),
    TxnField("unit_name", wtypes.bytes_wtype, immediate="ConfigAssetUnitName"),
    TxnField("asset_name", wtypes.bytes_wtype, immediate="ConfigAssetName"),
    TxnField("url", wtypes.bytes_wtype, immediate="ConfigAssetURL"),
    TxnField("metadata_hash", wtypes.bytes_wtype, immediate="ConfigAssetMetadataHash"),
]


class AssetConfigTransactionExpressionBuilder(_TypedTransactionExpressionBuilder):
    wtype = wtypes.asset_config_wtype
    transaction_fields_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_TRANSACTION_FIELDS,
        TxnField("config_asset", wtypes.asset_wtype),
        *ASSET_CREATE_INNER_TRANSACTION_FIELDS,
        *ASSET_CONFIG_INNER_TRANSACTION_FIELDS,
    )


class AssetConfigTransactionClassExpressionBuilder(_TransactionClassExpressionBuilder):
    expression_builder_type = AssetConfigTransactionExpressionBuilder


ASSET_TRANSFER_INNER_TRANSACTION_FIELDS = [
    TxnField("xfer_asset", wtypes.asset_wtype),
    TxnField("asset_sender", wtypes.account_wtype),
    TxnField("asset_amount", wtypes.uint64_wtype),
    TxnField("asset_receiver", wtypes.account_wtype),
    TxnField("asset_close_to", wtypes.account_wtype),
]


class AssetTransferTransactionExpressionBuilder(_TypedTransactionExpressionBuilder):
    wtype = wtypes.asset_transfer_wtype
    transaction_fields_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_TRANSACTION_FIELDS,
        *ASSET_TRANSFER_INNER_TRANSACTION_FIELDS,
    )


class AssetTransferTransactionClassExpressionBuilder(_TransactionClassExpressionBuilder):
    expression_builder_type = AssetTransferTransactionExpressionBuilder


FREEZE_ASSET_INNER_TRANSACTION_FIELDS = [
    TxnField("freeze_asset", wtypes.asset_wtype),
    TxnField("freeze_account", wtypes.account_wtype, immediate="FreezeAssetAccount"),
    TxnField("frozen", wtypes.bool_wtype, immediate="FreezeAssetFrozen"),
]


class AssetFreezeTransactionExpressionBuilder(_TypedTransactionExpressionBuilder):
    wtype = wtypes.asset_freeze_wtype
    transaction_fields_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_TRANSACTION_FIELDS,
        *FREEZE_ASSET_INNER_TRANSACTION_FIELDS,
    )


class AssetFreezeTransactionClassExpressionBuilder(_TransactionClassExpressionBuilder):
    expression_builder_type = AssetFreezeTransactionExpressionBuilder


class ApplicationCallTransactionArrayExpressionBuilder(IntermediateExpressionBuilder):
    def __init__(
        self,
        transaction: Expression,
        immediate: str,
        wtype: wtypes.WType,
        location: SourceLocation,
    ):
        super().__init__(location)
        self.transaction = transaction
        self.immediate = immediate
        self.wtype = wtype

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        match args:
            case [(ExpressionBuilder() | Literal(value=int())) as eb]:
                index_expr = expect_operand_wtype(eb, wtypes.uint64_wtype)
                return var_expression(
                    IntrinsicCall(
                        source_location=location,
                        wtype=self.wtype,
                        op_code="gtxnsas",
                        immediates=[self.immediate],
                        stack_args=[self.transaction, index_expr],
                    )
                )
            case _:
                raise CodeError("Invalid/unhandled arguments", location)


COMMON_APPLICATION_ARRAY_INNER_TRANSACTION_FIELDS = [
    TxnField("application_args", wtypes.bytes_wtype),
    TxnField("accounts", wtypes.account_wtype),
    TxnField("assets", wtypes.asset_wtype),
    TxnField("applications", wtypes.application_wtype),
]

UPDATE_AND_CREATE_APPLICATION_INNER_TRANSACTION_FIELDS = [
    TxnField("approval_program", wtypes.bytes_wtype),
    TxnField("clear_state_program", wtypes.bytes_wtype),
]

CREATE_APPLICATION_INNER_TRANSACTION_FIELDS = [
    TxnField("global_num_uint", wtypes.uint64_wtype),
    TxnField("global_num_byte_slice", wtypes.uint64_wtype),
    TxnField("local_num_uint", wtypes.uint64_wtype),
    TxnField("local_num_byte_slice", wtypes.uint64_wtype),
    TxnField("extra_program_pages", wtypes.uint64_wtype),
]
on_completion_field = TxnField("on_completion", wtypes.uint64_wtype)
application_id_field = TxnField(
    "application_id", wtypes.application_wtype, immediate="ApplicationID"
)


class ApplicationCallTransactionExpressionBuilder(_TypedTransactionExpressionBuilder):
    wtype = wtypes.application_call_wtype
    transaction_fields_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_TRANSACTION_FIELDS,
        *UPDATE_AND_CREATE_APPLICATION_INNER_TRANSACTION_FIELDS,
        *CREATE_APPLICATION_INNER_TRANSACTION_FIELDS,
        application_id_field,
        on_completion_field,
        TxnField("num_app_args", wtypes.uint64_wtype),
        TxnField("num_accounts", wtypes.uint64_wtype),
        TxnField("num_assets", wtypes.uint64_wtype),
        TxnField("num_applications", wtypes.uint64_wtype),
        TxnField("last_log", wtypes.bytes_wtype),
        TxnField("num_approval_program_pages", wtypes.uint64_wtype),
        TxnField("num_clear_state_program_pages", wtypes.uint64_wtype),
    )
    transaction_array_method_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_APPLICATION_ARRAY_INNER_TRANSACTION_FIELDS,
        TxnField("approval_program_pages", wtypes.bytes_wtype),
        TxnField("clear_state_program_pages", wtypes.bytes_wtype),
    )

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        try:
            field = self.transaction_array_method_mapping[name]
        except KeyError:
            pass
        else:
            return ApplicationCallTransactionArrayExpressionBuilder(
                self.expr, field.immediate, field.wtype, location
            )
        return super().member_access(name, location)


class ApplicationCallTransactionClassExpressionBuilder(_TransactionClassExpressionBuilder):
    expression_builder_type = ApplicationCallTransactionExpressionBuilder


class CreateInnerTransactionExpressionBuilder(IntermediateExpressionBuilder, abc.ABC):
    keyword_mapping: typing.ClassVar[MemberTypeMap]
    wtype: wtypes.WType
    function_name: str
    transaction_type: constants.TransactionType
    result_field: str | None = None

    def get_transaction_fields(
        self, arg_name: str, arg: ExpressionBuilder | Literal
    ) -> list[tuple[str, Expression]]:
        try:
            field = self.keyword_mapping[arg_name]
        except KeyError as ex:
            raise CodeError(
                f"{arg_name} is not a valid keyword argument", arg.source_location
            ) from ex
        field_expr = expect_operand_wtype(arg, field.wtype)
        return [(field.immediate, field_expr)]

    def call(
        self,
        args: Sequence[ExpressionBuilder | Literal],
        arg_kinds: list[mypy.nodes.ArgKind],
        arg_names: list[str | None],
        location: SourceLocation,
        original_expr: mypy.nodes.CallExpr,
    ) -> ExpressionBuilder:
        transaction_fields: list[tuple[str, Expression]] = []
        for arg_name, arg in zip(arg_names, args, strict=True):
            if arg_name is None:
                raise CodeError(
                    f"Positional arguments are not supported for {self.function_name}", location
                )
            transaction_fields.extend(self.get_transaction_fields(arg_name, arg))
        return var_expression(
            CreateInnerTransaction(
                transaction_type=UInt64Constant(
                    source_location=location,
                    value=self.transaction_type.value,
                    teal_alias=self.transaction_type.name,
                ),
                wtype=self.wtype,
                fields=transaction_fields,
                result_field=self.result_field,
                source_location=location,
            )
        )


class CreatePaymentInnerTransactionExpressionBuilder(CreateInnerTransactionExpressionBuilder):
    keyword_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_CREATE_TRANSACTION_FIELDS,
        *PAYMENT_INNER_TRANSACTION_FIELDS,
    )
    wtype = wtypes.void_wtype
    function_name: str = "payment_txn"
    transaction_type = constants.TransactionType.pay


class CreateAssetInnerTransactionExpressionBuilder(CreateInnerTransactionExpressionBuilder):
    keyword_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_CREATE_TRANSACTION_FIELDS,
        *ASSET_CREATE_INNER_TRANSACTION_FIELDS,
        *ASSET_CONFIG_INNER_TRANSACTION_FIELDS,
    )
    wtype = wtypes.asset_wtype
    function_name: str = "create_asset_txn"
    transaction_type = constants.TransactionType.acfg
    result_field = "CreatedAssetID"


class ConfigAssetInnerTransactionExpressionBuilder(CreateInnerTransactionExpressionBuilder):
    keyword_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_CREATE_TRANSACTION_FIELDS,
        TxnField("config_asset", wtypes.asset_wtype),
        *ASSET_CONFIG_INNER_TRANSACTION_FIELDS,
    )
    wtype = wtypes.void_wtype
    function_name: str = "config_asset_txn"
    transaction_type = constants.TransactionType.acfg


class FreezeAssetInnerTransactionExpressionBuilder(CreateInnerTransactionExpressionBuilder):
    keyword_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_CREATE_TRANSACTION_FIELDS,
        *FREEZE_ASSET_INNER_TRANSACTION_FIELDS,
    )
    wtype = wtypes.void_wtype
    function_name: str = "freeze_asset_txn"
    transaction_type = constants.TransactionType.afrz


class TransferAssetInnerTransactionExpressionBuilder(CreateInnerTransactionExpressionBuilder):
    keyword_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_CREATE_TRANSACTION_FIELDS,
        *ASSET_TRANSFER_INNER_TRANSACTION_FIELDS,
    )
    wtype = wtypes.void_wtype
    function_name: str = "transfer_asset_txn"
    transaction_type = constants.TransactionType.axfer


class _ApplicationInnerTransactionExpressionBuilder(CreateInnerTransactionExpressionBuilder):
    keyword_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_CREATE_TRANSACTION_FIELDS,
        *UPDATE_AND_CREATE_APPLICATION_INNER_TRANSACTION_FIELDS,
        *CREATE_APPLICATION_INNER_TRANSACTION_FIELDS,
    )
    array_keyword_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_APPLICATION_ARRAY_INNER_TRANSACTION_FIELDS,
    )
    transaction_type = constants.TransactionType.appl

    def get_transaction_fields(
        self, arg_name: str, arg: ExpressionBuilder | Literal
    ) -> list[tuple[str, Expression]]:
        try:
            field = self.array_keyword_mapping[arg_name]
        except KeyError:
            return super().get_transaction_fields(arg_name, arg)

        match arg:
            case ValueExpressionBuilder(
                expr=TupleExpression() as expr, wtype=wtypes.WTuple(types=tuple_item_types)
            ) if all(t == field.wtype for t in tuple_item_types):
                return [
                    (field.immediate, expect_operand_wtype(item, field.wtype))
                    for item in expr.items
                ]

        raise CodeError(f"{arg_name} should be of type tuple[{field.wtype.stub_name}, ...]")


class CreateCreateApplicationInnerTransactionExpressionBuilder(
    _ApplicationInnerTransactionExpressionBuilder
):
    keyword_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_CREATE_TRANSACTION_FIELDS,
        *UPDATE_AND_CREATE_APPLICATION_INNER_TRANSACTION_FIELDS,
        *CREATE_APPLICATION_INNER_TRANSACTION_FIELDS,
        on_completion_field,
    )
    wtype = wtypes.application_wtype
    function_name: str = "create_application_txn"
    result_field = "CreatedApplicationID"


class CreateUpdateApplicationInnerTransactionExpressionBuilder(
    _ApplicationInnerTransactionExpressionBuilder
):
    keyword_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_CREATE_TRANSACTION_FIELDS,
        *UPDATE_AND_CREATE_APPLICATION_INNER_TRANSACTION_FIELDS,
        application_id_field,
    )
    wtype = wtypes.void_wtype
    function_name: str = "update_application_txn"


class CreateCallApplicationInnerTransactionExpressionBuilder(
    _ApplicationInnerTransactionExpressionBuilder
):
    keyword_mapping: typing.ClassVar[MemberTypeMap] = _to_map(
        *COMMON_CREATE_TRANSACTION_FIELDS,
        application_id_field,
        on_completion_field,
    )
    wtype = wtypes.void_wtype
    function_name: str = "call_application_txn"
