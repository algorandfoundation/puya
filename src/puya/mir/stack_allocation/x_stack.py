import itertools
from collections.abc import Iterable, Sequence, Set

import attrs

from puya import log
from puya.errors import InternalError
from puya.mir import models as mir
from puya.mir.context import ProgramMIRContext
from puya.mir.stack import Stack
from puya.mir.vla import VariableLifetimeAnalysis

logger = log.get_logger(__name__)


@attrs.define(eq=False, repr=False)
class BlockRecord:
    block: mir.MemoryBasicBlock
    local_references: list[mir.AbstractStore | mir.AbstractLoad]
    live_in: Set[str]
    live_out: Set[str]
    children: "list[BlockRecord]" = attrs.field(factory=list)
    parents: "list[BlockRecord]" = attrs.field(factory=list)
    co_parents: "list[BlockRecord]" = attrs.field(factory=list)
    siblings: "list[BlockRecord]" = attrs.field(factory=list)

    x_stack_in: Sequence[str] | None = None
    x_stack_out: Sequence[str] | None = None

    def __repr__(self) -> str:
        # due to recursive nature of BlockRecord, provide str implementation to
        # simplify output
        return f"BlockRecord({self.block})"

    @staticmethod
    def by_index(block: "BlockRecord") -> int:
        return block.block.id


@attrs.frozen
class EdgeSet:
    out_blocks: Sequence[BlockRecord] = attrs.field(converter=tuple[BlockRecord, ...])
    in_blocks: Sequence[BlockRecord] = attrs.field(converter=tuple[BlockRecord, ...])


def sort_by_appearance(
    variables: Set[str], block: mir.MemoryBasicBlock, *, load: bool = True
) -> Sequence[str]:
    appearance = list[str]()
    block_ops = block.ops if load else reversed(block.ops)
    if load:
        virtual_ops = (o.local_id for o in block_ops if isinstance(o, mir.AbstractLoad))
    else:
        virtual_ops = (o.local_id for o in block_ops if isinstance(o, mir.AbstractStore))
    for local_id in virtual_ops:
        if local_id in variables and local_id not in appearance:
            appearance.append(local_id)
            # don't keep searching once we are done
            if len(appearance) == len(variables):
                break
    return appearance


def len_and_value(value: tuple[str, ...]) -> tuple[int, tuple[str, ...]]:
    return len(value), value


def find_shared_x_stack(x_stack_candidates: Sequence[Sequence[str]]) -> Sequence[str]:
    """Find a common subsequence that is shared by all x-stacks"""
    cache = dict[tuple[tuple[str, ...], tuple[str, ...]], tuple[str, ...]]()

    def lcs(s1: tuple[str, ...], s2: tuple[str, ...]) -> tuple[str, ...]:
        key = (s1, s2)
        result = cache.get(key)
        if result is None:
            i = len(s1)
            j = len(s2)
            if i == 0 or j == 0:
                result = ()
            elif s1[-1] == s2[-1]:
                result = (*lcs(s1[:-1], s2[:-1]), s1[-1])
            else:
                result = max(lcs(s1[:-1], s2), lcs(s1, s2[:-1]), key=len_and_value)
            cache[key] = result
        return result

    shared, *others = sorted({tuple(s) for s in x_stack_candidates}, key=len_and_value)
    for other in others:
        shared = lcs(shared, other)
    return shared


def get_x_stack_load_ops(record: BlockRecord) -> set[mir.AbstractLoad]:
    block = record.block
    assert block.x_stack_in is not None

    remaining = set(block.x_stack_in)
    load_ops = []
    for ref in record.local_references:
        if isinstance(ref, mir.AbstractLoad) and ref.local_id in remaining:
            remaining.remove(ref.local_id)
            load_ops.append(ref)

    if remaining:
        raise InternalError(
            f"Failed to move {', '.join(remaining)} from the x-stack",
            location=block.source_location,
        )

    return set(load_ops)


def get_x_stack_store_ops(record: BlockRecord) -> set[mir.AbstractStore]:
    block = record.block
    assert block.x_stack_out is not None

    remaining = set(block.x_stack_out)
    store_ops = []
    for ref in reversed(record.local_references):
        if isinstance(ref, mir.AbstractStore) and ref.local_id in remaining:
            remaining.remove(ref.local_id)
            store_ops.append(ref)

    if remaining:
        raise InternalError(
            f"Failed to copy {', '.join(remaining)} to the x-stack",
            location=block.source_location,
        )

    return set(store_ops)


