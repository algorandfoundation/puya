from __future__ import annotations

import abc
import typing

from puya.awst import wtypes
from puya.awst.nodes import (
    CheckedMaybe,
    Expression,
    IntrinsicCall,
    Literal,
    NumericComparison,
    NumericComparisonExpression,
    ReinterpretCast,
    TupleExpression,
    UInt64Constant,
)
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

MemberTypeMap = dict[str, tuple[str, wtypes.WType]]

COMMON_TRANSACTION_FIELDS: MemberTypeMap = {
    "sender": ("Sender", wtypes.account_wtype),
    "fee": ("Fee", wtypes.uint64_wtype),
    "first_valid": ("FirstValid", wtypes.uint64_wtype),
    "first_valid_time": ("FirstValidTime", wtypes.uint64_wtype),
    "last_valid": ("LastValid", wtypes.uint64_wtype),
    "note": ("Note", wtypes.bytes_wtype),
    "lease": ("Lease", wtypes.bytes_wtype),
    "type_bytes": ("Type", wtypes.bytes_wtype),
    "type": ("TypeEnum", wtypes.uint64_wtype),
    "group_index": ("GroupIndex", wtypes.uint64_wtype),
    "txn_id": ("TxID", wtypes.bytes_wtype),
    "rekey_to": ("RekeyTo", wtypes.account_wtype),
}


class _TransactionExpressionBuilder(ValueExpressionBuilder, abc.ABC):
    transaction_fields_mapping: typing.ClassVar[MemberTypeMap]

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        try:
            immediate, wtype = self.transaction_fields_mapping[name]
        except KeyError:
            pass
        else:
            return self.gtxns(immediate, wtype, location)
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
    transaction_fields_mapping: typing.ClassVar[MemberTypeMap] = COMMON_TRANSACTION_FIELDS


class TransactionBaseClassExpressionBuilder(_TransactionClassExpressionBuilder):
    expression_builder_type = TransactionBaseExpressionBuilder


class PaymentTransactionExpressionBuilder(_TypedTransactionExpressionBuilder):
    wtype = wtypes.payment_wtype
    transaction_fields_mapping: typing.ClassVar[MemberTypeMap] = {
        **COMMON_TRANSACTION_FIELDS,
        "receiver": ("Receiver", wtypes.account_wtype),
        "amount": ("Amount", wtypes.uint64_wtype),
        "close_remainder_to": ("CloseRemainderTo", wtypes.account_wtype),
    }


class PaymentTransactionClassExpressionBuilder(_TransactionClassExpressionBuilder):
    expression_builder_type = PaymentTransactionExpressionBuilder


class KeyRegistrationTransactionExpressionBuilder(_TypedTransactionExpressionBuilder):
    wtype = wtypes.key_registration_wtype
    transaction_fields_mapping: typing.ClassVar[MemberTypeMap] = {
        **COMMON_TRANSACTION_FIELDS,
        "vote_key": ("VotePK", wtypes.account_wtype),
        "selection_key": ("SelectionPK", wtypes.account_wtype),
        "vote_first": ("VoteFirst", wtypes.uint64_wtype),
        "vote_last": ("VoteLast", wtypes.uint64_wtype),
        "vote_key_dilution": ("VoteKeyDilution", wtypes.uint64_wtype),
        "non_participation": ("Nonparticipation", wtypes.bool_wtype),
        "state_proof_key": ("StateProofPK", wtypes.bytes_wtype),
    }


class KeyRegistrationTransactionClassExpressionBuilder(_TransactionClassExpressionBuilder):
    expression_builder_type = KeyRegistrationTransactionExpressionBuilder


class AssetConfigTransactionExpressionBuilder(_TypedTransactionExpressionBuilder):
    wtype = wtypes.asset_config_wtype
    transaction_fields_mapping: typing.ClassVar[MemberTypeMap] = {
        **COMMON_TRANSACTION_FIELDS,
        "config_asset": ("ConfigAsset", wtypes.uint64_wtype),
        "total": ("ConfigAssetTotal", wtypes.uint64_wtype),
        "decimals": ("ConfigAssetDecimals", wtypes.uint64_wtype),
        "default_frozen": ("ConfigAssetDefaultFrozen", wtypes.bool_wtype),
        "unit_name": ("ConfigAssetUnitName", wtypes.bytes_wtype),
        "asset_name": ("ConfigAssetName", wtypes.bytes_wtype),
        "url": ("ConfigAssetURL", wtypes.bytes_wtype),
        "metadata_hash": ("ConfigAssetMetadataHash", wtypes.bytes_wtype),
        "manager": ("ConfigAssetManager", wtypes.account_wtype),
        "reserve": ("ConfigAssetReserve", wtypes.account_wtype),
        "freeze": ("ConfigAssetFreeze", wtypes.account_wtype),
        "clawback": ("ConfigAssetClawback", wtypes.account_wtype),
    }


