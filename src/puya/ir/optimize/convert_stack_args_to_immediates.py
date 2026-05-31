import typing

import attrs

from puya import log
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize.context import IROptimizationContext
from puya.ir.visitor_mutator import IRMutator

logger = log.get_logger(__name__)


def convert_stack_args_to_immediates(
    _context: IROptimizationContext, subroutine: models.Subroutine
) -> bool:
    mutator = _StackArgsToImmediatesMutator()
    for block in subroutine.body:
        mutator.visit_block(block)
    return mutator.modified > 0


@attrs.define(kw_only=True)
class _StackArgsToImmediatesMutator(IRMutator):
    modified: int = 0

    @typing.override
    def visit_intrinsic_op(self, intrinsic: models.Intrinsic) -> None:
        if (
            intrinsic.args
            and (replacement := _try_convert_stack_args_to_immediates(intrinsic)) is not None
        ):
            before = str(intrinsic)
            # note: assignment order here relies on current attrs validators, if that changes
            # an alternative would be to assign to list slices first, then op, then call
            # attrs.validate() manually
            intrinsic.op, intrinsic.immediates, intrinsic.args = replacement
            logger.debug(f"Simplified {before} to {intrinsic}")
            self.modified += 1


def _try_convert_stack_args_to_immediates(
    intrinsic: models.Intrinsic,
) -> tuple[AVMOp, list[str | int], list[models.Value]] | None:
    match intrinsic.op:
        case AVMOp.gitxnas:
            (array_index_arg,) = intrinsic.args
            if (array_index := _extract_uint8(array_index_arg)) is not None:
                group_index_imm, field = intrinsic.immediates
                return AVMOp.gitxna, [group_index_imm, field, array_index], []
        case AVMOp.itxnas:
            (array_index_arg,) = intrinsic.args
            if (array_index := _extract_uint8(array_index_arg)) is not None:
                (field,) = intrinsic.immediates
                return AVMOp.itxna, [field, array_index], []
        case AVMOp.loads:
            (slot_arg,) = intrinsic.args
            if (slot := _extract_uint8(slot_arg)) is not None:
                return AVMOp.load, [slot], []
        case AVMOp.stores:
            slot_arg, value = intrinsic.args
            if (slot := _extract_uint8(slot_arg)) is not None:
                return AVMOp.store, [slot], [value]
        case AVMOp.extract3:
            bytes_arg, start_arg, length_arg = intrinsic.args
            if (
                (start := _extract_uint8(start_arg)) is not None
                and (length := _extract_uint8(length_arg)) is not None
                # note the lower bound of 1 on length, extract with immediates vs extract3
                # have *very* different behaviour if the length is 0
                and length >= 1
            ):
                return AVMOp.extract, [start, length], [bytes_arg]
        case AVMOp.substring3:
            bytes_arg, start_arg, end_arg = intrinsic.args
            if (start := _extract_uint8(start_arg)) is not None and (
                end := _extract_uint8(end_arg)
            ) is not None:
                return AVMOp.substring, [start, end], [bytes_arg]
        case AVMOp.replace3:
            a, start_arg, b = intrinsic.args
            if (start := _extract_uint8(start_arg)) is not None:
                return AVMOp.replace2, [start], [a, b]
        case AVMOp.args:
            (idx_arg,) = intrinsic.args
            if (idx := _extract_uint8(idx_arg)) is not None:
                return AVMOp.arg, [idx], []
        case AVMOp.gaids:
            (group_index_arg,) = intrinsic.args
            if (group_index := _extract_uint8(group_index_arg)) is not None:
                return AVMOp.gaid, [group_index], []
        case AVMOp.gloads:
            (group_index_arg,) = intrinsic.args
            if (group_index := _extract_uint8(group_index_arg)) is not None:
                (slot_imm,) = intrinsic.immediates
                return AVMOp.gload, [group_index, slot_imm], []
        case AVMOp.gloadss:
            group_index_arg, slot_arg = intrinsic.args
            if (slot := _extract_uint8(slot_arg)) is not None:
                if (group_index := _extract_uint8(group_index_arg)) is not None:
                    return AVMOp.gload, [group_index, slot], []
                return AVMOp.gloads, [slot], [group_index_arg]
        case AVMOp.txnas:
            (array_index_arg,) = intrinsic.args
            if (array_index := _extract_uint8(array_index_arg)) is not None:
                (field,) = intrinsic.immediates
                return AVMOp.txna, [field, array_index], []
        case AVMOp.gtxns:
            (group_index_arg,) = intrinsic.args
            if (group_index := _extract_uint8(group_index_arg)) is not None:
                (field,) = intrinsic.immediates
                return AVMOp.gtxn, [group_index, field], []
        case AVMOp.gtxnas:
            (array_index_arg,) = intrinsic.args
            if (array_index := _extract_uint8(array_index_arg)) is not None:
                group_index_imm, field = intrinsic.immediates
                return AVMOp.gtxna, [group_index_imm, field, array_index], []
        case AVMOp.gtxnsa:
            (group_index_arg,) = intrinsic.args
            if (group_index := _extract_uint8(group_index_arg)) is not None:
                field, array_index_imm = intrinsic.immediates
                return AVMOp.gtxna, [group_index, field, array_index_imm], []
        case AVMOp.gtxnsas:
            group_index_arg, array_index_arg = intrinsic.args
            (field,) = intrinsic.immediates
            if (group_index := _extract_uint8(group_index_arg)) is not None:
                if (array_index := _extract_uint8(array_index_arg)) is not None:
                    return AVMOp.gtxna, [group_index, field, array_index], []
                return AVMOp.gtxnas, [group_index, field], [array_index_arg]
            if (array_index := _extract_uint8(array_index_arg)) is not None:
                return AVMOp.gtxnsa, [field, array_index], [group_index_arg]
    return None


def _extract_uint8(arg: models.Value) -> int | None:
    match arg:
        case models.UInt64Constant(value=value) if value <= 255:
            return value
    return None
