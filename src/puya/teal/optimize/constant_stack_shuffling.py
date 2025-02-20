import attrs

from puya.parse import sequential_source_locations_merge
from puya.teal import models
from puya.teal._util import preserve_stack_manipulations
from puya.teal.optimize._data import LOAD_OP_CODES


def perform_constant_stack_shuffling(block: models.TealBlock) -> bool:
    result = block.ops.copy()
    loads = list[models.TealOp]()
    loads_modified = modified = False
    start_idx = idx = 0
    while idx < len(result):
        op = result[idx]
        if _is_constant_load(op):
            if not loads:
                start_idx = idx
                loads_modified = False
            loads.append(op)
        elif loads and op.op_code in ("dup", "dupn"):
            modified = loads_modified = True
            (n,) = op.immediates or (1,)
            assert isinstance(n, int)
            # extend loads with n copies of the last load
            last_load = loads[-1]
            repeated_load = attrs.evolve(
                last_load, source_location=op.source_location, stack_manipulations=[]
            )
            repeated_loads = [repeated_load] * n
            repeated_loads[-1] = attrs.evolve(
                repeated_loads[-1], stack_manipulations=op.stack_manipulations
            )
            loads.extend(repeated_loads)
        elif loads:
            match op:
                case models.Uncover(n=n) if n < len(loads):
                    modified = loads_modified = True
                    uncovered = loads.pop(-(n + 1))
                    loads.append(uncovered)
                case models.Cover(n=n) if n < len(loads):
                    modified = loads_modified = True
                    covered = loads.pop()
                    loads.insert(len(loads) - n, covered)
                case _:
                    if loads_modified:
                        window = slice(start_idx, idx)
                        preserve_stack_manipulations(result, window, loads)
                        idx = start_idx + len(loads)
                    loads = []
        idx += 1

    if loads_modified and loads:
        window = slice(start_idx, len(result))
        preserve_stack_manipulations(result, window, loads)
    block.ops[:] = result
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
    block.ops[:] = result
    return modified


def constant_dup2_insertion(block: models.TealBlock) -> bool:
    result = block.ops
    modified = False
    idx = 0
    while (idx + 4) <= len(block.ops):
        load_a, load_b, load_a2, load_b2 = block.ops[idx : idx + 4]
        if (
            _is_constant_load(load_a)
            and _is_constant_load(load_b)
            and (load_a, load_b) == (load_a2, load_b2)
        ):
            loc = sequential_source_locations_merge(
                (load_a2.source_location, load_b2.source_location)
            )
            dup2 = models.Dup2(source_location=loc)
            preserve_stack_manipulations(result, slice(idx + 2, idx + 4), [dup2])
            modified = True
            idx += 3
        else:
            idx += 1
    block.ops[:] = result
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

    preserve_stack_manipulations(loads, slice(1, None), [dup_op])
    return True


def _is_constant_load(op: models.TealOp) -> bool:
    return op.op_code in LOAD_OP_CODES or (isinstance(op, models.FrameDig) and op.n < 0)
