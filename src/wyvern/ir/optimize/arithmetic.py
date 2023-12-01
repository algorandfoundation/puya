import attrs
import structlog

from wyvern.codegen.utils import format_bytes
from wyvern.context import CompileContext
from wyvern.ir import models
from wyvern.ir.avm_ops import AVMOp
from wyvern.ir.types_ import AVMType

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(__name__)


def get_int_constant(value: models.ValueProvider) -> int | None:
    if isinstance(value, models.UInt64Constant):
        return value.value
    return None


def try_simplify_arithmetic_ops(value: models.ValueProvider) -> models.ValueProvider | None:
    # TODO: handle bytes math
    # TODO: handle all math ops including shl, shr, exp, etc
    match value:
        case models.Intrinsic(
            args=[models.UInt64Constant(value=x)], op=AVMOp.not_, source_location=op_loc
        ):
            not_x = models.UInt64Constant(source_location=op_loc, value=0 if x else 1)
            logger.debug(f"Folded !{x} to {not_x}")
            return not_x
        case models.Intrinsic(
            op=AVMOp.len_,
            args=[models.BytesConstant(value=x, encoding=encoding)],
            source_location=op_loc,
        ):
            len_x = len(x)
            logger.debug(f"Folded len({format_bytes(x, encoding)}) to {len_x}")
            return models.UInt64Constant(source_location=op_loc, value=len_x)
        case models.Intrinsic(
            args=[
                models.Value(atype=AVMType.uint64) as a,
                models.Value(atype=AVMType.uint64) as b,
            ],
            op=op,
        ):
            c: int | models.Value | None = None
            a_const = get_int_constant(a)
            b_const = get_int_constant(b)
            if a == b:
                match op:
                    case AVMOp.sub:
                        c = 0
                    case AVMOp.eq:
                        c = 1
                    case AVMOp.neq:
                        c = 0
                    case AVMOp.div_floor:
                        c = 1
            # 0 == b <-> !b
            elif a_const == 0 and op == AVMOp.eq:
                return attrs.evolve(value, op=AVMOp.not_, args=[b])
            # a == 0 <-> !a
            elif b_const == 0 and op == AVMOp.eq:
                return attrs.evolve(value, op=AVMOp.not_, args=[a])
            # TODO: can we somehow do the below only in a boolean context?
            # # 0 != b <-> b
            # elif a_const == 0 and op == AVMOp.neq:
            #     c = b
            # # a != 0 <-> a
            # elif b_const == 0 and op == AVMOp.neq:
            #     c = a
            elif a_const == 1 and op == AVMOp.mul:
                c = b
            elif b_const == 1 and op == AVMOp.mul:
                c = a
            elif a_const == 0 and op in (AVMOp.add, AVMOp.sub, AVMOp.or_):
                c = b
            elif b_const == 0 and op in (AVMOp.add, AVMOp.sub, AVMOp.or_):
                c = a
            elif 0 in (a_const, b_const) and op in (AVMOp.mul, AVMOp.and_):
                c = 0
            elif a_const is not None and b_const is not None:
                match op:
                    case AVMOp.add:
                        c = a_const + b_const
                    case AVMOp.sub:
                        c = a_const - b_const
                    case AVMOp.mul:
                        c = a_const * b_const
                    case AVMOp.div_floor:
                        c = a_const // b_const
                    case AVMOp.lt:
                        c = 1 if a_const < b_const else 0
                    case AVMOp.lte:
                        c = 1 if a_const <= b_const else 0
                    case AVMOp.gt:
                        c = 1 if a_const > b_const else 0
                    case AVMOp.gte:
                        c = 1 if a_const >= b_const else 0
                    case AVMOp.eq:
                        c = 1 if a_const == b_const else 0
                    case AVMOp.neq:
                        c = 1 if a_const != b_const else 0
            if c is not None:
                if isinstance(c, models.ValueProvider):
                    logger.debug(f"Folded {a} {op} {b} to {c}")
                    return c
                else:
                    logger.debug(f"Folded {a_const} {op} {b_const} to {c}")
                    return models.UInt64Constant(value=c, source_location=value.source_location)
    return None


def arithmetic_simplification(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    """Simplify arithmetic expressions e.g. a-a -> 0, a*0 -> 0, a*1 -> a"""
    modified = 0

    for block in subroutine.body:
        for op in block.ops:
            match op:
                case models.Assignment(source=source) as assignment:
                    simplified = try_simplify_arithmetic_ops(source)
                    if simplified is not None:
                        assignment.source = simplified
                        modified += 1

    return modified > 0
