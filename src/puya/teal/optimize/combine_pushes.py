import itertools
import typing
from collections.abc import Sequence

from puya.parse import sequential_source_locations_merge
from puya.teal import models


def combine_pushes(program: models.TealProgram) -> None:
    for block in itertools.chain.from_iterable(sub.blocks for sub in program.all_subroutines):
        pushes = list[models.PushInt | models.PushBytes]()
        result = list[models.TealOp]()
        for op in block.ops:
            if _is_different_push_type(pushes, op):
                result.append(_combine_ops(pushes))
                pushes = []
            if isinstance(op, models.PushInt | models.PushBytes):
                pushes.append(op)
            else:
                result.append(op)
        if pushes:
            result.append(_combine_ops(pushes))
        block.ops[:] = result


def _is_different_push_type(
    consecutive: list[models.PushInt | models.PushBytes], next_op: models.TealOp
) -> bool:
    return bool(consecutive) and type(consecutive[-1]) is not type(next_op)


def _combine_ops(consecutive: Sequence[models.PushInt | models.PushBytes]) -> models.TealOp:
    if len(consecutive) == 1:
        return consecutive[0]
    loc = sequential_source_locations_merge(op.source_location for op in consecutive)
    stack_manipulations = list(
        itertools.chain.from_iterable(op.stack_manipulations for op in consecutive)
    )
    if isinstance(consecutive[0], models.PushInt):
        consecutive = typing.cast(Sequence[models.PushInt], consecutive)
        return models.PushInts(
            values=[v.value for v in consecutive],
            stack_manipulations=stack_manipulations,
            source_location=loc,
            comment=_comment_ops(consecutive),
        )
    else:
        consecutive = typing.cast(Sequence[models.PushBytes], consecutive)
        return models.PushBytess(
            values=[(v.value, v.encoding) for v in consecutive],
            stack_manipulations=stack_manipulations,
            source_location=loc,
            comment=_comment_ops(consecutive),
        )


def _comment_ops(consecutive: Sequence[models.PushInt | models.PushBytes]) -> str:
    return ", ".join(
        map(str, ((v.comment or " ".join(map(str, v.immediates))) for v in consecutive))
    )
