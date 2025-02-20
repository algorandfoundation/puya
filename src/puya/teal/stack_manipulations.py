import typing
from collections.abc import Sequence

from puya.errors import InternalError
from puya.teal import models


class StackOutOfBoundsError(InternalError):
    pass


def apply_stack_manipulations(
    stack_manipulations: Sequence[models.StackManipulation],
    stack: list[str],
    defined: set[str],
) -> None:
    for sm in stack_manipulations:
        match sm:
            case models.StackConsume(n=n):
                try:
                    for _ in range(n):
                        stack.pop()
                except IndexError as ex:
                    raise StackOutOfBoundsError("stack is empty") from ex
            case models.StackExtend() as se:
                stack.extend(se.local_ids)
            case models.StackDefine() as sd:
                defined.update(sd.local_ids)
            case models.StackInsert(depth=depth, local_id=local_id):
                index = len(stack) - depth
                if index < 0 or index > len(stack):
                    raise StackOutOfBoundsError(f"stack insert at index {index} is out of bounds")
                stack.insert(index, local_id)
            case models.StackPop(depth=depth):
                index = len(stack) - depth - 1
                try:
                    stack.pop(index)
                except IndexError as ex:
                    raise StackOutOfBoundsError(
                        f"stack pop at index {index} is out of bounds"
                    ) from ex
            case _:
                typing.assert_never(sm)
