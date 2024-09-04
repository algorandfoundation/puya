import typing
from collections.abc import Sequence

import attrs

from puya.errors import InternalError
from puya.teal import models

_T = typing.TypeVar("_T", bound=models.TealOp)


def preserve_stack_manipulations(
    new: Sequence[_T], original: Sequence[models.TealOp | models.StackManipulation]
) -> Sequence[_T]:
    """Replaces all stack manipulations on new, with stack manipulations from original

    Note: stack manipulations will all be placed on last op on new"""
    if not new:
        raise ValueError("expected a non empty sequence to put stack manipulations on")
    # clear existing stack_manipulations on new sequence
    new = [attrs.evolve(op, stack_manipulations=()) for op in new]
    stack_manipulations = [
        sm
        for op in original
        for sm in (op.stack_manipulations if isinstance(op, models.TealOp) else [op])
    ]
    # add stack manipulations to last op in new sequence
    new[-1] = attrs.evolve(
        new[-1],
        stack_manipulations=stack_manipulations,
    )
    return new


def preserve_stack_manipulations_window(
    ops: list[_T],
    window: slice,
    new: Sequence[_T],
) -> None:
    """Replaces window of ops with new, preserving any stack manipulations from original window

    new is not empty: added to last op in new
    new is empty, window starts after first index: appended to prior op
    new is empty, window ends before last index: prepended to subsequent op
    """
    if not new:
        # expand window to include at least 1 op
        if window.start > 0:
            # expand window to prior op
            window = slice(window.start - 1, window.stop)
            new = [ops[window.start]]
        elif window.stop < len(ops):  # must be start of a block
            # expand window to subsequent op
            new = [ops[window.stop]]
            window = slice(window.start, window.stop + 1)
        else:
            # can this even happen? if it does, maybe attach to block instead?
            raise InternalError("could not preserve stack manipulations")
    ops[window] = preserve_stack_manipulations(
        new, [sm for op in ops[window] for sm in op.stack_manipulations]
    )