class AssetConfigTransactionClassExpressionBuilder(_TransactionClassExpressionBuilder):
    expression_builder_type = AssetConfigTransactionExpressionBuilder


class AssetTransferTransactionExpressionBuilder(_TypedTransactionExpressionBuilder):
    wtype = wtypes.asset_transfer_wtype
    transaction_fields_mapping: typing.ClassVar[MemberTypeMap] = {
        **COMMON_TRANSACTION_FIELDS,
        "xfer_asset": ("XferAsset", wtypes.asset_wtype),
        "asset_amount": ("AssetAmount", wtypes.uint64_wtype),
        "asset_sender": ("AssetSender", wtypes.account_wtype),
        "asset_receiver": ("AssetReceiver", wtypes.account_wtype),
        "asset_close_to": ("AssetCloseTo", wtypes.account_wtype),
    }


class AssetTransferTransactionClassExpressionBuilder(_TransactionClassExpressionBuilder):
    expression_builder_type = AssetTransferTransactionExpressionBuilder


class AssetFreezeTransactionExpressionBuilder(_TypedTransactionExpressionBuilder):
    wtype = wtypes.asset_freeze_wtype
    transaction_fields_mapping: typing.ClassVar[MemberTypeMap] = {
        **COMMON_TRANSACTION_FIELDS,
        "freeze_asset": ("FreezeAsset", wtypes.uint64_wtype),
        "freeze_account": ("FreezeAssetAccount", wtypes.account_wtype),
        "frozen": ("FreezeAssetFrozen", wtypes.bool_wtype),
    }


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


class ApplicationCallTransactionExpressionBuilder(_TypedTransactionExpressionBuilder):
    wtype = wtypes.application_call_wtype
    transaction_fields_mapping: typing.ClassVar[MemberTypeMap] = {
        **COMMON_TRANSACTION_FIELDS,
        "application_id": ("ApplicationID", wtypes.uint64_wtype),
        "on_completion": ("OnCompletion", wtypes.uint64_wtype),
        "num_app_args": ("NumAppArgs", wtypes.uint64_wtype),
        "num_accounts": ("NumAccounts", wtypes.uint64_wtype),
        "approval_program": ("ApprovalProgram", wtypes.bytes_wtype),
        "clear_state_program": ("ClearStateProgram", wtypes.bytes_wtype),
        "num_assets": ("NumAssets", wtypes.uint64_wtype),
        "num_applications": ("NumApplications", wtypes.uint64_wtype),
        "global_num_uint": ("GlobalNumUint", wtypes.uint64_wtype),
        "global_num_byte_slice": ("GlobalNumByteSlice", wtypes.uint64_wtype),
        "local_num_uint": ("LocalNumUint", wtypes.uint64_wtype),
        "local_num_byte_slice": ("LocalNumByteSlice", wtypes.uint64_wtype),
        "extra_program_pages": ("ExtraProgramPages", wtypes.uint64_wtype),
        "last_log": ("LastLog", wtypes.bytes_wtype),
        "num_approval_program_pages": ("NumApprovalProgramPages", wtypes.uint64_wtype),
        "num_clear_state_program_pages": ("NumClearStateProgramPages", wtypes.uint64_wtype),
    }
    transaction_array_method_mapping: typing.ClassVar[MemberTypeMap] = {
        "application_args": ("ApplicationArgs", wtypes.bytes_wtype),
        "accounts": ("Accounts", wtypes.account_wtype),
        "assets": ("Assets", wtypes.asset_wtype),
        "applications": ("Applications", wtypes.application_wtype),
        "approval_program_pages": ("ApprovalProgramPages", wtypes.bytes_wtype),
        "clear_state_program_pages": ("ClearStateProgramPages", wtypes.bytes_wtype),
    }

    def member_access(self, name: str, location: SourceLocation) -> ExpressionBuilder | Literal:
        try:
            immediate, wtype = self.transaction_array_method_mapping[name]
        except KeyError:
            pass
        else:
            return ApplicationCallTransactionArrayExpressionBuilder(
                self.expr, immediate, wtype, location
            )
        return super().member_access(name, location)


class ApplicationCallTransactionClassExpressionBuilder(_TransactionClassExpressionBuilder):
    expression_builder_type = ApplicationCallTransactionExpressionBuilder
