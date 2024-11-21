from collections.abc import Mapping

import attrs
from immutabledict import immutabledict

from puya import log
from puya.awst.txn_fields import TxnField
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb.bytes import BytesExpressionBuilder
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
    StaticSizedCollectionBuilder,
)
from puyapy.awst_build.eb.tuple import TupleLiteralBuilder
from puyapy.awst_build.utils import resolve_literal

logger = log.get_logger(__name__)


@attrs.frozen(kw_only=True)
class PythonITxnArgument:
    field: TxnField
    type: pytypes.PyType
    """the primary type of the field - will be called to convert literals,
    expect for special cases explicitly overridden in literal_overrides
    for array fields, this is the type of the items"""
    additional_types: tuple[pytypes.PyType, ...] = ()
    """any extra types that are acceptable, will be carried through without validation
    (so don't put literals in here)"""
    literal_overrides: Mapping[pytypes.LiteralOnlyType, pytypes.PyType] = attrs.field(
        converter=immutabledict, factory=immutabledict
    )
    array_promote: bool = False
    """if the field is an array, accept individual arguments and convert to array format"""
    auto_serialize_bytes: bool = False
    """rely on to_bytes() - only valid if the type is pytypes.BytesType"""

    def __attrs_post_init__(self) -> None:
        assert self.field.is_inner_param
        assert self.type not in self.additional_types
        if self.array_promote:
            assert self.field.is_array
        if self.auto_serialize_bytes:
            assert self.type is pytypes.BytesType
            assert not self.additional_types
            assert not self.literal_overrides

    def validate_and_convert(self, builder: NodeBuilder) -> InstanceBuilder:
        if not self.field.is_array:
            dummy_pytype = self.type
        else:
            dummy_pytype = pytypes.GenericTupleType.parameterise(
                [self.type] * self.field.num_values, builder.source_location
            )

        dummy_default = expect.default_dummy_value(dummy_pytype)
        eb = expect.instance_builder(builder, default=dummy_default)
        if not self.field.is_array:
            return self._validate_and_convert_item(eb)
        elif isinstance(eb, StaticSizedCollectionBuilder):
            return TupleLiteralBuilder(
                [self._validate_and_convert_item(item) for item in eb.iterate_static()],
                eb.source_location,
            )
        elif self.array_promote:
            # TODO: split bytes literals >= 4096
            item = self._validate_and_convert_item(eb)
            return TupleLiteralBuilder([item], item.source_location)
        else:
            return expect.argument_of_type(
                eb, pytypes.VariadicTupleType(items=self.type), default=dummy_default
            )

    def _validate_and_convert_item(self, item: InstanceBuilder) -> InstanceBuilder:
        if self.field == TxnField.ApplicationArgs:
            if pytypes.AccountType <= item.pytype:
                logger.warning(
                    f"{item.pytype} will not be added to foreign array,"
                    f" use .bytes to suppress this warning",
                    location=item.source_location,
                )
            elif item.pytype.is_type_or_subtype(pytypes.AssetType, pytypes.ApplicationType):
                logger.warning(
                    f"{item.pytype} will not be added to foreign array,"
                    f" use .id to suppress this warning",
                    location=item.source_location,
                )

        if self.auto_serialize_bytes:
            return BytesExpressionBuilder(item.to_bytes(item.source_location))

        override_literal_type = self.literal_overrides.get(item.pytype)  # type: ignore[call-overload]
        if override_literal_type is not None:
            item = resolve_literal(item, override_literal_type)
        return expect.argument_of_type_else_dummy(
            item, self.type, *self.additional_types, resolve_literal=True
        )


