import attrs

from puya import log
from puya.avm import AVMType
from puya.ir import models
from puya.ir.avm_ops import AVMOp
from puya.ir.optimize.context import IROptimizationContext

logger = log.get_logger(__name__)


def convert_stack_args_to_immediates(
    _context: IROptimizationContext, subroutine: models.Subroutine
) -> bool:
    modified = 0
    for block in subroutine.body:
        ops = []
        for op in block.ops:
            ops.append(op)
            match op:
                case models.Assignment(source=models.Intrinsic(args=args) as intrinsic) if args:
                    with_immediates = _try_convert_stack_args_to_immediates(intrinsic)
                    if with_immediates is not None:
                        logger.debug(f"Simplified {op.source} to {with_immediates}")
                        op.source = with_immediates
                        modified += 1
                case models.Intrinsic(args=args) as intrinsic if args:
                    with_immediates = _try_convert_stack_args_to_immediates(intrinsic)
                    if with_immediates is not None:
                        logger.debug(f"Simplified {op} to {with_immediates}")
                        ops[-1] = with_immediates
                        modified += 1
        block.ops[:] = ops
    return modified > 0


def _try_convert_stack_args_to_immediates(intrinsic: models.Intrinsic) -> models.Intrinsic | None:
    match intrinsic:
        case models.Intrinsic(
            op=AVMOp.gitxnas,
            args=[models.UInt64Constant(value=array_index)],
            immediates=[group_index, field],
        ) if array_index <= 255:
            return attrs.evolve(
                intrinsic,
                op=AVMOp.gitxna,
                args=[],
                immediates=[group_index, field, array_index],
            )
        case models.Intrinsic(
            op=AVMOp.itxnas,
            args=[models.UInt64Constant(value=array_index)],
            immediates=[field],
        ) if array_index <= 255:
            return attrs.evolve(
                intrinsic,
                op=AVMOp.itxna,
                args=[],
                immediates=[field, array_index],
            )
        case models.Intrinsic(
            op=(AVMOp.loads | AVMOp.stores as op),
            args=[models.UInt64Constant(value=slot), *rest],
        ) if slot <= 255:
            return attrs.evolve(
                intrinsic,
                immediates=[slot],
                args=rest,
                op=AVMOp.load if op == AVMOp.loads else AVMOp.store,
            )
        case models.Intrinsic(
            op=AVMOp.extract3,
            args=[
                models.Value(atype=AVMType.bytes),
                models.UInt64Constant(value=S),
                models.UInt64Constant(value=L),
            ],
        ) if S <= 255 and 1 <= L <= 255:
            # note the lower bound of 1 on length, extract with immediates vs extract3
            # have *very* different behaviour if the length is 0
            return attrs.evolve(
                intrinsic, immediates=[S, L], args=intrinsic.args[:1], op=AVMOp.extract
            )
        case models.Intrinsic(
            op=AVMOp.substring3,
            args=[
                models.Value(atype=AVMType.bytes),
                models.UInt64Constant(value=S),
                models.UInt64Constant(value=E),
            ],
        ) if S <= 255 and E <= 255:
            return attrs.evolve(
                intrinsic, immediates=[S, E], args=intrinsic.args[:1], op=AVMOp.substring
            )
        case models.Intrinsic(
            op=AVMOp.replace3,
            args=[a, models.UInt64Constant(value=S), b],
        ) if S <= 255:
            return attrs.evolve(intrinsic, immediates=[S], args=[a, b], op=AVMOp.replace2)
        case models.Intrinsic(
            op=AVMOp.args,
            args=[models.UInt64Constant(value=idx)],
        ) if idx <= 255:
            return attrs.evolve(intrinsic, op=AVMOp.arg, immediates=[idx], args=[])
        case models.Intrinsic(
            op=AVMOp.gaids,
            args=[models.UInt64Constant(value=group_index)],
        ) if group_index <= 255:
            return attrs.evolve(intrinsic, op=AVMOp.gaid, immediates=[group_index], args=[])
        case models.Intrinsic(
            op=AVMOp.gloads,
            args=[models.UInt64Constant(value=group_index)],
            immediates=[slot],
        ) if group_index <= 255:
            return attrs.evolve(intrinsic, op=AVMOp.gload, immediates=[group_index, slot], args=[])
        case models.Intrinsic(
            op=AVMOp.gloadss,
            args=[
                models.UInt64Constant(value=group_index),
                models.UInt64Constant(value=slot),
            ],
        ) if group_index <= 255 and slot <= 255:
            return attrs.evolve(intrinsic, op=AVMOp.gload, immediates=[group_index, slot], args=[])
        case models.Intrinsic(
            op=AVMOp.gloadss,
            args=[group_index_arg, models.UInt64Constant(value=slot)],
        ) if slot <= 255:
            return attrs.evolve(
                intrinsic, op=AVMOp.gloads, immediates=[slot], args=[group_index_arg]
            )
        case models.Intrinsic(
            op=AVMOp.txnas,
            args=[models.UInt64Constant(value=array_index)],
            immediates=[field],
        ) if array_index <= 255:
            return attrs.evolve(intrinsic, op=AVMOp.txna, immediates=[field, array_index], args=[])
        case models.Intrinsic(
            op=AVMOp.gtxns,
            args=[models.UInt64Constant(value=group_index)],
            immediates=[field],
        ) if group_index <= 255:
            return attrs.evolve(intrinsic, op=AVMOp.gtxn, immediates=[group_index, field], args=[])
        case models.Intrinsic(
            op=AVMOp.gtxnas,
            args=[models.UInt64Constant(value=array_index)],
            immediates=[group_index, field],
        ) if array_index <= 255:
            return attrs.evolve(
                intrinsic,
                op=AVMOp.gtxna,
                immediates=[group_index, field, array_index],
                args=[],
            )
        case models.Intrinsic(
            op=AVMOp.gtxnsa,
            args=[models.UInt64Constant(value=group_index)],
            immediates=[field, array_index],
        ) if group_index <= 255:
            return attrs.evolve(
                intrinsic,
                op=AVMOp.gtxna,
                immediates=[group_index, field, array_index],
                args=[],
            )
        case models.Intrinsic(
            op=AVMOp.gtxnsas,
            args=[
                models.UInt64Constant(value=group_index),
                models.UInt64Constant(value=array_index),
            ],
            immediates=[field],
        ) if group_index <= 255 and array_index <= 255:
            return attrs.evolve(
                intrinsic,
                op=AVMOp.gtxna,
                immediates=[group_index, field, array_index],
                args=[],
            )
        case models.Intrinsic(
            op=AVMOp.gtxnsas,
            args=[models.UInt64Constant(value=group_index), array_index_arg],
            immediates=[field],
        ) if group_index <= 255:
            return attrs.evolve(
                intrinsic,
                op=AVMOp.gtxnas,
                immediates=[group_index, field],
                args=[array_index_arg],
            )
        case models.Intrinsic(
            op=AVMOp.gtxnsas,
            args=[group_index_arg, models.UInt64Constant(value=array_index)],
            immediates=[field],
        ) if array_index <= 255:
            return attrs.evolve(
                intrinsic,
                op=AVMOp.gtxnsa,
                immediates=[field, array_index],
                args=[group_index_arg],
            )
    return None
