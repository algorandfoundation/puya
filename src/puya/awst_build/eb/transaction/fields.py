from collections.abc import Mapping

import attrs
from immutabledict import immutabledict

from puya.awst.txn_fields import TxnField
from puya.awst_build import pytypes
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb.interface import InstanceBuilder, NodeBuilder, StaticSizedCollectionBuilder
from puya.awst_build.eb.tuple import TupleLiteralBuilder
from puya.awst_build.utils import resolve_literal, snake_case


@attrs.frozen(kw_only=True)
class PythonTxnFieldParam:
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
            assert self.type == pytypes.BytesType
            assert not self.additional_types
            assert not self.literal_overrides

    def validate_and_convert(self, builder: NodeBuilder) -> InstanceBuilder:
        if self.field.is_array:
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
            item = self._validate_and_convert_item(eb)
            return TupleLiteralBuilder([item], item.source_location)
        else:
            return expect.argument_of_type(
                eb, pytypes.VariadicTupleType(items=self.type), default=dummy_default
            )

    def _validate_and_convert_item(self, item: InstanceBuilder) -> InstanceBuilder:
        if (
            override_literal_type := self.literal_overrides.get(item.pytype)  # type: ignore[call-overload]
        ) is not None:
            item = resolve_literal(item, override_literal_type)


