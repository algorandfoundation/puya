from collections import deque
from collections.abc import Iterator

import structlog

from puya.context import CompileContext
from puya.ir import models
from puya.ir.builder import TMP_VAR_INDICATOR
from puya.ir.visitor_mem_replacer import MemoryReplacer

logger: structlog.typing.FilteringBoundLogger = structlog.get_logger(__name__)


def bfs_block_order(sub: models.Subroutine) -> Iterator[models.BasicBlock]:
    q = deque[models.BasicBlock]()
    q.append(sub.body[0])
    visited = {sub.body[0]}
    while q:
        block = q.popleft()
        yield block
        for succ in block.successors:
            if succ not in visited:
                q.append(succ)
                visited.add(succ)


def copy_propagation(_context: CompileContext, subroutine: models.Subroutine) -> bool:
    set_lookup = dict[models.Register, list[models.Register]]()
    all_equivalence_sets = list[list[models.Register]]()

    def add_to_equiv_sets(dest: models.Register, sauce: models.Register) -> None:
        try:
            equiv_set = set_lookup[sauce]
            assert sauce in equiv_set
        except KeyError:
            set_lookup[sauce] = equiv_set = [sauce]
            all_equivalence_sets.append(equiv_set)
        equiv_set.append(target)
        set_lookup[dest] = equiv_set

    modified = False
    for block in bfs_block_order(subroutine):
        for phi in block.phis.copy():
            if not phi.args:
                continue
            # if all of a phi's arguments are in the same equivalence set,
            # the phi is actually redundant and can be eliminated
            first_arg, *rest = phi.args
            try:
                first_arg_equiv_set = set_lookup[first_arg.value]
            except KeyError:
                continue
            rest_locals = {arg.value for arg in rest}
            if rest_locals.issubset(first_arg_equiv_set):
                first_arg_equiv_set.append(phi.register)
                block.phis.remove(phi)
                modified = True

        for op in block.ops.copy():
            match op:
                case models.Assignment(targets=[target], source=models.Register() as source):
                    add_to_equiv_sets(dest=target, sauce=source)
                    block.ops.remove(op)
                    modified = True

    for equivalence_set in all_equivalence_sets:
        assert len(equivalence_set) >= 2
        equiv_set_ids = ", ".join(x.local_id for x in equivalence_set)
        logger.debug(f"Found equivalence set: {equiv_set_ids}")
        for reg in equivalence_set:
            if TMP_VAR_INDICATOR not in reg.name:
                replacement = reg
                break
        else:
            replacement = equivalence_set[0]
        find_set = equivalence_set.copy()
        find_set.remove(replacement)

        replaced = MemoryReplacer.apply(
            find=find_set, replacement=replacement, blocks=subroutine.body
        )
        if replaced:
            find_local_ids = "{" + ", ".join(x.local_id for x in find_set) + "}"
            logger.debug(
                f"Replacing {find_local_ids} with {replacement.local_id}"
                f" made {replaced} modifications"
            )
            modified = True

    return modified