def add_x_stack_ops(sub: mir.MemorySubroutine, record: BlockRecord) -> None:
    block = record.block
    # determine ops to replace
    load_ops = get_x_stack_load_ops(record)
    store_ops = get_x_stack_store_ops(record)

    stack = Stack.begin_block(sub, block)
    for index, op in enumerate(block.mem_ops):
        if op in store_ops:
            assert isinstance(op, mir.AbstractStore)
            # can replace virtual store op because only variables that could be fully
            # scheduled are on the x-stack
            block.mem_ops[index] = op = mir.StoreXStack(
                local_id=op.local_id,
                depth=stack.xl_height - 1,  # store to bottom
                atype=op.atype,
                source_location=op.source_location,
            )
        elif op in load_ops:
            assert isinstance(op, mir.AbstractLoad)
            block.mem_ops[index] = op = mir.LoadXStack(
                local_id=op.local_id,
                depth=stack.xl_height - stack.x_stack.index(op.local_id) - 1,
                atype=op.atype,
                source_location=op.source_location,
            )
        op.accept(stack)


def add_x_stack_ops_to_edge_sets(sub: mir.MemorySubroutine, edge_sets: Sequence[EdgeSet]) -> None:
    records = dict.fromkeys(
        b
        for edge_set in edge_sets
        for b in itertools.chain(edge_set.out_blocks, edge_set.in_blocks)
        if b.x_stack_in or b.x_stack_out
    )
    for record in records:
        assert record.x_stack_in is not None
        assert record.x_stack_out is not None
        record.block.x_stack_in = record.x_stack_in
        record.block.x_stack_out = record.x_stack_out
        add_x_stack_ops(sub, record)


def _unique_ordered_blocks(blocks: Iterable[BlockRecord]) -> list[BlockRecord]:
    return sorted(set(blocks), key=BlockRecord.by_index)


def get_edge_set(block: BlockRecord) -> EdgeSet | None:
    out_blocks = _unique_ordered_blocks(itertools.chain((block,), block.co_parents))
    # keep expanding out_blocks (and consequently in_blocks) until out_blocks stabilize
    while True:
        in_blocks = _unique_ordered_blocks(s for p in out_blocks for s in p.children)
        new_out_blocks = _unique_ordered_blocks(p for s in in_blocks for p in s.parents)
        if new_out_blocks == out_blocks:
            break
        out_blocks = new_out_blocks

    return EdgeSet(out_blocks, in_blocks) if in_blocks else None


def get_edge_sets(sub: mir.MemorySubroutine, vla: VariableLifetimeAnalysis) -> Sequence[EdgeSet]:
    records = {
        block.block_name: BlockRecord(
            block=block,
            local_references=[
                op for op in block.ops if isinstance(op, mir.AbstractStore | mir.AbstractLoad)
            ],
            live_in=vla.get_live_in_variables(block.ops[0]),
            live_out=vla.get_live_out_variables(block.ops[-1]),
        )
        for block in sub.body
    }
    blocks = list(records.values())

    # given blocks 1,2,3,4,5,6 and 7
    # edges: 1->5, 2->4, 2->5, 2->6, 3->5, 7->6, 7->8
    #
    # e.g  1  2  3   7
    #       \/|\/   / \
    #      / \|/ \ /   \
    #     4   5   6     8
    #
    #   consider 2
    #   4, 5 & 6 are children
    #   1 & 3 are co-parents of 5, 7 is a co-parent of 6
    # 1, 2, 3 and 7 form the out_blocks of an edge set
    # 4, 5 & 6 are the in_blocks of the same edge set

    # 1. first pass
    # populate children and parents
    for block in blocks:
        block.children = [records[c] for c in block.block.successors]
        for child in block.children:
            child.parents.append(block)

    # 2. second pass - boundary mapping
    for block in blocks:
        # determine siblings
        for parent in block.parents:
            for child in parent.children:
                if child is not block and child not in block.siblings:
                    block.siblings.append(child)

        # determine co-parents
        for child in block.children:
            for parent in child.parents:
                if parent is not block and parent not in block.co_parents:
                    block.co_parents.append(parent)

    edge_sets = dict[EdgeSet, None]()
    for block in blocks:
        # keep expanding edge set until it stabilizes
        edge_set = get_edge_set(block)
        if edge_set:
            edge_sets[edge_set] = None
        else:
            block.x_stack_out = ()

        if not block.parents:
            block.x_stack_in = ()

    return list(edge_sets.keys())