PYTHON_ITXN_ARGUMENTS = {
    # type(:) TransactionType = ...,
    "type": PythonITxnArgument(
        field=TxnField.TypeEnum,
        type=pytypes.TransactionTypeType,
    ),
    # ## payment
    # receiver: Account | str = ...,
    "receiver": PythonITxnArgument(
        field=TxnField.Receiver,
        type=pytypes.AccountType,
    ),
    # amount: UInt64 | int = ...,
    "amount": PythonITxnArgument(
        field=TxnField.Amount,
        type=pytypes.UInt64Type,
    ),
    # close_remainder_to: Account | str = ...,
    "close_remainder_to": PythonITxnArgument(
        field=TxnField.CloseRemainderTo,
        type=pytypes.AccountType,
    ),
    # ## key registration
    # vote_key: Bytes | bytes = ...,
    "vote_key": PythonITxnArgument(
        field=TxnField.VotePK,
        type=pytypes.BytesType,
    ),
    # selection_key: Bytes | bytes = ...,
    "selection_key": PythonITxnArgument(
        field=TxnField.SelectionPK,
        type=pytypes.BytesType,
    ),
    # vote_first: UInt64 | int = ...,
    "vote_first": PythonITxnArgument(
        field=TxnField.VoteFirst,
        type=pytypes.UInt64Type,
    ),
    # vote_last: UInt64 | int = ...,
    "vote_last": PythonITxnArgument(
        field=TxnField.VoteLast,
        type=pytypes.UInt64Type,
    ),
    # vote_key_dilution: UInt64 | int = ...,
    "vote_key_dilution": PythonITxnArgument(
        field=TxnField.VoteKeyDilution,
        type=pytypes.UInt64Type,
    ),
    # non_participation: UInt64 | int | bool = ...,
    "non_participation": PythonITxnArgument(
        field=TxnField.Nonparticipation,
        type=pytypes.UInt64Type,
        additional_types=(pytypes.BoolType,),
    ),
    # state_proof_key: Bytes | bytes = ...,
    "state_proof_key": PythonITxnArgument(
        field=TxnField.StateProofPK,
        type=pytypes.BytesType,
    ),
    # ## asset config
    # config_asset: Asset | UInt64 | int = ...,
    "config_asset": PythonITxnArgument(
        field=TxnField.ConfigAsset,
        type=pytypes.AssetType,
        additional_types=(pytypes.UInt64Type,),
    ),
    # total: UInt64 | int = ...,
    "total": PythonITxnArgument(
        field=TxnField.ConfigAssetTotal,
        type=pytypes.UInt64Type,
    ),
    # unit_name: String | Bytes | str | bytes = ...,
    "unit_name": PythonITxnArgument(
        field=TxnField.ConfigAssetUnitName,
        type=pytypes.BytesType,
        additional_types=(pytypes.StringType,),
        literal_overrides={pytypes.StrLiteralType: pytypes.StringType},
    ),
    # asset_name: String | Bytes | str | bytes = ...,
    "asset_name": PythonITxnArgument(
        field=TxnField.ConfigAssetName,
        type=pytypes.BytesType,
        additional_types=(pytypes.StringType,),
        literal_overrides={pytypes.StrLiteralType: pytypes.StringType},
    ),
    # decimals: UInt64 | int = ...,
    "decimals": PythonITxnArgument(
        field=TxnField.ConfigAssetDecimals,
        type=pytypes.UInt64Type,
    ),
    # default_frozen: bool = ...,
    "default_frozen": PythonITxnArgument(
        field=TxnField.ConfigAssetDefaultFrozen,
        type=pytypes.BoolType,
    ),
    # url: String | Bytes | bytes | str = ...,
    "url": PythonITxnArgument(
        field=TxnField.ConfigAssetURL,
        type=pytypes.BytesType,
        additional_types=(pytypes.StringType,),
        literal_overrides={pytypes.StrLiteralType: pytypes.StringType},
    ),
    # metadata_hash: Bytes | bytes = ...,
    "metadata_hash": PythonITxnArgument(
        field=TxnField.ConfigAssetMetadataHash,
        type=pytypes.BytesType,
    ),
    # manager: Account | str = ...,
    "manager": PythonITxnArgument(
        field=TxnField.ConfigAssetManager,
        type=pytypes.AccountType,
    ),
    # reserve: Account | str = ...,
    "reserve": PythonITxnArgument(
        field=TxnField.ConfigAssetReserve,
        type=pytypes.AccountType,
    ),
    # freeze: Account | str = ...,
    "freeze": PythonITxnArgument(
        field=TxnField.ConfigAssetFreeze,
        type=pytypes.AccountType,
    ),
    # clawback: Account | str = ...,
    "clawback": PythonITxnArgument(
        field=TxnField.ConfigAssetClawback,
        type=pytypes.AccountType,
    ),
    # ## asset transfer
    # xfer_asset: Asset | UInt64 | int = ...,
    "xfer_asset": PythonITxnArgument(
        field=TxnField.XferAsset,
        type=pytypes.AssetType,
        additional_types=(pytypes.UInt64Type,),
    ),
    # asset_amount: UInt64 | int = ...,
    "asset_amount": PythonITxnArgument(
        field=TxnField.AssetAmount,
        type=pytypes.UInt64Type,
    ),
    # asset_sender: Account | str = ...,
    "asset_sender": PythonITxnArgument(
        field=TxnField.AssetSender,
        type=pytypes.AccountType,
    ),
    # asset_receiver: Account | str = ...,
    "asset_receiver": PythonITxnArgument(
        field=TxnField.AssetReceiver,
        type=pytypes.AccountType,
    ),
    # asset_close_to: Account | str = ...,
    "asset_close_to": PythonITxnArgument(
        field=TxnField.AssetCloseTo,
        type=pytypes.AccountType,
    ),
    # ## asset freeze
    # freeze_asset: Asset | UInt64 | int = ...,
    "freeze_asset": PythonITxnArgument(
        field=TxnField.FreezeAsset,
        type=pytypes.AssetType,
        additional_types=(pytypes.UInt64Type,),
    ),
    # freeze_account: Account | str = ...,
    "freeze_account": PythonITxnArgument(
        field=TxnField.FreezeAssetAccount,
        type=pytypes.AccountType,
    ),
    # frozen: bool = ...,
    "frozen": PythonITxnArgument(
        field=TxnField.FreezeAssetFrozen,
        type=pytypes.BoolType,
    ),
    # ## application call
    # app_id: Application | UInt64 | int = ...,
    "app_id": PythonITxnArgument(
        field=TxnField.ApplicationID,
        type=pytypes.ApplicationType,
        additional_types=(pytypes.UInt64Type,),
    ),
    # approval_program: Bytes | bytes | tuple[Bytes, ...] = ...,
    "approval_program": PythonITxnArgument(
        field=TxnField.ApprovalProgramPages,
        type=pytypes.BytesType,
        array_promote=True,
    ),
    # clear_state_program: Bytes | bytes | tuple[Bytes, ...] = ...,
    "clear_state_program": PythonITxnArgument(
        field=TxnField.ClearStateProgramPages,
        type=pytypes.BytesType,
        array_promote=True,
    ),
    # on_completion: OnCompleteAction | UInt64 | int = ...,
    "on_completion": PythonITxnArgument(
        field=TxnField.OnCompletion,
        type=pytypes.OnCompleteActionType,
        additional_types=(pytypes.UInt64Type,),
    ),
    # global_num_uint: UInt64 | int = ...,
    "global_num_uint": PythonITxnArgument(
        field=TxnField.GlobalNumUint,
        type=pytypes.UInt64Type,
    ),
    # global_num_bytes: UInt64 | int = ...,
    "global_num_bytes": PythonITxnArgument(
        field=TxnField.GlobalNumByteSlice,
        type=pytypes.UInt64Type,
    ),
    # local_num_uint: UInt64 | int = ...,
    "local_num_uint": PythonITxnArgument(
        field=TxnField.LocalNumUint,
        type=pytypes.UInt64Type,
    ),
    # local_num_bytes: UInt64 | int = ...,
    "local_num_bytes": PythonITxnArgument(
        field=TxnField.LocalNumByteSlice,
        type=pytypes.UInt64Type,
    ),
    # extra_program_pages: UInt64 | int = ...,
    "extra_program_pages": PythonITxnArgument(
        field=TxnField.ExtraProgramPages,
        type=pytypes.UInt64Type,
    ),
    # app_args: tuple[object, ...] = ...,
    "app_args": PythonITxnArgument(
        field=TxnField.ApplicationArgs,
        type=pytypes.BytesType,
        auto_serialize_bytes=True,
    ),
    # accounts: tuple[Account, ...] = ...,
    "accounts": PythonITxnArgument(
        field=TxnField.Accounts,
        type=pytypes.AccountType,
    ),
    # assets: tuple[Asset, ...] = ...,
    "assets": PythonITxnArgument(
        field=TxnField.Assets,
        type=pytypes.AssetType,
    ),
    # apps: tuple[Application, ...] = ...,
    "apps": PythonITxnArgument(
        field=TxnField.Applications,
        type=pytypes.ApplicationType,
    ),
    # ## shared
    # sender: Account | str = ...,
    "sender": PythonITxnArgument(
        field=TxnField.Sender,
        type=pytypes.AccountType,
    ),
    # fee: UInt64 | int = 0,
    "fee": PythonITxnArgument(
        field=TxnField.Fee,
        type=pytypes.UInt64Type,
    ),
    # note: String | Bytes | str | bytes = ...,
    "note": PythonITxnArgument(
        field=TxnField.Note,
        type=pytypes.BytesType,
        additional_types=(pytypes.StringType,),
        literal_overrides={pytypes.StrLiteralType: pytypes.StringType},
    ),
    # rekey_to: Account | str = ...,
    "rekey_to": PythonITxnArgument(
        field=TxnField.RekeyTo,
        type=pytypes.AccountType,
    ),
}
