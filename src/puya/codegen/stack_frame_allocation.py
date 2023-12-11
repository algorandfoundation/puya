from collections.abc import Sequence

import attrs
import structlog

from puya.avm_type import AVMType
from puya.codegen import ops
from puya.codegen.context import ProgramCodeGenContext
from puya.codegen.stack_koopmans import peephole_optimization
from puya.codegen.vla import VariableLifetimeAnalysis

logger = structlog.get_logger(__name__)


def get_lazy_fstack(subroutine: ops.MemorySubroutine) -> list[ops.StoreVirtual]:
    result = list[ops.StoreVirtual]()
    seen_local_ids = set[str]()
    # TODO: consider more than the entry block
    entry = subroutine.body[0]
    # if entry is re-entrant then can't lazy allocate anything
    if entry.predecessors:
        return result
    for op in entry.ops:
        if isinstance(op, ops.StoreVirtual) and op.local_id not in seen_local_ids:
            seen_local_ids.add(op.local_id)
            result.append(op)
    return result


def get_local_id_types(subroutine: ops.MemorySubroutine) -> dict[str, AVMType]:
    variable_mapping = dict[str, AVMType]()
    for block in subroutine.all_blocks:
        for op in block.ops:
            if isinstance(op, ops.StoreVirtual):
                try:
                    existing_type = variable_mapping[op.local_id]
                except KeyError:
                    existing_type = op.atype
                variable_mapping[op.local_id] = existing_type | op.atype
    return variable_mapping


def get_allocate_op(
    subroutine: ops.MemorySubroutine,
    all_variables: Sequence[str],
    allocate_on_first_store: list[str],
) -> ops.Allocate | None:
    # determine variables to allocate at beginning of frame,
    # and order them so bytes are listed first, followed by uints

    allocate_at_entry = list[str]()
    variable_type_mapping = get_local_id_types(subroutine)
    num_uints = num_bytes = 0
    for variable in all_variables:
        if variable in allocate_on_first_store:
            continue
        allocate_at_entry.append(variable)
        match variable_type_mapping[variable]:
            case AVMType.uint64:
                num_uints += 1
            case AVMType.bytes:
                num_bytes += 1
            case AVMType.any:
                # treat any as uint when pre-allocating
                num_uints += 1
    if not allocate_at_entry:
        return None
    allocate_at_entry = sorted(allocate_at_entry, key=lambda x: variable_type_mapping[x].value)
    return ops.Allocate(
        allocate_on_entry=allocate_at_entry,
        num_bytes=num_bytes,
        num_uints=num_uints,
    )


def allocate_locals_on_stack(
    _context: ProgramCodeGenContext, subroutine: ops.MemorySubroutine
) -> None:
    vla = VariableLifetimeAnalysis.analyze(subroutine)
    all_variables = vla.all_variables
    if not all_variables:
        return

    first_store_ops = get_lazy_fstack(subroutine)
    allocate_on_first_store = [op.local_id for op in first_store_ops]

    allocate = get_allocate_op(subroutine, all_variables, allocate_on_first_store)
    allocate_at_entry = allocate.allocate_on_entry if allocate else []
    if allocate:
        subroutine.preamble.ops.append(allocate)
    logger.debug(f"{subroutine.signature.name} f-stack entry: {allocate_at_entry}")
    logger.debug(f"{subroutine.signature.name} f-stack on first store: {allocate_on_first_store}")

    subroutine.body[0].f_stack_in = allocate_at_entry
    for block in subroutine.body[1:]:
        block.f_stack_in = [*allocate_at_entry, *allocate_on_first_store]

    for block in subroutine.body:
        for index, op in enumerate(block.ops):
            match op:
                case ops.StoreVirtual(
                    local_id=local_id, source_location=src_location, atype=atype
                ):
                    block.ops[index] = ops.StoreFStack(
                        local_id=local_id,
                        source_location=src_location,
                        insert=op in first_store_ops,
                        atype=atype,
                    )
                case ops.LoadVirtual(
                    local_id=local_id,
                    source_location=src_location,
                    atype=atype,
                ):
                    block.ops[index] = ops.LoadFStack(
                        local_id=local_id,
                        source_location=src_location,
                        atype=atype,
                    )
                case ops.RetSub() as retsub:
                    block.ops[index] = attrs.evolve(retsub, f_stack_size=len(all_variables))
    peephole_optimization(subroutine)
