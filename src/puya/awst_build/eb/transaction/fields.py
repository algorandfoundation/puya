from puya.awst.txn_fields import TxnField
from puya.awst_build.utils import snake_case

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