ITXN_FIELD_PARAMS = {
    # type(:) TransactionType = ...,
    "type": PythonTxnFieldParam(
        field=TxnField.TypeEnum,
        type=pytypes.TransactionTypeType,
    ),
    # ## payment
    # receiver: Account | str = ...,
    "receiver": PythonTxnFieldParam(
        field=TxnField.Receiver,
        type=pytypes.AccountType,
    ),
    # amount: UInt64 | int = ...,
    "amount": PythonTxnFieldParam(
        field=TxnField.Amount,
        type=pytypes.UInt64Type,
    ),
    # close_remainder_to: Account | str = ...,
    "close_remainder_to": PythonTxnFieldParam(
        field=TxnField.CloseRemainderTo,
        type=pytypes.AccountType,
    ),
    # ## key registration
    # vote_key: Bytes | bytes = ...,
    "vote_key": PythonTxnFieldParam(
        field=TxnField.VotePK,
        type=pytypes.BytesType,
    ),
    # selection_key: Bytes | bytes = ...,
    "selection_key": PythonTxnFieldParam(
        field=TxnField.SelectionPK,
        type=pytypes.BytesType,
    ),
    # vote_first: UInt64 | int = ...,
    "vote_first": PythonTxnFieldParam(
        field=TxnField.VoteFirst,
        type=pytypes.UInt64Type,
    ),
    # vote_last: UInt64 | int = ...,
    "vote_last": PythonTxnFieldParam(
        field=TxnField.VoteLast,
        type=pytypes.UInt64Type,
    ),
    # vote_key_dilution: UInt64 | int = ...,
    "vote_key_dilution": PythonTxnFieldParam(
        field=TxnField.VoteKeyDilution,
        type=pytypes.UInt64Type,
    ),
    # non_participation: UInt64 | int | bool = ...,
    "non_participation": PythonTxnFieldParam(
        field=TxnField.Nonparticipation,
        type=pytypes.UInt64Type,
        additional_types=(pytypes.BoolType,),
    ),
    # state_proof_key: Bytes | bytes = ...,
    "state_proof_key": PythonTxnFieldParam(
        field=TxnField.StateProofPK,
        type=pytypes.BytesType,
    ),
    # ## asset config
    # config_asset: Asset | UInt64 | int = ...,
    "config_asset": PythonTxnFieldParam(
        field=TxnField.ConfigAsset,
        type=pytypes.AssetType,
        additional_types=(pytypes.UInt64Type,),
    ),
    # total: UInt64 | int = ...,
    "total": PythonTxnFieldParam(
        field=TxnField.ConfigAssetTotal,
        type=pytypes.UInt64Type,
    ),
    # unit_name: String | Bytes | str | bytes = ...,
    "unit_name": PythonTxnFieldParam(
        field=TxnField.ConfigAssetUnitName,
        type=pytypes.BytesType,
        additional_types=(pytypes.StringType,),
        literal_overrides={pytypes.StrLiteralType: pytypes.StringType},
    ),
    # asset_name: String | Bytes | str | bytes = ...,
    "asset_name": PythonTxnFieldParam(
        field=TxnField.ConfigAssetName,
        type=pytypes.BytesType,
        additional_types=(pytypes.StringType,),
        literal_overrides={pytypes.StrLiteralType: pytypes.StringType},
    ),
    # decimals: UInt64 | int = ...,
    "decimals": PythonTxnFieldParam(
        field=TxnField.ConfigAssetDecimals,
        type=pytypes.UInt64Type,
    ),
    # default_frozen: bool = ...,
    "default_frozen": PythonTxnFieldParam(
        field=TxnField.ConfigAssetDefaultFrozen,
        type=pytypes.BoolType,
    ),
    # url: String | Bytes | bytes | str = ...,
    "url": PythonTxnFieldParam(
        field=TxnField.ConfigAssetURL,
        type=pytypes.BytesType,
        additional_types=(pytypes.StringType,),
        literal_overrides={pytypes.StrLiteralType: pytypes.StringType},
    ),
    # metadata_hash: Bytes | bytes = ...,
    "metadata_hash": PythonTxnFieldParam(
        field=TxnField.ConfigAssetMetadataHash,
        type=pytypes.BytesType,
    ),
    # manager: Account | str = ...,
    "manager": PythonTxnFieldParam(
        field=TxnField.ConfigAssetManager,
        type=pytypes.AccountType,
    ),
    # reserve: Account | str = ...,
    "reserve": PythonTxnFieldParam(
        field=TxnField.ConfigAssetReserve,
        type=pytypes.AccountType,
    ),
    # freeze: Account | str = ...,
    "freeze": PythonTxnFieldParam(
        field=TxnField.ConfigAssetFreeze,
        type=pytypes.AccountType,
    ),
    # clawback: Account | str = ...,
    "clawback": PythonTxnFieldParam(
        field=TxnField.ConfigAssetClawback,
        type=pytypes.AccountType,
    ),
    # ## asset transfer
    # xfer_asset: Asset | UInt64 | int = ...,
    "xfer_asset": PythonTxnFieldParam(
        field=TxnField.XferAsset,
        type=pytypes.AssetType,
        additional_types=(pytypes.UInt64Type,),
    ),
    # asset_amount: UInt64 | int = ...,
    "asset_amount": PythonTxnFieldParam(
        field=TxnField.AssetAmount,
        type=pytypes.UInt64Type,
    ),
    # asset_sender: Account | str = ...,
    "asset_sender": PythonTxnFieldParam(
        field=TxnField.AssetSender,
        type=pytypes.AccountType,
    ),
    # asset_receiver: Account | str = ...,
    "asset_receiver": PythonTxnFieldParam(
        field=TxnField.AssetReceiver,
        type=pytypes.AccountType,
    ),
    # asset_close_to: Account | str = ...,
    "asset_close_to": PythonTxnFieldParam(
        field=TxnField.AssetCloseTo,
        type=pytypes.AccountType,
    ),
    # ## asset freeze
    # freeze_asset: Asset | UInt64 | int = ...,
    "freeze_asset": PythonTxnFieldParam(
        field=TxnField.FreezeAsset,
        type=pytypes.AssetType,
        additional_types=(pytypes.UInt64Type,),
    ),
    # freeze_account: Account | str = ...,
    "freeze_account": PythonTxnFieldParam(
        field=TxnField.FreezeAssetAccount,
        type=pytypes.AccountType,
    ),
    # frozen: bool = ...,
    "frozen": PythonTxnFieldParam(
        field=TxnField.FreezeAssetFrozen,
        type=pytypes.BoolType,
    ),
    # ## application call
    # app_id: Application | UInt64 | int = ...,
    "app_id": PythonTxnFieldParam(
        field=TxnField.ApplicationID,
        type=pytypes.ApplicationType,
        additional_types=(pytypes.UInt64Type,),
    ),
    # approval_program: Bytes | bytes | tuple[Bytes, ...] = ...,
    "approval_program": PythonTxnFieldParam(
        field=TxnField.ApprovalProgramPages,
        type=pytypes.BytesType,
        array_promote=True,
    ),
    # clear_state_program: Bytes | bytes | tuple[Bytes, ...] = ...,
    "clear_state_program": PythonTxnFieldParam(
        field=TxnField.ClearStateProgramPages,
        type=pytypes.BytesType,
        array_promote=True,
    ),
    # on_completion: OnCompleteAction | UInt64 | int = ...,
    "on_completion": PythonTxnFieldParam(
        field=TxnField.OnCompletion,
        type=pytypes.OnCompleteActionType,
        additional_types=(pytypes.UInt64Type,),
    ),
    # global_num_uint: UInt64 | int = ...,
    "global_num_uint": PythonTxnFieldParam(
        field=TxnField.GlobalNumUint,
        type=pytypes.UInt64Type,
    ),
    # global_num_bytes: UInt64 | int = ...,
    "global_num_bytes": PythonTxnFieldParam(
        field=TxnField.GlobalNumByteSlice,
        type=pytypes.UInt64Type,
    ),
    # local_num_uint: UInt64 | int = ...,
    "local_num_uint": PythonTxnFieldParam(
        field=TxnField.LocalNumUint,
        type=pytypes.UInt64Type,
    ),
    # local_num_bytes: UInt64 | int = ...,
    "local_num_bytes": PythonTxnFieldParam(
        field=TxnField.LocalNumByteSlice,
        type=pytypes.UInt64Type,
    ),
    # extra_program_pages: UInt64 | int = ...,
    "extra_program_pages": PythonTxnFieldParam(
        field=TxnField.ExtraProgramPages,
        type=pytypes.UInt64Type,
    ),
    # app_args: tuple[object, ...] = ...,
    "app_args": PythonTxnFieldParam(
        field=TxnField.ApplicationArgs,
        type=pytypes.BytesType,
        auto_serialize_bytes=True,
    ),
    # accounts: tuple[Account, ...] = ...,
    "accounts": PythonTxnFieldParam(
        field=TxnField.Accounts,
        type=pytypes.AccountType,
    ),
    # assets: tuple[Asset, ...] = ...,
    "assets": PythonTxnFieldParam(
        field=TxnField.Assets,
        type=pytypes.AssetType,
    ),
    # apps: tuple[Application, ...] = ...,
    "apps": PythonTxnFieldParam(
        field=TxnField.Applications,
        type=pytypes.ApplicationType,
    ),
    # ## shared
    # sender: Account | str = ...,
    "sender": PythonTxnFieldParam(
        field=TxnField.Sender,
        type=pytypes.AccountType,
    ),
    # fee: UInt64 | int = 0,
    "fee": PythonTxnFieldParam(
        field=TxnField.Fee,
        type=pytypes.UInt64Type,
    ),
    # note: String | Bytes | str | bytes = ...,
    "note": PythonTxnFieldParam(
        field=TxnField.Note,
        type=pytypes.BytesType,
        additional_types=(pytypes.StringType,),
        literal_overrides={pytypes.StrLiteralType: pytypes.StringType},
    ),
    # rekey_to: Account | str = ...,
    "rekey_to": PythonTxnFieldParam(
        field=TxnField.RekeyTo,
        type=pytypes.AccountType,
    ),
}
_IMMEDIATE_TO_PYTHON_OVERRIDES = {
    TxnField.VotePK: "vote_key",
    TxnField.SelectionPK: "selection_key",
    TxnField.Type: "type_bytes",
    TxnField.TypeEnum: "type",
    TxnField.TxID: "txn_id",
    TxnField.ApplicationID: "app_id",
    TxnField.ConfigAssetTotal: "total",
    TxnField.ConfigAssetDecimals: "decimals",
    TxnField.ConfigAssetDefaultFrozen: "default_frozen",
    TxnField.ConfigAssetUnitName: "unit_name",
    TxnField.ConfigAssetName: "asset_name",
    TxnField.ConfigAssetURL: "url",
    TxnField.ConfigAssetMetadataHash: "metadata_hash",
    TxnField.ConfigAssetManager: "manager",
    TxnField.ConfigAssetReserve: "reserve",
    TxnField.ConfigAssetFreeze: "freeze",
    TxnField.ConfigAssetClawback: "clawback",
    TxnField.FreezeAssetAccount: "freeze_account",
    TxnField.FreezeAssetFrozen: "frozen",
    TxnField.NumApplications: "num_apps",
    TxnField.GlobalNumByteSlice: "global_num_bytes",
    TxnField.LocalNumByteSlice: "local_num_bytes",
    TxnField.Nonparticipation: "non_participation",
    TxnField.CreatedAssetID: "created_asset",
    TxnField.CreatedApplicationID: "created_app",
    TxnField.StateProofPK: "state_proof_key",
    TxnField.ApplicationArgs: "app_args",
    TxnField.Applications: "apps",
}


@attrs.frozen
class PythonTxnFieldResult:
    name: str
    type: pytypes.PyType


@attrs.frozen
class PythonTxnField:
    field: TxnField
    python_field_name: str
    python_argument_name: str


def get_field_python_name(field: TxnField) -> str:
    try:
        return _IMMEDIATE_TO_PYTHON_OVERRIDES[field]
    except KeyError:
        pass
    return snake_case(field.immediate)


def get_argument_python_name(field: TxnField) -> str | None:
    match field:
        case TxnField.ApprovalProgram | TxnField.ClearStateProgram:
            return None
        case TxnField.ApprovalProgramPages:
            field = TxnField.ApprovalProgram
        case TxnField.ClearStateProgramPages:
            field = TxnField.ClearStateProgram
    return get_field_python_name(field)
