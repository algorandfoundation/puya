import attrs

from puya.parse import sequential_source_locations_merge
from puya.teal import models
from puya.teal._util import preserve_stack_manipulations
from puya.teal.optimize._data import LOAD_OP_CODES


def perform_constant_stack_shuffling(block: models.TealBlock) -> bool:
    result = list[models.TealOp]()
    loads = list[models.TealOp]()
    simplified = list[models.TealOp]()
    modified = False
    for op in block.ops:
        if _is_constant_load(op):
            simplified.append(op)
            loads.append(op)
        elif loads and op.op_code in ("dup", "dupn"):
            modified = True
            simplified.append(op)
            (n,) = op.immediates or (1,)
            assert isinstance(n, int)
            # extend loads with n copies of the last load
            loads.extend([attrs.evolve(loads[-1], source_location=op.source_location)] * n)
        elif loads:
            match op:
                case models.Uncover(n=n) if n < len(loads):
                    modified = True
                    simplified.append(op)
                    uncovered = loads.pop(-(n + 1))
                    loads.append(uncovered)
                case models.Cover(n=n) if n < len(loads):
                    modified = True
                    simplified.append(op)
                    covered = loads.pop()
                    loads.insert(len(loads) - n, covered)
                case _:
                    result.extend(
                        preserve_stack_manipulations(loads, simplified) if modified else loads
                    )
                    loads = []
                    simplified = []
                    result.append(op)
        else:
            result.append(op)
    if loads:
        result.extend(preserve_stack_manipulations(loads, simplified) if modified else loads)
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
            dup2 = preserve_stack_manipulations(
                [models.Dup2(source_location=loc)], [load_a2, load_b2]
            )
            result[idx : idx + 4] = [load_a, load_b, *dup2]
            modified = True
            idx += 3
        else:
            idx += 1
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
    loads[1:] = preserve_stack_manipulations([dup_op], loads[1:])
    return True


def _is_constant_load(op: models.TealOp) -> bool:
    return op.op_code in LOAD_OP_CODES or (isinstance(op, models.FrameDig) and op.n < 0)
