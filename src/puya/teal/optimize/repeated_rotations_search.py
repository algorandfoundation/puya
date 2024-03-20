import functools
import itertools
import typing
from collections.abc import Sequence

import attrs

from puya import log
from puya.teal import models

TealOpSequence = tuple[models.TealOpN, ...]
logger = log.get_logger(__name__)


class InvalidOpSequenceError(Exception):
    pass


@attrs.define
class TealStack:
    stack: list[int]

    @classmethod
    def from_stack_size(cls, stack_size: int) -> "TealStack":
        return cls(stack=list(range(stack_size)))

    def apply(self, ops: Sequence[models.TealOpN]) -> "TealStack":
        stack = TealStack(self.stack.copy())
        for op in ops:
            n = op.n
            if n:
                index = len(stack.stack) - n - 1
                if index < 0 or index >= len(stack.stack):
                    raise InvalidOpSequenceError
                match op.op_code:
                    case "cover":
                        stack.stack.insert(index, stack.stack.pop())
                    case "uncover":
                        stack.stack.append(stack.stack.pop(index))
                    case _:
                        raise InvalidOpSequenceError
        return stack


@functools.cache
def simplify_rotation_ops(original_ops: TealOpSequence) -> TealOpSequence | None:
    num_rot_ops = len(original_ops)
    max_rot_op_n = 0
    for o in original_ops:
        max_rot_op_n = max(max_rot_op_n, o.n)

    original_stack = TealStack.from_stack_size(max_rot_op_n + 1)

    expected = original_stack.apply(original_ops)
    # entire sequence can be removed!
    if expected == original_stack:
        return ()

    possible_rotation_ops = get_possible_rotation_ops(max_rot_op_n)
    original_stack_result = original_stack.apply(original_ops)

    # TODO: use a non-bruteforce approach and/or capture common simplifications as data
    for num_rotation_ops in range(num_rot_ops):
        for maybe_ops in itertools.permutations(possible_rotation_ops, num_rotation_ops):
            try:
                stack = original_stack.apply(maybe_ops)
            except InvalidOpSequenceError:
                continue
            if expected == stack:
                assert original_stack_result == original_stack.apply(maybe_ops)
                return tuple(attrs.evolve(op, source_location=None) for op in maybe_ops)
    return None


@functools.cache
def get_possible_rotation_ops(n: int) -> TealOpSequence:
    possible_ops = list[models.TealOpN]()
    for i in range(1, n + 1):
        possible_ops.append(models.Cover(i, source_location=None))
        possible_ops.append(models.Uncover(i, source_location=None))
    return tuple(possible_ops)


ROTATION_SIMPLIFY_OPS = frozenset(
    [
        "cover",
        "uncover",
    ]
)


def repeated_rotation_ops_search(teal_ops: list[models.TealOp]) -> list[models.TealOp]:
    maybe_remove_rotations = list[models.TealOpN]()
    result = list[models.TealOp]()
    for teal_op in teal_ops:
        if teal_op.op_code in ROTATION_SIMPLIFY_OPS:
            maybe_remove_rotations.append(typing.cast(models.TealOpN, teal_op))
        else:
            maybe_simplified = _maybe_simplified(maybe_remove_rotations)
            maybe_remove_rotations = []
            result.extend(maybe_simplified)
            result.append(teal_op)
    result.extend(_maybe_simplified(maybe_remove_rotations))
    return result


def _maybe_simplified(
    maybe_remove_rotations: list[models.TealOpN], window_size: int = 5
) -> Sequence[models.TealOpN]:
    if len(maybe_remove_rotations) < 2:
        return maybe_remove_rotations

    for start_idx in range(len(maybe_remove_rotations) - 1):
        window = maybe_remove_rotations[start_idx : start_idx + window_size + 1]
        simplified = simplify_rotation_ops(tuple(window))
        if simplified is not None:
            logger.debug(
                f"Replaced '{'; '.join(map(str, maybe_remove_rotations))}'"
                f" with '{'; '.join(map(str, simplified))}',"
                f" reducing by {len(maybe_remove_rotations) - len(simplified)} ops by search"
            )
            result_ = maybe_remove_rotations.copy()
            result_[start_idx : start_idx + window_size + 1] = simplified
            assert result_ != maybe_remove_rotations
            return result_
    return maybe_remove_rotations
