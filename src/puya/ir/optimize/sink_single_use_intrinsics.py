import itertools
import typing

from puya import algo_constants, log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize._utils import SSAReadTracker

logger = log.get_logger(__name__)


# "conservative" sets of fields that can't fail/change
# and are therefore safely movable by this pass
_MOVABLE_TXN_FIELDS: typing.Final = frozenset(
    {
        # excluded:
        # - FirstValidTime: fails if negative
        # - array fields: read via txna, not txn
        # - NumLogs, LastLog, CreatedAssetID, CreatedApplicationID:
        #   reading effects from the current transaction always fails
        "Sender",
        "Fee",
        "FirstValid",
        "LastValid",
        "Note",
        "Lease",
        "Receiver",
        "Amount",
        "CloseRemainderTo",
        "VotePK",
        "SelectionPK",
        "VoteFirst",
        "VoteLast",
        "VoteKeyDilution",
        "Type",
        "TypeEnum",
        "XferAsset",
        "AssetAmount",
        "AssetSender",
        "AssetReceiver",
        "AssetCloseTo",
        "GroupIndex",
        "TxID",
        "ApplicationID",
        "OnCompletion",
        "NumAppArgs",
        "NumAccounts",
        "ApprovalProgram",
        "ClearStateProgram",
        "RekeyTo",
        "ConfigAsset",
        "ConfigAssetTotal",
        "ConfigAssetDecimals",
        "ConfigAssetDefaultFrozen",
        "ConfigAssetUnitName",
        "ConfigAssetName",
        "ConfigAssetURL",
        "ConfigAssetMetadataHash",
        "ConfigAssetManager",
        "ConfigAssetReserve",
        "ConfigAssetFreeze",
        "ConfigAssetClawback",
        "FreezeAsset",
        "FreezeAssetAccount",
        "FreezeAssetFrozen",
        "NumAssets",
        "NumApplications",
        "GlobalNumUint",
        "GlobalNumByteSlice",
        "LocalNumUint",
        "LocalNumByteSlice",
        "ExtraProgramPages",
        "Nonparticipation",
        "StateProofPK",
        "NumApprovalProgramPages",
        "NumClearStateProgramPages",
        "RejectVersion",
    }
)
_MOVABLE_GLOBAL_FIELDS: typing.Final = frozenset(
    {
        # excluded:
        # - OpcodeBudget: value depends on position
        # - LatestTimestamp: fails if negative
        "MinTxnFee",
        "MinBalance",
        "MaxTxnLife",
        "ZeroAddress",
        "GroupSize",
        "LogicSigVersion",
        "Round",
        "CurrentApplicationID",
        "CreatorAddress",
        "CurrentApplicationAddress",
        "GroupID",
        "CallerApplicationID",
        "CallerApplicationAddress",
        "AssetCreateMinBalance",
        "AssetOptInMinBalance",
        "GenesisHash",
        "PayoutsEnabled",
        "PayoutsGoOnlineFee",
        "PayoutsPercent",
        "PayoutsMinBalance",
        "PayoutsMaxBalance",
    }
)


def _is_unconditionally_movable(intrinsic: models.Intrinsic) -> bool:
    """Reads no registers, has no side effects and cannot fail, so may be moved anywhere."""
    match intrinsic:
        case models.Intrinsic(op=AVMOp.bzero, args=[models.UInt64Constant(value=size)]):
            return size <= algo_constants.MAX_BYTES_LENGTH
        case models.Intrinsic(op=AVMOp.itob, args=[models.Constant()]):
            return True
        case models.Intrinsic(op=AVMOp.txn, immediates=[field]):
            return field in _MOVABLE_TXN_FIELDS
        case models.Intrinsic(op=AVMOp.global_, immediates=[field]):
            return field in _MOVABLE_GLOBAL_FIELDS
        case _:
            return False


def _consumes_single_value(op: models.Op) -> bool:
    match op:
        case models.Intrinsic(args=[_]) | models.Assignment(source=models.Intrinsic(args=[_])):
            return True
        case _:
            return False


def sink_single_use_intrinsics(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    """Move never-fail intrinsic assignments next to their sole consumer."""
    ssa_reads = SSAReadTracker()
    for block in subroutine.body:
        for op in block.all_ops:
            ssa_reads.add(op)

    # maps each consumer to the assignment that should be sunk to directly before it
    consumer_assignment = dict[models.Op, models.Assignment]()
    for block in subroutine.body:
        # iterate over a copy so the assignment can be removed from the block
        for op, next_op in itertools.zip_longest(block.ops.copy(), block.ops[1:]):
            match op:
                case models.Assignment(
                    targets=[target], source=models.Intrinsic() as intrinsic
                ) if _is_unconditionally_movable(intrinsic):
                    consumer = ssa_reads.get_sole_usage(target)
                    if (
                        isinstance(consumer, models.Op)
                        and consumer is not next_op
                        and _consumes_single_value(consumer)
                    ):
                        logger.debug(f"moving {op} to be co-located with sole usage {consumer}")
                        consumer_assignment[consumer] = op
                        block.ops.remove(op)
    if not consumer_assignment:
        return False

    for block in subroutine.body:
        new_ops = list[models.Op]()
        for op in block.ops:
            if (assignment_to_sink := consumer_assignment.pop(op, None)) is not None:
                new_ops.append(assignment_to_sink)
            new_ops.append(op)
        block.ops[:] = new_ops
    assert not consumer_assignment, f"consumers not in any block: {consumer_assignment}"
    return True
