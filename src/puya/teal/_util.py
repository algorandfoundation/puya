import typing

import attrs

from puya.teal import models

_T = typing.TypeVar("_T", bound=models.TealOp)


def combine_stack_manipulations(base_op: _T, *others: models.TealOp) -> _T:
    return attrs.evolve(
        base_op,
        stack_manipulations=simplify_stack_manipulations(
            [
                *base_op.stack_manipulations,
                *(sm for op in others for sm in op.stack_manipulations),
            ]
        ),
    )


def simplify_stack_manipulations(
    stack_manipulations: list[models.StackManipulation],
) -> list[models.StackManipulation]:
    return stack_manipulations
    # TODO: make this work?
    result = []
    for sm in stack_manipulations:
        if sm.manipulation != "remove":
            result.append(sm)
            continue
        # if manipulation is a remove, attempt to locate and remove a prior insert
        for idx in reversed(range(len(result))):
            maybe_add = result[idx]
            if (
                maybe_add.stack == sm.stack
                and maybe_add.local_id == sm.local_id
                and maybe_add.manipulation == "insert"
            ):
                # match found, pop add and discard remove
                result.pop(idx)
                break
        else:
            # no match found, so keep remove
            result.append(sm)
    return result
