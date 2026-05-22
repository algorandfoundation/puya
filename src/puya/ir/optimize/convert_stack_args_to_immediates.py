import typing

import attrs

from puya import log
from puya.avm import AVMType
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
    match intrinsic:
        case models.Intrinsic(
            op=AVMOp.gitxnas,
            args=[models.UInt64Constant(value=array_index)],
            immediates=[group_index, field],
        ) if array_index <= 255:
            return AVMOp.gitxna, [group_index, field, array_index], []
        case models.Intrinsic(
            op=AVMOp.itxnas,
            args=[models.UInt64Constant(value=array_index)],
            immediates=[field],
        ) if array_index <= 255:
            return AVMOp.itxna, [field, array_index], []
        case models.Intrinsic(
            op=(AVMOp.loads | AVMOp.stores as op),
            args=[models.UInt64Constant(value=slot), *rest],
        ) if slot <= 255:
            return AVMOp.load if op == AVMOp.loads else AVMOp.store, [slot], rest
        case models.Intrinsic(
            op=AVMOp.extract3,
            args=[
                models.Value(atype=AVMType.bytes) as bytes_arg,
                models.UInt64Constant(value=S),
                models.UInt64Constant(value=L),
            ],
        ) if S <= 255 and 1 <= L <= 255:
            # note the lower bound of 1 on length, extract with immediates vs extract3
            # have *very* different behaviour if the length is 0
            return AVMOp.extract, [S, L], [bytes_arg]
        case models.Intrinsic(
            op=AVMOp.substring3,
            args=[
                models.Value(atype=AVMType.bytes) as bytes_arg,
                models.UInt64Constant(value=S),
                models.UInt64Constant(value=E),
            ],
        ) if S <= 255 and E <= 255:
            return AVMOp.substring, [S, E], [bytes_arg]
        case models.Intrinsic(
            op=AVMOp.replace3,
            args=[a, models.UInt64Constant(value=S), b],
        ) if S <= 255:
            return AVMOp.replace2, [S], [a, b]
        case models.Intrinsic(
            op=AVMOp.args,
            args=[models.UInt64Constant(value=idx)],
        ) if idx <= 255:
            return AVMOp.arg, [idx], []
        case models.Intrinsic(
            op=AVMOp.gaids,
            args=[models.UInt64Constant(value=group_index)],
        ) if group_index <= 255:
            return AVMOp.gaid, [group_index], []
        case models.Intrinsic(
            op=AVMOp.gloads,
            args=[models.UInt64Constant(value=group_index)],
            immediates=[slot],
        ) if group_index <= 255:
            return AVMOp.gload, [group_index, slot], []
        case models.Intrinsic(
            op=AVMOp.gloadss,
            args=[
                models.UInt64Constant(value=group_index),
                models.UInt64Constant(value=slot),
            ],
        ) if group_index <= 255 and slot <= 255:
            return AVMOp.gload, [group_index, slot], []
        case models.Intrinsic(
            op=AVMOp.gloadss,
            args=[group_index_arg, models.UInt64Constant(value=slot)],
        ) if slot <= 255:
            return AVMOp.gloads, [slot], [group_index_arg]
        case models.Intrinsic(
            op=AVMOp.txnas,
            args=[models.UInt64Constant(value=array_index)],
            immediates=[field],
        ) if array_index <= 255:
            return AVMOp.txna, [field, array_index], []
        case models.Intrinsic(
            op=AVMOp.gtxns,
            args=[models.UInt64Constant(value=group_index)],
            immediates=[field],
        ) if group_index <= 255:
            return AVMOp.gtxn, [group_index, field], []
        case models.Intrinsic(
            op=AVMOp.gtxnas,
            args=[models.UInt64Constant(value=array_index)],
            immediates=[group_index, field],
        ) if array_index <= 255:
            return AVMOp.gtxna, [group_index, field, array_index], []
        case models.Intrinsic(
            op=AVMOp.gtxnsa,
            args=[models.UInt64Constant(value=group_index)],
            immediates=[field, array_index],
        ) if group_index <= 255:
            return AVMOp.gtxna, [group_index, field, array_index], []
        case models.Intrinsic(
            op=AVMOp.gtxnsas,
            args=[
                models.UInt64Constant(value=group_index),
                models.UInt64Constant(value=array_index),
            ],
            immediates=[field],
        ) if group_index <= 255 and array_index <= 255:
            return AVMOp.gtxna, [group_index, field, array_index], []
        case models.Intrinsic(
            op=AVMOp.gtxnsas,
            args=[models.UInt64Constant(value=group_index), array_index_arg],
            immediates=[field],
        ) if group_index <= 255:
            return AVMOp.gtxnas, [group_index, field], [array_index_arg]
        case models.Intrinsic(
            op=AVMOp.gtxnsas,
            args=[group_index_arg, models.UInt64Constant(value=array_index)],
            immediates=[field],
        ) if array_index <= 255:
            return AVMOp.gtxnsa, [field, array_index], [group_index_arg]
    return None
