from collections.abc import Sequence

import attrs

from puya.errors import InternalError
from puya.teal import models
from puya.teal.stack_manipulations import StackOutOfBoundsError, apply_stack_manipulations
from puya.utils import coalesce


def preserve_stack_manipulations[T: models.TealOp](
    ops: list[T], window: slice, new: Sequence[T]
) -> None:
    """Replaces window of ops with new, preserving any stack manipulations from original window
    if the sequences are not equivalent.

    new is not empty: added to last op in new
    new is empty, window starts after first index: appended to prior op
    new is empty, window ends before last index: prepended to subsequent op
    """
    assert window.step in (1, None), "window step must be 1"
    window_start = window.start
    assert window_start is not None and window_start >= 0, "window start must be non-negative"
    window_stop = coalesce(window.stop, len(ops))
    assert window_stop >= window_start, "window stop must be non-negative"

    is_pure_deletion = not new
    if is_pure_deletion:
        if window_start > 0:
            # shove it all on the prior op
            window_start -= 1
            new = [ops[window_start]]
        elif window_stop < len(ops):  # must be start of a block
            new = [ops[window_stop]]
            window_stop += 1
        else:
            raise InternalError(
                "could not preserve stack manipulations due to entire block deletion"
            )
        window = slice(window_start, window_stop)

    original_sm = [sm for op in ops[window] for sm in op.stack_manipulations]
    new_sm = [sm for op in new for sm in op.stack_manipulations]
    if is_pure_deletion or not _stack_manipulations_are_equivalent(original_sm, new_sm):
        # clear existing stack_manipulations on new sequence
        new = [attrs.evolve(op, stack_manipulations=()) for op in new]
        # add original stack manipulations to last op in new sequence
        new[-1] = attrs.evolve(new[-1], stack_manipulations=original_sm)

    # replace original ops with new ops
    ops[window] = new


def _stack_manipulations_are_equivalent(
    a: Sequence[models.StackManipulation], b: Sequence[models.StackManipulation]
) -> bool:
    if a == b:
        return True

    try:
        stack_a, defined_a = _apply_stack_manipulations(a)
        stack_b, defined_b = _apply_stack_manipulations(b)
    except StackOutOfBoundsError:
        # we don't simulate the f-stack, x-stack, or even the l-stack prior to this
        # window of ops, so out of bounds access is totally expected at some points.
        # at the time of writing this comment, tracking all the above was implemented,
        # and it only made a difference with repeated-rotations-search which is O2 only,
        # so not worth the digital plumbing
        return False
    stacks_same = stack_a == stack_b
    defines_same = defined_a == defined_b
    return stacks_same and defines_same


def _apply_stack_manipulations(
    sm: Sequence[models.StackManipulation],
) -> tuple[list[str], set[str]]:
    stack = list[str]()
    defined = set[str]()
    apply_stack_manipulations(sm, stack, defined)
    return stack, defined
