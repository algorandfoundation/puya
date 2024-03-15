from puya.awst.nodes import TxnField
from puya.awst_build.utils import snake_case

_IMMEDIATE_TO_PYTHON_OVERRIDES = {
    "VotePK": "vote_key",
    "SelectionPK": "selection_key",
    "Type": "type_bytes",
    "TypeEnum": "type",
    "TxID": "txn_id",
    "ApplicationID": "app_id",
    "ConfigAssetTotal": "total",
    "ConfigAssetDecimals": "decimals",
    "ConfigAssetDefaultFrozen": "default_frozen",
    "ConfigAssetUnitName": "unit_name",
    "ConfigAssetName": "asset_name",
    "ConfigAssetURL": "url",
    "ConfigAssetMetadataHash": "metadata_hash",
    "ConfigAssetManager": "manager",
    "ConfigAssetReserve": "reserve",
    "ConfigAssetFreeze": "freeze",
    "ConfigAssetClawback": "clawback",
    "FreezeAssetAccount": "freeze_account",
    "FreezeAssetFrozen": "frozen",
    "NumApplications": "num_apps",
    "GlobalNumByteSlice": "global_num_bytes",
    "LocalNumByteSlice": "local_num_bytes",
    "Nonparticipation": "non_participation",
    "CreatedAssetID": "created_asset",
    "CreatedApplicationID": "created_app",
    "StateProofPK": "state_proof_key",
    "ApplicationArgs": "app_args",
    "Applications": "apps",
}


def get_field_python_name(field: TxnField) -> str:
    immediate = field.immediate
    try:
        return _IMMEDIATE_TO_PYTHON_OVERRIDES[immediate]
    except KeyError:
        pass
    return snake_case(immediate)
