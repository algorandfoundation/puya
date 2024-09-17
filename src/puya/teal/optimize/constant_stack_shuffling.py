import attrs

from puya.parse import sequential_source_locations_merge
from puya.teal import models
from puya.teal._util import combine_stack_manipulations
from puya.teal.optimize._data import LOAD_OP_CODES


def perform_constant_stack_shuffling(block: models.TealBlock) -> bool:
    result = list[models.TealOp]()
    loads = list[models.TealOp]()
    modified = False
    for op in block.ops:
        if _is_constant_load(op):
            loads.append(op)
        elif loads and op.op_code in ("dup", "dupn"):
            (n,) = op.immediates or (1,)
            assert isinstance(n, int)
            # extend loads with n copies of the last load
            loads.extend(
                [
                    attrs.evolve(
                        loads[-1],
                        stack_manipulations=(),
                        source_location=op.source_location,
                    )
                ]
                * n
            )
            # add dup stack manipulations to last load so overall stack manipulations are correct
            loads[-1] = combine_stack_manipulations(loads[-1], op)
            modified = True
        elif loads:
            match op:
                case models.Dig(n=n) if n < len(loads):
                    modified = True
                    dug = loads[-(n + 1)]
                    combined = combine_stack_manipulations(dug, op)
                    loads.append(combined)
                case models.Uncover(n=n) if n < len(loads):
                    modified = True
                    uncovered = loads.pop(-(n + 1))
                    combined = combine_stack_manipulations(uncovered, op)
                    loads.append(combined)
                case models.Cover(n=n) if n < len(loads):
                    modified = True
                    loads.insert(
                        len(loads) - n,
                        combine_stack_manipulations(loads.pop(), op),
                    )
                case _:
                    result.extend(loads)
                    loads = []
                    result.append(op)
        else:
            result.append(op)
    if loads:
        result.extend(loads)
    block.ops = result
    return modified


def constant_dupn_insertion(block: models.TealBlock) -> bool:
    result = list[models.TealOp]()
    loads = list[models.TealOp]()
    modified = False
    for op in block.ops:
        if loads and op == loads[0]:
            loads.append(op)
        else:
            if loads:
                modified = _collapse_loads(loads) or modified
                result.extend(loads)
                loads = []
            if _is_constant_load(op):
                loads.append(op)
            else:
                result.append(op)
    if loads:
        modified = _collapse_loads(loads) or modified
        result.extend(loads)
    block.ops = result
    return modified


def _collapse_loads(loads: list[models.TealOp]) -> bool:
    n = len(loads) - 1
    if n < 1:
        return False

    dup_source_location = sequential_source_locations_merge(op.source_location for op in loads[1:])
    if n == 1:
        dup_op: models.TealOp = models.Dup(source_location=dup_source_location)
    else:
        dup_op = models.DupN(n=n, source_location=dup_source_location)
    loads[1:] = [combine_stack_manipulations(dup_op, *loads[1:])]
    return True


def _is_constant_load(op: models.TealOp) -> bool:
    return op.op_code in LOAD_OP_CODES or (isinstance(op, models.FrameDig) and op.n < 0)
