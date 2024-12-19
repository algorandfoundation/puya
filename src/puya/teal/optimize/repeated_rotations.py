from collections.abc import Sequence

from puya.teal import models
from puya.teal._util import preserve_stack_manipulations


def _simplify_repeated_rotation_ops(
    maybe_simplify: list[models.Cover | models.Uncover],
) -> tuple[Sequence[models.Cover | models.Uncover], bool]:
    first = maybe_simplify[0]
    is_cover = isinstance(first, models.Cover)
    n = first.n
    number_of_ops = len(maybe_simplify)
    number_of_inverse = n + 1 - number_of_ops
    while number_of_inverse < 0:
        number_of_inverse += n + 1
    if number_of_inverse >= number_of_ops:
        return maybe_simplify, False
    inverse_op: models.Cover | models.Uncover = (
        models.Uncover(n=n, source_location=first.source_location)
        if is_cover
        else models.Cover(n=n, source_location=first.source_location)
    )
    simplified = [inverse_op] * number_of_inverse
    return simplified, True


def simplify_repeated_rotation_ops(block: models.TealBlock) -> bool:
    result = block.ops.copy()
    maybe_simplify = list[models.Cover | models.Uncover]()
    modified = False
    end_idx = 0
    while end_idx < len(result):
        op = result[end_idx]
        if isinstance(op, models.Cover | models.Uncover) and (
            not maybe_simplify or op == maybe_simplify[0]
        ):
            maybe_simplify.append(op)
        else:
            if maybe_simplify:
                maybe_simplified, modified_ = _simplify_repeated_rotation_ops(maybe_simplify)
                modified = modified or modified_
                preserve_stack_manipulations(
                    result, slice(end_idx - len(maybe_simplify), end_idx), maybe_simplified
                )
                end_idx += len(maybe_simplified) - len(maybe_simplify)
                maybe_simplify = []
            if isinstance(op, models.Cover | models.Uncover):
                maybe_simplify.append(op)
        end_idx += 1
    if maybe_simplify:
        maybe_simplified, modified_ = _simplify_repeated_rotation_ops(maybe_simplify)
        modified = modified or modified_
        idx = len(result)
        preserve_stack_manipulations(
            result, slice(idx - len(maybe_simplify), idx), maybe_simplified
        )
    block.ops[:] = result
    return modified


def simplify_swap_ops(block: models.TealBlock) -> bool:
    result = list[models.TealOp]()
    modified = False
    for op in block.ops:
        if isinstance(op, models.Cover | models.Uncover) and (op.n == 1):
            modified = True
            result.append(
                models.Swap(
                    source_location=op.source_location, stack_manipulations=op.stack_manipulations
                )
            )
        else:
            result.append(op)
    block.ops[:] = result
    return modified
