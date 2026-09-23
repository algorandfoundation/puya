import itertools
import typing

from puya import algo_constants, log
from puya.context import CompileContext
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize._utils import SSAReadTracker
from puya.utils import EditSet

logger = log.get_logger(__name__)


# "conservative" sets of fields that can't fail/change
# and are therefore safely movable by this pass
_MOVABLE_TXN_FIELDS: typing.Final = frozenset(
    {
        # excluded:
        # - FirstValidTime: fails if negative (technically can't fail in mainnet)
        # - NumLogs, LastLog, CreatedAssetID, CreatedApplicationID:
        #   reading these effects from the current transaction always fails
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
    # reads no registers, has no side effects and cannot fail, so may be moved anywhere
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


def _splits_dupable_chunk(
    ops: list[models.Op],
    op_idx: int,
    op: models.Assignment,
    consumer: models.Op,
    ssa_reads: SSAReadTracker,
) -> bool:
    # when there is a chunk of adjacent value loads followed by consumers of said values
    # (i.e. they happen to be locally aligned stack optimally already) some of them may
    # be replaced by `dup` ops at TEAL level, which will probably be better than moving
    # the loads (as dups are one byte and loads may be a couple), so we leave them be

    # if not on the same basic block, probably beneficial to move them
    if consumer not in ops:
        return False

    # collect the chunk of identical loads before and up to `op`
    source = op.source.freeze()
    loads_chunk = [op]
    for other_op in reversed(ops[:op_idx]):
        if isinstance(other_op, models.Assignment) and other_op.source.freeze() == source:
            loads_chunk.append(other_op)
        else:
            break

    # collect the rest of the chunk, identical loads after op
    chunk_end = op_idx + 1
    for other_op in ops[op_idx + 1 :]:
        if isinstance(other_op, models.Assignment) and other_op.source.freeze() == source:
            loads_chunk.append(other_op)
            chunk_end += 1
        else:
            break

    if len(loads_chunk) < 2:
        return False

    # look at the ops following the chunk that should consume loaded values
    # if there is a "gap" (i.e. an op that is not a reader for any load in the chunk)
    # then the consumers are not consecutive, and thus we choose to sink
    readers = {reader for load in loads_chunk for reader in ssa_reads.get(load.targets[0])}
    for consumer_op in ops[chunk_end:]:
        if consumer_op not in readers:
            return False
        if consumer_op is consumer:
            return True
    return False


def sink_single_use_intrinsics(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    """Move never-fail intrinsic assignments next to their sole consumer."""
    ssa_reads = SSAReadTracker()
    for block in subroutine.body:
        for op in block.all_ops:
            ssa_reads.add(op)

    # maps each consumer to the assignment that should be sunk to directly before it
    consumer_assignment = dict[models.Op, models.Assignment]()
    # maps each block to its edits
    edits = dict[models.BasicBlock, EditSet[models.Op]]()
    for block in subroutine.body:
        ops = block.ops
        block_edits = EditSet[models.Op]()
        edits[block] = block_edits

        for op_idx, (op, next_op) in enumerate(itertools.zip_longest(ops, ops[1:])):
            match op:
                case models.Assignment(
                    targets=[target], source=models.Intrinsic() as intrinsic
                ) if _is_unconditionally_movable(intrinsic):
                    consumer = ssa_reads.get_sole_usage(target)
                    if (
                        isinstance(consumer, models.Op)
                        and consumer is not next_op
                        and _consumes_single_value(consumer)
                        and not _splits_dupable_chunk(ops, op_idx, op, consumer, ssa_reads)
                    ):
                        logger.debug(f"moving {op} to be co-located with sole usage {consumer}")
                        consumer_assignment[consumer] = op
                        block_edits.remove(op_idx)
    if not consumer_assignment:
        return False

    for block in subroutine.body:
        block_edits = edits[block]
        for idx, op in enumerate(block.ops):
            if (assignment_to_sink := consumer_assignment.pop(op, None)) is not None:
                block_edits.add_edit(idx, 0, (assignment_to_sink,))
        block_edits.apply(block.ops)
    assert not consumer_assignment, f"consumers not in any block: {consumer_assignment}"
    return True
