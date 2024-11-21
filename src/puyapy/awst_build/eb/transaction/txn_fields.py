import attrs

from puya import log
from puya.awst.txn_fields import TxnField
from puyapy.awst_build import pytypes

logger = log.get_logger(__name__)


@attrs.frozen
class PythonTxnField:
    field: TxnField
    type: pytypes.RuntimeType


PYTHON_TXN_FIELDS = {
    "sender": PythonTxnField(TxnField.Sender, pytypes.AccountType),
    "fee": PythonTxnField(TxnField.Fee, pytypes.UInt64Type),
    "first_valid": PythonTxnField(TxnField.FirstValid, pytypes.UInt64Type),
    "first_valid_time": PythonTxnField(TxnField.FirstValidTime, pytypes.UInt64Type),
    "last_valid": PythonTxnField(TxnField.LastValid, pytypes.UInt64Type),
    "note": PythonTxnField(TxnField.Note, pytypes.BytesType),
    "lease": PythonTxnField(TxnField.Lease, pytypes.BytesType),
    "receiver": PythonTxnField(TxnField.Receiver, pytypes.AccountType),
    "amount": PythonTxnField(TxnField.Amount, pytypes.UInt64Type),
    "close_remainder_to": PythonTxnField(TxnField.CloseRemainderTo, pytypes.AccountType),
    "vote_key": PythonTxnField(TxnField.VotePK, pytypes.BytesType),
    "selection_key": PythonTxnField(TxnField.SelectionPK, pytypes.BytesType),
    "vote_first": PythonTxnField(TxnField.VoteFirst, pytypes.UInt64Type),
    "vote_last": PythonTxnField(TxnField.VoteLast, pytypes.UInt64Type),
    "vote_key_dilution": PythonTxnField(TxnField.VoteKeyDilution, pytypes.UInt64Type),
    "type_bytes": PythonTxnField(TxnField.Type, pytypes.BytesType),
    "type": PythonTxnField(TxnField.TypeEnum, pytypes.TransactionTypeType),
    "xfer_asset": PythonTxnField(TxnField.XferAsset, pytypes.AssetType),
    "asset_amount": PythonTxnField(TxnField.AssetAmount, pytypes.UInt64Type),
    "asset_sender": PythonTxnField(TxnField.AssetSender, pytypes.AccountType),
    "asset_receiver": PythonTxnField(TxnField.AssetReceiver, pytypes.AccountType),
    "asset_close_to": PythonTxnField(TxnField.AssetCloseTo, pytypes.AccountType),
    "group_index": PythonTxnField(TxnField.GroupIndex, pytypes.UInt64Type),
    "txn_id": PythonTxnField(TxnField.TxID, pytypes.BytesType),
    "app_id": PythonTxnField(TxnField.ApplicationID, pytypes.ApplicationType),
    "on_completion": PythonTxnField(TxnField.OnCompletion, pytypes.OnCompleteActionType),
    "num_app_args": PythonTxnField(TxnField.NumAppArgs, pytypes.UInt64Type),
    "num_accounts": PythonTxnField(TxnField.NumAccounts, pytypes.UInt64Type),
    "approval_program": PythonTxnField(TxnField.ApprovalProgram, pytypes.BytesType),
    "clear_state_program": PythonTxnField(TxnField.ClearStateProgram, pytypes.BytesType),
    "rekey_to": PythonTxnField(TxnField.RekeyTo, pytypes.AccountType),
    "config_asset": PythonTxnField(TxnField.ConfigAsset, pytypes.AssetType),
    "total": PythonTxnField(TxnField.ConfigAssetTotal, pytypes.UInt64Type),
    "decimals": PythonTxnField(TxnField.ConfigAssetDecimals, pytypes.UInt64Type),
    "default_frozen": PythonTxnField(TxnField.ConfigAssetDefaultFrozen, pytypes.BoolType),
    "unit_name": PythonTxnField(TxnField.ConfigAssetUnitName, pytypes.BytesType),
    "asset_name": PythonTxnField(TxnField.ConfigAssetName, pytypes.BytesType),
    "url": PythonTxnField(TxnField.ConfigAssetURL, pytypes.BytesType),
    "metadata_hash": PythonTxnField(TxnField.ConfigAssetMetadataHash, pytypes.BytesType),
    "manager": PythonTxnField(TxnField.ConfigAssetManager, pytypes.AccountType),
    "reserve": PythonTxnField(TxnField.ConfigAssetReserve, pytypes.AccountType),
    "freeze": PythonTxnField(TxnField.ConfigAssetFreeze, pytypes.AccountType),
    "clawback": PythonTxnField(TxnField.ConfigAssetClawback, pytypes.AccountType),
    "freeze_asset": PythonTxnField(TxnField.FreezeAsset, pytypes.AssetType),
    "freeze_account": PythonTxnField(TxnField.FreezeAssetAccount, pytypes.AccountType),
    "frozen": PythonTxnField(TxnField.FreezeAssetFrozen, pytypes.BoolType),
    "num_assets": PythonTxnField(TxnField.NumAssets, pytypes.UInt64Type),
    "num_apps": PythonTxnField(TxnField.NumApplications, pytypes.UInt64Type),
    "global_num_uint": PythonTxnField(TxnField.GlobalNumUint, pytypes.UInt64Type),
    "global_num_bytes": PythonTxnField(TxnField.GlobalNumByteSlice, pytypes.UInt64Type),
    "local_num_uint": PythonTxnField(TxnField.LocalNumUint, pytypes.UInt64Type),
    "local_num_bytes": PythonTxnField(TxnField.LocalNumByteSlice, pytypes.UInt64Type),
    "extra_program_pages": PythonTxnField(TxnField.ExtraProgramPages, pytypes.UInt64Type),
    "non_participation": PythonTxnField(TxnField.Nonparticipation, pytypes.BoolType),
    "num_logs": PythonTxnField(TxnField.NumLogs, pytypes.UInt64Type),
    "created_asset": PythonTxnField(TxnField.CreatedAssetID, pytypes.AssetType),
    "created_app": PythonTxnField(TxnField.CreatedApplicationID, pytypes.ApplicationType),
    "last_log": PythonTxnField(TxnField.LastLog, pytypes.BytesType),
    "state_proof_key": PythonTxnField(TxnField.StateProofPK, pytypes.BytesType),
    "num_approval_program_pages": PythonTxnField(
        TxnField.NumApprovalProgramPages, pytypes.UInt64Type
    ),
    "num_clear_state_program_pages": PythonTxnField(
        TxnField.NumClearStateProgramPages,
        pytypes.UInt64Type,
    ),
    "app_args": PythonTxnField(TxnField.ApplicationArgs, pytypes.BytesType),
    "accounts": PythonTxnField(TxnField.Accounts, pytypes.AccountType),
    "assets": PythonTxnField(TxnField.Assets, pytypes.AssetType),
    "apps": PythonTxnField(TxnField.Applications, pytypes.ApplicationType),
    "logs": PythonTxnField(TxnField.Logs, pytypes.BytesType),
    "approval_program_pages": PythonTxnField(TxnField.ApprovalProgramPages, pytypes.BytesType),
    "clear_state_program_pages": PythonTxnField(
        TxnField.ClearStateProgramPages, pytypes.BytesType
    ),
}
