import operator
import typing
from collections import Counter
from functools import reduce

from puya.ussemble import models
from puya.ussemble.context import AssembleContext

MAX_CONSTANT_INDEX = 255
_T = typing.TypeVar("_T", int, bytes)


def optimize_ops(ctx: AssembleContext, ops: list[models.Node]) -> list[models.Node]:
    ops = populate_constant_blocks(ops)
    if not ctx.options.match_algod_bytecode:
        ops = combine_pushes(ops)
    return ops


def populate_constant_blocks(ops: list[models.Node]) -> list[models.Node]:
    all_ints = list[int]()
    all_bytes = list[bytes]()

    # collect constants
    for op in ops:
        match op:
            case models.PushInt(value=int_value):
                all_ints.append(int_value)
            case models.PushBytes(value=bytes_value):
                all_bytes.append(bytes_value)

    # determine constant blocks
    int_block = _get_constants(all_ints)
    bytes_block = _get_constants(all_bytes)
    if not int_block and not bytes_block:
        return ops

    # replace reads
    result = list[models.Node]()
    if int_block:
        result.append(models.IntBlock(constants=int_block, source_location=None))
    if bytes_block:
        result.append(models.BytesBlock(constants=bytes_block, source_location=None))
    for op in ops:
        match op:
            case models.PushInt(value=int_value, source_location=loc):
                try:
                    const_index = int_block[int_value]
                except KeyError:
                    pass
                else:
                    op = models.IntC(index=const_index, source_location=loc)
            case models.PushBytes(value=bytes_value, source_location=loc):
                try:
                    const_index = bytes_block[bytes_value]
                except KeyError:
                    pass
                else:
                    op = models.BytesC(index=const_index, source_location=loc)
        result.append(op)

    return result


def combine_pushes(ops: list[models.Node]) -> list[models.Node]:
    result = list[models.Node]()
    pushes = list[models.PushInt | models.PushBytes]()
    for op in ops:
        if _is_different_push_type(pushes, op):
            if pushes:
                result.append(_combine_ops(pushes))
            pushes = []
        if isinstance(op, models.PushInt | models.PushBytes):
            pushes.append(op)
        else:
            result.append(op)
    if pushes:
        result.append(_combine_ops(pushes))
    return result


def _is_different_push_type(
    consecutive: list[models.PushInt | models.PushBytes], next_op: models.Node
) -> bool:
    return bool(consecutive) and type(consecutive[-1]) is not type(next_op)


def _combine_ops(consecutive: list[models.PushInt | models.PushBytes]) -> models.Node:
    if len(consecutive) == 1:
        return consecutive[0]
    values = [op.value for op in consecutive]
    loc = reduce(operator.add, filter(None, (op.source_location for op in consecutive)))
    if isinstance(values[0], int):
        int_values = [int(v) for v in values]
        return models.PushInts(values=int_values, source_location=loc)
    else:
        bytes_values = [bytes(v) for v in values]
        return models.PushBytess(values=bytes_values, source_location=loc)


def _get_constants(values: list[_T]) -> dict[_T, int]:
    counter = Counter(values)
    multiple = [value for value, freq in counter.most_common() if freq > 1]
    return {value: index for index, value in enumerate(multiple) if index <= MAX_CONSTANT_INDEX}
