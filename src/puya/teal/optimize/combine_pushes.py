import itertools
import typing
from collections.abc import Sequence

from puya.parse import sequential_source_locations_merge
from puya.teal import models


def combine_pushes(program: models.TealProgram) -> None:
    for block in itertools.chain.from_iterable(sub.blocks for sub in program.all_subroutines):
        result = list[models.TealOp]()
        for push_type, group in itertools.groupby(block.ops, key=_push_type):
            ops = list(group)
            if push_type is None or len(ops) < 2:
                result.extend(ops)
            else:
                loc = sequential_source_locations_merge(op.source_location for op in ops)
                stack_manipulations = list(
                    itertools.chain.from_iterable(op.stack_manipulations for op in ops)
                )
                if push_type == "int":
                    consecutive_i = typing.cast(Sequence[models.PushInt], ops)
                    result.append(
                        models.PushInts(
                            values=[v.value for v in consecutive_i],
                            stack_manipulations=stack_manipulations,
                            source_location=loc,
                            comments=[op.comment for op in consecutive_i],
                        )
                    )
                else:
                    typing.assert_type(push_type, typing.Literal["bytes"])
                    consecutive_b = typing.cast(Sequence[models.PushBytes], ops)
                    result.append(
                        models.PushBytess(
                            values=[(v.value, v.encoding) for v in consecutive_b],
                            stack_manipulations=stack_manipulations,
                            source_location=loc,
                            comments=[op.comment for op in consecutive_b],
                        )
                    )
        block.ops[:] = result


def _push_type(op: models.TealOp) -> typing.Literal["int", "bytes", None]:
    if type(op) is models.PushInt:
        return "int"
    if type(op) is models.PushBytes:
        return "bytes"
    return None