def schedule_sets(vla: VariableLifetimeAnalysis, edge_sets: Sequence[EdgeSet]) -> None:
    # determine all blocks referencing variables, so we can track if all references to a
    # variable are scheduled to x-stack
    stores = dict[str, set[mir.MemoryBasicBlock]]()
    loads = dict[str, set[mir.MemoryBasicBlock]]()
    for variable in vla.all_variables:
        stores[variable] = vla.get_store_blocks(variable)
        loads[variable] = vla.get_load_blocks(variable)

    for edge_set in edge_sets:
        in_blocks = edge_set.in_blocks
        out_blocks = edge_set.out_blocks

        # get potential l-stacks (unordered)
        l_stacks = [
            *(b.live_out for b in out_blocks),
            *(b.live_in for b in in_blocks),
        ]

        # determine shared l-stack variables for this edge_set
        # determine all valid x-stacks (ordered)
        first, *others = l_stacks
        common_locals = frozenset(first).intersection(*others)

        # TODO: better results might be possible if we allow reordering of x-stack
        x_stack_candidates = [
            *(sort_by_appearance(common_locals, b.block, load=False) for b in out_blocks),
            *(sort_by_appearance(common_locals, b.block, load=True) for b in in_blocks),
        ]

        # find an x_stack for this EdgeSet
        x_stack = find_shared_x_stack(x_stack_candidates)

        for block in out_blocks:
            assert block.x_stack_out is None
            block.x_stack_out = x_stack
            for x in x_stack:
                stores[x].remove(block.block)

        for block in in_blocks:
            assert block.x_stack_in is None
            block.x_stack_in = x_stack
            for x in x_stack:
                loads[x].remove(block.block)

    # adjust final x-stacks based on what could be fully scheduled
    variables_not_fully_scheduled = {
        var for var, blocks in itertools.chain(stores.items(), loads.items()) if len(blocks) > 0
    }
    variables_successfully_scheduled = sorted(stores.keys() - variables_not_fully_scheduled)
    for block in {b for es in edge_sets for b in itertools.chain((*es.out_blocks, *es.in_blocks))}:
        assert block.x_stack_out is not None
        assert block.x_stack_in is not None
        block.x_stack_out = tuple(
            x for x in block.x_stack_out if x in variables_successfully_scheduled
        )
        block.x_stack_in = tuple(
            x for x in block.x_stack_in if x in variables_successfully_scheduled
        )

    if variables_successfully_scheduled:
        logger.debug(
            f"Allocated {len(variables_successfully_scheduled)} "
            f"variable/s to x-stack: {', '.join(variables_successfully_scheduled)}"
        )


def validate_pair(parent: BlockRecord, child: BlockRecord) -> bool:
    parent_x = parent.x_stack_out
    child_x = child.x_stack_in
    assert parent_x is not None
    assert child_x is not None
    if parent_x != child_x:
        logger.error(
            f"x-stacks do not match for {parent.block} -> {child.block}: "
            f"{', '.join(parent_x)} -> {', '.join(child_x)}"
        )
        return False
    if parent_x:
        logger.debug(f"shared x-stack for {parent.block} -> {child.block}: {', '.join(parent_x)}")
    return True


def validate_x_stacks(edge_sets: Sequence[EdgeSet]) -> bool:
    ok = True
    for edge_set in edge_sets:
        for parent in edge_set.out_blocks:
            for child in edge_set.in_blocks:
                ok = validate_pair(parent, child) and ok
    return ok


def x_stack_allocation(_ctx: ProgramMIRContext, sub: mir.MemorySubroutine) -> None:
    # this is basically baileys algorithm
    vla = VariableLifetimeAnalysis(sub)
    edge_sets = get_edge_sets(sub, vla)
    if not edge_sets:
        # nothing to do
        return

    logger.debug(f"Found {len(edge_sets)} edge set/s for {sub.signature.name}")
    schedule_sets(vla, edge_sets)

    if not validate_x_stacks(edge_sets):
        raise InternalError("Could not schedule x-stack")

    add_x_stack_ops_to_edge_sets(sub, edge_sets)
