# ruff: noqa: PIE796
import enum
import typing

import attrs

from puya.avm import AVMType
from puya.awst import wtypes

__all__ = [
    "TxnField",
]


@attrs.frozen(eq=False, hash=False)
class _TxnFieldData:
    wtype: wtypes.WType
    num_values: int = attrs.field(default=1, validator=attrs.validators.ge(1), kw_only=True)
    is_inner_param: bool = attrs.field(default=True, kw_only=True)


_Bytes32WType = wtypes.BytesWType(length=32)


@enum.unique
class TxnField(enum.Enum):
    def __init__(self, data: _TxnFieldData):
        # _name_ is set by the EnumType metaclass during construction,
        # and refers to the class member name
        self.immediate: typing.Final = self._name_
        assert data.wtype.scalar_type is not None
        self.avm_type: typing.Final = data.wtype.scalar_type
        typing.assert_type(self.avm_type, typing.Literal[AVMType.uint64, AVMType.bytes])
        self.wtype: typing.Final = data.wtype
        self.num_values: typing.Final = data.num_values
        self.is_inner_param: typing.Final = data.is_inner_param

    @property
    def is_array(self) -> bool:
        return self.num_values > 1

    def valid_argument_type(self, wtype: wtypes.WType) -> bool:
        if not self.is_array:
            return wtype.scalar_type == self.avm_type
        else:
            return isinstance(wtype, wtypes.WTuple) and all(
                item_wtype.scalar_type == self.avm_type for item_wtype in wtype.types
            )

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"immediate={self.immediate!r},"
            f" wtype={self.wtype},"
            f" num_values={self.num_values!r},"
            f" is_inner_param={self.is_inner_param!r}"
            ")"
        )

    Sender = _TxnFieldData(wtypes.account_wtype)
    Fee = _TxnFieldData(wtypes.uint64_wtype)
    FirstValid = _TxnFieldData(wtypes.uint64_wtype, is_inner_param=False)
    FirstValidTime = _TxnFieldData(wtypes.uint64_wtype, is_inner_param=False)
    LastValid = _TxnFieldData(wtypes.uint64_wtype, is_inner_param=False)
    Note = _TxnFieldData(wtypes.bytes_wtype)
    Lease = _TxnFieldData(_Bytes32WType, is_inner_param=False)
    Receiver = _TxnFieldData(wtypes.account_wtype)
    Amount = _TxnFieldData(wtypes.uint64_wtype)
    CloseRemainderTo = _TxnFieldData(wtypes.account_wtype)
    VotePK = _TxnFieldData(_Bytes32WType)
    SelectionPK = _TxnFieldData(_Bytes32WType)
    VoteFirst = _TxnFieldData(wtypes.uint64_wtype)
    VoteLast = _TxnFieldData(wtypes.uint64_wtype)
    VoteKeyDilution = _TxnFieldData(wtypes.uint64_wtype)
    Type = _TxnFieldData(wtypes.bytes_wtype)
    TypeEnum = _TxnFieldData(wtypes.uint64_wtype)
    XferAsset = _TxnFieldData(wtypes.asset_wtype)
    AssetAmount = _TxnFieldData(wtypes.uint64_wtype)
    AssetSender = _TxnFieldData(wtypes.account_wtype)
    AssetReceiver = _TxnFieldData(wtypes.account_wtype)
    AssetCloseTo = _TxnFieldData(wtypes.account_wtype)
    GroupIndex = _TxnFieldData(wtypes.uint64_wtype, is_inner_param=False)
    TxID = _TxnFieldData(_Bytes32WType, is_inner_param=False)
    # v2
    ApplicationID = _TxnFieldData(wtypes.application_wtype)
    OnCompletion = _TxnFieldData(wtypes.uint64_wtype)
    NumAppArgs = _TxnFieldData(wtypes.uint64_wtype, is_inner_param=False)
    NumAccounts = _TxnFieldData(wtypes.uint64_wtype, is_inner_param=False)
    ApprovalProgram = _TxnFieldData(wtypes.bytes_wtype)
    ClearStateProgram = _TxnFieldData(wtypes.bytes_wtype)
    RekeyTo = _TxnFieldData(wtypes.account_wtype)
    ConfigAsset = _TxnFieldData(wtypes.asset_wtype)
    ConfigAssetTotal = _TxnFieldData(wtypes.uint64_wtype)
    ConfigAssetDecimals = _TxnFieldData(wtypes.uint64_wtype)
    ConfigAssetDefaultFrozen = _TxnFieldData(wtypes.bool_wtype)
    ConfigAssetUnitName = _TxnFieldData(wtypes.bytes_wtype)
    ConfigAssetName = _TxnFieldData(wtypes.bytes_wtype)
    ConfigAssetURL = _TxnFieldData(wtypes.bytes_wtype)
    ConfigAssetMetadataHash = _TxnFieldData(_Bytes32WType)
    ConfigAssetManager = _TxnFieldData(wtypes.account_wtype)
    ConfigAssetReserve = _TxnFieldData(wtypes.account_wtype)
    ConfigAssetFreeze = _TxnFieldData(wtypes.account_wtype)
    ConfigAssetClawback = _TxnFieldData(wtypes.account_wtype)
    FreezeAsset = _TxnFieldData(wtypes.asset_wtype)
    FreezeAssetAccount = _TxnFieldData(wtypes.account_wtype)
    FreezeAssetFrozen = _TxnFieldData(wtypes.bool_wtype)
    # v3
    NumAssets = _TxnFieldData(wtypes.uint64_wtype, is_inner_param=False)
    NumApplications = _TxnFieldData(wtypes.uint64_wtype, is_inner_param=False)
    GlobalNumUint = _TxnFieldData(wtypes.uint64_wtype)
    GlobalNumByteSlice = _TxnFieldData(wtypes.uint64_wtype)
    LocalNumUint = _TxnFieldData(wtypes.uint64_wtype)
    LocalNumByteSlice = _TxnFieldData(wtypes.uint64_wtype)
    # v4
    ExtraProgramPages = _TxnFieldData(wtypes.uint64_wtype)
    # v5
    Nonparticipation = _TxnFieldData(wtypes.bool_wtype)
    NumLogs = _TxnFieldData(wtypes.uint64_wtype, is_inner_param=False)
    CreatedAssetID = _TxnFieldData(wtypes.asset_wtype, is_inner_param=False)
    CreatedApplicationID = _TxnFieldData(wtypes.application_wtype, is_inner_param=False)
    # v6
    LastLog = _TxnFieldData(wtypes.bytes_wtype, is_inner_param=False)
    StateProofPK = _TxnFieldData(wtypes.bytes_wtype)
    # v7
    NumApprovalProgramPages = _TxnFieldData(wtypes.uint64_wtype, is_inner_param=False)
    NumClearStateProgramPages = _TxnFieldData(wtypes.uint64_wtype, is_inner_param=False)
    # array fields
    # TODO: allow configuring as these are consensus values
    # v2
    ApplicationArgs = _TxnFieldData(wtypes.bytes_wtype, num_values=16)
    Accounts = _TxnFieldData(wtypes.account_wtype, num_values=4)
    # v3
    Assets = _TxnFieldData(wtypes.asset_wtype, num_values=8)
    Applications = _TxnFieldData(wtypes.application_wtype, num_values=8)
    # v5
    Logs = _TxnFieldData(wtypes.bytes_wtype, num_values=32, is_inner_param=False)
    # v7
    ApprovalProgramPages = _TxnFieldData(wtypes.bytes_wtype, num_values=4)
    ClearStateProgramPages = _TxnFieldData(wtypes.bytes_wtype, num_values=4)
